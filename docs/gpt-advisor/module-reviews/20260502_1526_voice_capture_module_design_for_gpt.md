# 呼叫天禄语音采集模块构思与校准请求

时间：2026-05-02 15:26

项目路径：

`/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/g2-vision-voice-assistant`

## 1. 模块目标

“呼叫天禄”模块不要和视觉识别、交易状态、OpenCLAW 设置混成一团。它应该先成为一个独立、稳定的语音入口。

目标交互：

```text
用户选择“呼叫天禄”
→ 进入语音对话子菜单
→ 用户触发语音采集
→ 系统按环境选择可用麦克风
→ 语音转文字
→ 判断用户意图
→ 普通问题进入天禄问答
→ “帮我看看这是什么”进入视觉识别
→ “看看今天收益/风险”进入交易只读
→ G2 显示结果
→ 手机/耳机朗读
```

## 2. 当前用户对产品形态的要求

1. 不要做复杂的大杂烩。
2. 选择“呼叫天禄”后，下方子菜单必须是语音模块自己的内容。
3. 当前书签 2/4 下方应该显示：
   - 语音对话
   - 手动发送
4. 不应该继续显示视觉识别的：
   - 直接拍照
   - 相册选图
5. 语音识别到“帮我看看这是什么”时，可以自动进入视觉识别能力。
6. 语音采集要多环境自适应：
   - 第一优先：G2 眼镜麦克风
   - 第二优先：手机麦克风
   - 第三优先：蓝牙耳机麦克风
   - 最后兜底：文字输入

## 3. 当前已知实现

### 3.1 前端入口

主要文件：

`apps/evenhub-plugin/src/main.ts`

当前入口函数：

```ts
runVoiceFlow()
runG2MicWebSocketVoiceFlow()
runPhoneMicFallbackFlow()
runAssistantQuestion()
routeTextQuestionFromUserAction()
tryAutoCaptureFromVoice()
```

当前逻辑大致为：

```text
runVoiceFlow()
→ 如果有 Even bridge：runG2MicWebSocketVoiceFlow()
→ 否则如果可以请求手机麦克风：runPhoneMicFallbackFlow()
→ 否则提示用文字输入
```

### 3.2 G2 麦克风路径

主要文件：

`apps/evenhub-plugin/src/glass/glassMicProbe.ts`

当前链路：

```text
bridge.audioControl(true)
→ bridge.onEvenHubEvent(event => event.audioEvent?.audioPcm)
→ WebSocket /audio?mode=probe
→ 后端返回 audio_debug
→ G2 显示 PCM bytes / chunks
```

问题：

当前 `mode=probe` 只证明有没有收到 PCM，不做 ASR，也不进入问答。

### 3.3 手机 / 耳机麦克风路径

当前 `runPhoneMicFallbackFlow()` 只做：

```text
navigator.mediaDevices.getUserMedia({ audio: true, video: false })
→ 读取 audio track label
→ stop tracks
→ 提示“麦克风可用，但真实 ASR 未配置”
```

问题：

这不是实际语音对话，只是权限测试。

### 3.4 浏览器语音识别路径

主要文件：

`apps/evenhub-plugin/src/speech.ts`

已有：

```ts
listenOnce()
```

使用：

```text
window.SpeechRecognition / window.webkitSpeechRecognition
```

问题：

这个函数目前没有接入主流程。它可以作为手机网页 / Safari / 部分 WebView 的兜底，但不能作为 G2 主链路。

### 3.5 后端音频路径

主要文件：

`services/api-server/src/server.ts`

WebSocket：

```text
GET /audio?mode=probe
GET /audio?mode=mock-asr
GET /audio?mode=asr
```

当前后端支持：

1. `probe`：统计 PCM bytes/chunks
2. `mock-asr`：收到一定音频后返回固定 transcript
3. `asr`：调用真实 ASR adapter

### 3.6 ASR adapter

主要文件：

`services/api-server/src/asrAdapter.ts`

当前支持：

