# 呼叫天禄语音模块审计 - 2026-05-02 15:14

## 本轮范围

只审计“呼叫天禄 / 天禄问答”模块，不修改视觉识别、R1 相机、交易接口和 Glass UI 大结构。

目标是确认当前语音模块缺哪些真实能力，以及下一步如何做成多环境自适应采集：

1. 优先 G2 眼镜麦克风。
2. G2 麦克风不可用时，降级到手机 / 蓝牙耳机麦克风。
3. 语音识别到“帮我看看这是什么”等视觉意图时，触发现有视觉识别能力。

## 当前已有能力

### 1. 语音入口存在

文件：`apps/evenhub-plugin/src/main.ts`

当前 `runVoiceFlow()` 会按运行环境选择：

- 有 Even Bridge 时：进入 `runG2MicWebSocketVoiceFlow('assistant')`
- 没有 G2 麦克风但可请求手机麦克风时：进入 `runPhoneMicFallbackFlow()`
- 都不可用时：提示使用文字输入

### 2. G2 PCM MicProbe 已接入

文件：`apps/evenhub-plugin/src/glass/glassMicProbe.ts`

当前链路：

```text
bridge.audioControl(true)
→ event.audioEvent.audioPcm
→ WebSocket /audio?mode=probe
→ 后端返回 audio_debug
→ G2 显示 PCM bytes/chunks
```

这条链路用于确认 G2 是否能采集 PCM，但当前不是完整语音问答链路。

### 3. 后端 /audio 支持多模式

文件：`services/api-server/src/server.ts`

后端 WebSocket `/audio` 支持：

- `mode=probe`：只统计 PCM bytes/chunks
- `mode=mock-asr`：收到音频后返回固定文本
- `mode=asr`：调用真实 ASR adapter

### 4. 视觉意图识别函数已存在

文件：`apps/evenhub-plugin/src/main.ts`

已有：

- `extractTianluQuestion()`
- `isVisionIntent()`
- `runAssistantQuestion()`
- `tryAutoCaptureFromVoice()`

理论上，“你好天禄，帮我看看这是什么”可以被识别为视觉意图。

## 当前核心缺口

### P0-VOICE-001：G2 语音主链路仍停在 probe 模式

当前 `startGlassMicProbe()` 写死：

```text
/audio?mode=probe
```

结果是：

- 可以证明 PCM 是否收到。
- 但不会返回真实 transcript。
- 也不会触发 `/ask`。
- 更不会触发“帮我看看这是什么”的视觉识别。

所以现在的“呼叫天禄”不是完整问答，只是 MicProbe。

### P0-VOICE-002：手机 / 蓝牙耳机兜底只是权限检查

文件：`apps/evenhub-plugin/src/main.ts`

`runPhoneMicFallbackFlow()` 当前只做：

```text
navigator.mediaDevices.getUserMedia({ audio: true })
→ 拿到 track label
→ stop tracks
→ 显示“麦克风可用，真实 ASR 未配置”
```

它没有：

- 录音。
- 转文字。
- 调用 `/ask`。
- 触发视觉意图。

所以手机 / 耳机麦克风兜底目前还是占位，不是可用功能。

### P0-VOICE-003：浏览器 SpeechRecognition 存在但未接入当前语音流程

文件：`apps/evenhub-plugin/src/speech.ts`

`listenOnce()` 存在，并使用：

```text
window.SpeechRecognition / window.webkitSpeechRecognition
```

但当前 `runVoiceFlow()` 没有走它。

这可以作为手机浏览器 / Safari / 部分 WebView 的低成本兜底，但不能作为 G2 主链路。

### P0-VOICE-004：真实 ASR 未完成配置

文件：`services/api-server/src/asrAdapter.ts`

当前真实 ASR 依赖：

- `ASR_PROVIDER=http` + `ASR_HTTP_URL`
- 或 `ASR_PROVIDER=minimax` + `MINIMAX_ASR_ENDPOINT`
- 或 `ASR_PROVIDER=mock`

如果 `ASR_PROVIDER=minimax` 但 `MINIMAX_ASR_ENDPOINT` 为空，会明确报错。

MiniMax M2.7 文本模型不是 ASR。本项目现在不能假设 MiniMax 已经有可用语音转文字端点。

### P0-VOICE-005：“帮我看看这是什么”触发视觉识别的链路不稳定

`runAssistantQuestion()` 已经识别视觉意图，并调用 `tryAutoCaptureFromVoice()`。

但 `tryAutoCaptureFromVoice()` 依赖：

```text
capturePreparedPhoto()
```

如果当前没有已准备好的 camera stream，就会退到“请点击页面按钮确认打开相机”的老流程。

这需要对齐上一个视觉模块的结论：

- 如果已有相机流：直接截帧并调用 `/vision`
- 如果手机网页环境：触发现有“直接拍照 / 相册选图”入口
- 如果 Even/G2 环境不允许自动开相机：G2 显示“请在手机完成拍照”，手机端完成后自动上传

## 建议的最小整改顺序

### 第一步：先做 mock-asr 闭环

目的：先验证“G2 麦克风 → transcript → 天禄路由 → 视觉意图”通路，不被真实 ASR 卡住。

改法：

- 新增一个语音模式：`voiceMode = mock-asr | probe | asr`
- “呼叫天禄”默认先用：

```text
/audio?mode=mock-asr
```

后端会返回固定文本：

```text
你好天禄，帮我看一下交易机器人运行如何
```

下一步再扩展为：

```text
你好天禄，帮我看看这是什么
```

用于验证视觉意图。

### 第二步：让 final_transcript 真正进入 runAssistantQuestion()

当前 `startGlassMicProbe()` 的 `onTranscript` 只更新 UI。

应改为：

```text
收到 final_transcript
→ runAssistantQuestion(text)
```

这样才能进入：

- 视觉意图
- 普通问答
- 交易只读问答

### 第三步：做“帮我看看这是什么”视觉意图闭环

对齐视觉模块：

```text
语音文本命中视觉意图
→ 如果相机流 ready：截帧自动上传 /vision
→ 如果相机流不 ready：提示手机端完成直接拍照或相册选图
→ 手机端拍照/选图后自动上传
→ G2 显示识别结果
→ 自动朗读
```

### 第四步：手机 / 蓝牙耳机兜底做成真实可用

不要只做权限检测。建议两条兜底：

1. 优先 Web Speech：

```text
listenOnce()
→ runAssistantQuestion(transcript)
```

2. 如果 Web Speech 不可用，再显示文字输入兜底。

MediaRecorder + `/transcribe` 可以放后续，因为当前真实 ASR 未配置。

### 第五步：真实 ASR 最后接

只有前面链路跑通后，再接：

- `ASR_PROVIDER=http`
- 或真实 `MINIMAX_ASR_ENDPOINT`

否则会继续把“采集、路由、视觉意图、真实 ASR”混在一起排查。

## 推荐本轮下一步补丁范围

不要动视觉模块状态机，不要动交易状态，不要动 OpenCLAW。

只改：

1. `apps/evenhub-plugin/src/glass/glassMicProbe.ts`
   - 支持传入 `mode: 'probe' | 'mock-asr' | 'asr'`

2. `apps/evenhub-plugin/src/main.ts`
   - `runG2MicWebSocketVoiceFlow()` 支持选择 `mock-asr`
   - `onTranscript` 调用 `runAssistantQuestion(text)`
   - 手机/耳机兜底从“只测权限”改为显式可用 fallback：
     - Web Speech 可用时走 `listenOnce()`
     - 不可用时提示文字输入

3. `apps/evenhub-plugin/src/glass/glassScreens.ts`
   - 只小改语音页文案，让用户知道：
     - G2 麦克风
     - 手机/耳机兜底
     - 文字输入兜底

## 当前结论

“呼叫天禄”现在最大的问题不是 UI，而是链路停在 MicProbe：

```text
G2 PCM 已经尝试采集
但没有进入 transcript → assistant router → visual intent
```

手机/耳机麦克风也只是权限探测，没有真实语音问答。

下一步应该先把 mock-asr 闭环打通，再做真实 ASR。