```text
ASR_PROVIDER=mock
ASR_PROVIDER=http + ASR_HTTP_URL
ASR_PROVIDER=minimax + MINIMAX_ASR_ENDPOINT
```

已知问题：

MiniMax M2.7 文本模型不是 ASR。当前不能假设 MiniMax 已经有可用语音转文字接口。

如果 `ASR_PROVIDER=minimax` 但 `MINIMAX_ASR_ENDPOINT` 为空，会报：

```text
真实 ASR 未接入：ASR_PROVIDER=minimax 但 MINIMAX_ASR_ENDPOINT 为空
```

## 4. 当前主要断点

### 断点 1：G2 语音采集停留在 MicProbe

现在“呼叫天禄”看起来像开始录音，但实际只是：

```text
G2 PCM bytes/chunks 统计
```

它没有稳定完成：

```text
PCM → transcript → runAssistantQuestion() → 回答
```

### 断点 2：手机 / 耳机麦克风兜底不是完整功能

当前只是测试权限，不会：

- 录音
- 转文字
- 调用 `/ask`
- 触发视觉意图

### 断点 3：语音意图到视觉识别的链路不够稳

已有意图判断：

```ts
isVisionIntent(question)
```

可识别：

```text
帮我看看这是什么
帮我识别
看一下
读一下
```

但 `tryAutoCaptureFromVoice()` 依赖当前是否有已准备好的相机流。

如果没有相机流，就可能退到旧的“确认打开摄像头”流程。

### 断点 4：语音模块 UI 与功能逻辑不一致

用户已指出：

选择“呼叫天禄”后，下方不能再显示视觉识别按钮。

目前已修复手机网页 UI：

- 视觉识别：显示 `直接拍照 / 相册选图`
- 呼叫天禄：显示 `语音对话 / 手动发送`
- 交易状态：显示 `刷新状态 / 风险摘要`
- 设置：显示 `连接扫描 / 权限自检`

但语音功能本身仍未闭环。

## 5. 建议的新语音模块架构

### 5.1 统一入口

建议新增或重构为一个 Voice Controller：

```text
apps/evenhub-plugin/src/voice/voiceController.ts
```

职责：

```ts
startVoiceSession(options)
stopVoiceSession()
selectCaptureDeviceStrategy()
handleTranscript(text)
routeVoiceIntent(text)
```

### 5.2 设备采集策略

建议抽象：

```ts
type VoiceCaptureStrategy =
  | 'g2-pcm'
  | 'phone-web-speech'
  | 'phone-media-recorder'
  | 'text'
```

优先级：

```text
1. g2-pcm
2. phone-web-speech
3. phone-media-recorder
4. text
```

### 5.3 G2 PCM 主路径

```text
Even bridge ready
→ bridge.audioControl(true)
→ audioEvent.audioPcm
→ WebSocket /audio?mode=mock-asr 或 mode=asr
→ final_transcript
→ handleTranscript(text)
```

开发阶段建议先用：

```text
/audio?mode=mock-asr
```

原因：

先验证“采集 → transcript → 意图路由 → 结果显示”这条链，避免真实 ASR 卡住。

### 5.4 手机 / 耳机兜底路径

可分两种：

#### A. Web Speech

```text
listenOnce()
→ transcript
→ handleTranscript(text)
```

适合：

- 手机 Safari 支持时
- 普通浏览器调试

#### B. MediaRecorder / Audio Blob

```text
getUserMedia({ audio: true })
→ MediaRecorder 录音
→ 上传 /transcribe
→ transcript
→ handleTranscript(text)
```

前提：

后端真实 ASR 可用。

如果真实 ASR 不可用，不建议先做这条。

### 5.5 文字兜底

现有文字输入继续保留：

```text
手动发送
→ routeTextQuestionFromUserAction(text)
→ handleTranscript(text)
```

## 6. 意图路由设计

统一处理：

```ts
handleTranscript(text)
```

内部：

```text
1. 去掉/识别唤醒词：你好天禄 / 天禄 / 天路 / 天鹿
2. 判断视觉意图
3. 判断交易意图
4. 默认普通问答
```

### 6.1 视觉意图

示例：

```text
你好天禄，帮我看看这是什么
天禄，识别一下前面的东西
读一下这个
帮我看看刚才拍的内容
```

期望：

```text
如果当前已有照片 / 最近视觉结果：
→ 用 lastVisionSummary 回答

如果相机/拍照入口可用：
→ 触发现有视觉识别流程

如果不允许自动相机：
→ G2 显示：请在手机端拍照或选择照片
→ 手机端完成后自动上传并显示结果
```

### 6.2 交易意图

示例：

```text
你好天禄，查看今天收益
帮我看一下交易机器人运行如何
风险怎么样
```

期望：

```text
→ /ask
→ trading readonly fallback
→ G2 显示
→ 朗读
```

### 6.3 普通问答

```text
→ /ask
→ MiniMax / OpenCLAW fallback
→ G2 显示
→ 朗读
```

## 7. 建议的最小实施顺序

### Voice P0-001：不要碰真实 ASR，先跑 mock-asr

改动：

```text
startGlassMicProbe 支持 mode 参数
runG2MicWebSocketVoiceFlow 默认使用 mode=mock-asr
收到 final_transcript 后调用 runAssistantQuestion(text)
```

验收：

```text
G2 点击呼叫天禄
→ G2 PCM 发送到后端
→ 后端 mock 返回固定文字
→ 前端进入 runAssistantQuestion
→ G2 显示天禄正在思考/回复
```

### Voice P0-002：mock 文本改成视觉意图

后端 mock-asr 固定返回：

```text
你好天禄，帮我看看这是什么
```

验收：

```text
语音链路触发视觉意图
→ 如果已有图像/最近视觉结果，先用最近视觉结果回答
→ 如果没有，提示手机端拍照/选图
```

### Voice P0-003：手机 Web Speech 兜底

改动：

```text
runPhoneMicFallbackFlow 不再只测权限
如果 listenOnce 可用，调用 listenOnce()
识别后进入 runAssistantQuestion(text)
```

验收：

```text
浏览器 / 手机端点“语音对话”
→ 弹系统语音识别
→ 得到文字
→ 进入问答/视觉意图
```

### Voice P0-004：真实 ASR

最后再接：

```text
ASR_PROVIDER=http
ASR_HTTP_URL=...
```

或真实 MiniMax ASR endpoint。

## 8. GPT 需要校准的问题

请 GPT 重点判断：

1. 当前是否应该把 `mode=probe` 改为 `mode=mock-asr` 作为“呼叫天禄”的默认开发路径？
2. `final_transcript` 是否应该统一进入 `runAssistantQuestion(text)`？
3. 手机 / 耳机麦克风兜底是否先用 `SpeechRecognition`，而不是 MediaRecorder + 未配置 ASR？
4. “帮我看看这是什么”是否应该优先使用最近一次视觉结果，而不是强行打开相机？
5. 如果没有最近视觉结果，是否应提示手机端完成拍照/选图，而不是让 R1 或 G2 直接启动相机？
6. 是否建议新增 `voiceController.ts`，把当前散在 `main.ts` 的语音逻辑抽出来？
7. 当前 OpenCLAW 是否应该暂时不参与语音 P0，避免又把交易网关超时混进语音问题？

## 9. 给 Codex 的建议修复口径

如果 GPT 认可，可以让 Codex 下一步只做：

```text
Voice P0-001:
1. startGlassMicProbe 增加 mode 参数。
2. 呼叫天禄默认走 /audio?mode=mock-asr。
3. 收到 final_transcript 后调用 runAssistantQuestion(text)。
4. 不改视觉模块状态机。
5. 不改交易接口。
6. 不改 OpenCLAW。
7. 不接真实 ASR。
```

这样可以先让“呼叫天禄”从占位变成真实路由闭环。

