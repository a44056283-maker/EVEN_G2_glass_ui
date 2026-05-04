# 本地项目快照交接给 GPT

生成时间：2026-05-02 09:42

生成范围：仅读取本项目目录。

项目路径：

```text
/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/g2-vision-voice-assistant
```

安全说明：

- 本快照没有输出 `.env` 内容。
- 本快照没有输出 API key、token、密码、交易密钥、私钥。
- 本快照只用于 GPT 审计和生成后续 Codex 整改提示词。

## 1. 当前总体结论

当前项目已经具备工程骨架、Even Hub 插件、G2 GlassRenderer、G2 MicProbe、后端 `/vision`、`/audio`、`/ask`、OpenCLAW adapter、交易只读 adapter 和 EHPK 打包能力。

但核心可用性仍未稳定，当前最小优先级仍应是：

```text
P0：网页视觉识别闭环
P1：G2 眼镜显示视觉结果
P2：R1 输入事件真机日志
P3：R1 控制相机拍照/发送
```

不建议继续同时修改 ASR、OpenCLAW、交易、眼镜 UI 动画等多条线。

## 2. 当前路线图与协作文件

已存在：

```text
SOFTWARE_ROADMAP.md
TIMED_PROGRESS_LOG.md
GPT_DESKTOP_HANDOFF.md
docs/gpt-advisor/README.md
docs/gpt-advisor/CURRENT_STATUS.md
docs/gpt-advisor/NEXT_ACTIONS.md
docs/gpt-advisor/ISSUE_REGISTER.md
docs/gpt-advisor/DECISION_LOG.md
docs/gpt-advisor/MODULE_MAP.md
```

当前路线图估算整体完成度：约 28%。

当前 `NEXT_ACTIONS.md` 指定第一优先级是网页视觉识别闭环。

## 3. app.json 权限状态

文件：

```text
apps/evenhub-plugin/app.json
```

当前权限：

```text
camera
album
g2-microphone
network
```

network whitelist：

```text
https://g2-vision.tianlu2026.org
```

当前未声明：

```text
phone-microphone
```

说明：

- 当前主语音路线应优先 G2 麦克风。
- 如果以后启用手机/蓝牙耳机麦克风兜底，再考虑新增 `phone-microphone`。

## 4. 网页视觉识别闭环现状

相关文件：

```text
apps/evenhub-plugin/src/main.ts
apps/evenhub-plugin/src/camera.ts
apps/evenhub-plugin/src/camera/cameraStream.ts
apps/evenhub-plugin/src/api.ts
apps/evenhub-plugin/src/api/g2BridgeApi.ts
services/api-server/src/server.ts
```

当前实现路径：

```text
网页点击视觉识别入口
-> selectG2Bookmark('vision')
-> 进入视觉二级模块或执行 runCaptureFlow
-> capturePhoto / capturePreparedPhoto / file input fallback
-> recognizeImage
-> 后端 POST /vision
-> describeImage
-> askMiniMax 整理成 G2 短回答
```

关键观察：

1. `camera.ts` 里仍然有 iOS / embedded browser 时优先走 file input fallback 的逻辑：

```text
shouldUseFileCapture()
```

这可能导致用户感觉“网页不会直接调用相机流”，而是走系统相机/相册 picker。

2. `cameraStream.ts` 提供了隐藏 video stream + canvas 截帧路线：

```text
ensureCameraReady()
captureFrameFromCameraStream()
stopCamera()
```

这条路线更适合 R1 控制拍照，但目前网页普通点击仍主要走 `capturePhoto()` 旧路径。

3. 后端 `/vision` bodyLimit 当前是：

```text
12 * 1024 * 1024
```

前端图片压缩配置：

```text
MAX_IMAGE_EDGE = 1280
JPEG_QUALITY = 0.72
```

这应该能降低 `Request body is too large`，但仍需真机确认。

## 5. R1 相机控制现状

相关文件：

```text
apps/evenhub-plugin/src/main.ts
apps/evenhub-plugin/src/input/normalizeEvenInputEvent.ts
apps/evenhub-plugin/src/events.ts
apps/evenhub-plugin/src/camera/cameraStream.ts
```

当前视觉状态机：

```text
idle
preparing
camera_ready
captured
uploading
result
error
```

当前 R1 视觉逻辑：

```text
idle/result/error + click -> enterVisionPage()
enterVisionPage -> ensureCameraReady() -> vision_ready
camera_ready + click -> captureFrameFromCameraStream() -> captured
captured + click -> 上传图片
captured + double_click -> 上传图片
captured + next/previous -> 取消当前图片
```

与用户期望的差异：

- 用户期望进入视觉模块后，R1 第一次点击就能拍照。
- 当前如果还在 `idle`，第一次 R1 click 会进入/准备视觉页，第二次 click 才拍。
- 解决方向：点击首页“视觉识别”或进入视觉页时立即预热相机并设置 `visionState = camera_ready`，不要等 R1 click 才进入准备流程。

## 6. Glass UI 是否混用了网页逻辑

相关文件：

```text
apps/evenhub-plugin/src/glass/GlassRenderer.ts
apps/evenhub-plugin/src/glass/glassScreens.ts
apps/evenhub-plugin/src/glass/glassText.ts
apps/evenhub-plugin/src/display.ts
apps/evenhub-plugin/src/main.ts
```

当前 GlassRenderer：

- 使用单个全屏 `TextContainerProperty`。
- 画布尺寸来自 `GLASS_W / GLASS_H`，当前目标是 576 x 288。
- `isEventCapture = 1`。
- 切页使用 `rebuildPageContainer`。
- 同页更新使用 `textContainerUpgrade`。

当前仍存在的风险：

- 项目里仍有旧 `display.ts`，里面也构建多容器 HUD 页面和电量显示。
- `main.ts` 里同时调用 `GlassRenderer` 和旧 `showOnG2 / showBookmarkOnG2 / formatForG2`。
- 这意味着眼镜 UI 仍可能有两套路径，容易造成“网页改了、眼镜没变”或“眼镜显示混乱”。

建议 GPT 审计重点：

```text
是否可以把 G2 眼镜显示统一收敛到 GlassRenderer，
逐步减少 display.ts 对眼镜端主页面的参与。
```

## 7. G2 麦克风 PCM / MicProbe 状态

相关文件：

```text
apps/evenhub-plugin/src/glass/glassMicProbe.ts
apps/evenhub-plugin/src/voice/g2MicStream.ts
apps/evenhub-plugin/src/g2-mic.ts
services/api-server/src/server.ts
```

当前 MicProbe 实现：

```text
startGlassMicProbe()
-> renderer.show('voice_mic_probe')
-> WebSocket /audio?mode=probe
-> bridge.onEvenHubEvent(event.audioEvent?.audioPcm)
-> ws.send(bytes)
-> bridge.audioControl(true)
-> 每 500ms 更新 PCM bytes/chunks
-> 5 秒无 PCM 显示 voice_no_pcm
```

正向点：

- 主链路确实存在 G2 PCM 路径。
- probe 模式不接真实 ASR。
- 后端 `/audio?mode=probe` 会返回 `audio_debug`。

当前问题：

- 用户反馈真机仍显示麦克风测试页，且说话采集不到。
- 需要确认 `bridge.audioControl(true)` 是否在 Even App 真机环境实际成功。
- 需要确认当前页面是否真正进入 `voicePageState='probe'` 后能收到 `audioEvent`。
- 也需要确认用户测试的是 EHPK 最新包还是公网网页旧版本。

## 8. 浏览器麦克风 / SpeechRecognition 状态

相关文件：

```text
apps/evenhub-plugin/src/speech.ts
apps/evenhub-plugin/src/main.ts
```

当前仍存在：

```text
window.SpeechRecognition
window.webkitSpeechRecognition
navigator.mediaDevices.getUserMedia({ audio: true, video: false })
```

结论：

- 这些路径目前仍在代码中。
- 它们应只作为浏览器/手机兜底或调试，不应作为 G2 主链路。
- 用户看到“手机/蓝牙耳机麦克风权限被当前容器拒绝”时，很可能仍有网页 fallback 被触发或 UI 文案未清理。

建议下一步：

```text
先不要再自动启动浏览器麦克风 fallback。
G2 语音页只显示 G2 PCM MicProbe 状态。
网页兜底麦克风必须有单独按钮，并明确标注“手机麦克风兜底”。
```

## 9. ASR 状态

相关文件：

```text
services/api-server/src/asrAdapter.ts
services/api-server/src/server.ts
```

当前后端 ASR 支持：

```text
ASR_PROVIDER=http
ASR_PROVIDER=mock
ASR_PROVIDER=minimax / minimax-asr
```

当前逻辑：

- `mock` 返回固定文本：

```text
你好天禄，帮我看一下交易机器人运行如何
```

- `minimax` 需要 `MINIMAX_ASR_ENDPOINT`，为空则报错：

```text
真实 ASR 未接入：ASR_PROVIDER=minimax 但 MINIMAX_ASR_ENDPOINT 为空
```

结论：

- ASR 没有真实跑通。
- 这不是 MiniMax M2.7 文本模型可以自动替代的问题。
- 建议先使用 `/audio?mode=mock-asr` 验证 G2 PCM -> websocket -> transcript -> ask。

## 10. OpenCLAW 状态

相关文件：

```text
services/api-server/src/openclaw.ts
services/api-server/src/server.ts
```

当前支持：

```text
OPENCLAW_ENABLED=true
OPENCLAW_BASE_URL
OPENCLAW_GATEWAY_TOKEN / OPENCLAW_TOKEN
OPENCLAW_AGENT_MODEL / OPENCLAW_MODEL
OPENCLAW_ENDPOINT=chat_completions 或 responses
```

当前错误处理：

- 401/403 -> 认证失败。
- 404 -> 未连接。
- 405 -> endpoint 未启用。
- timeout 或其他错误 -> fallback。

`/ask` 逻辑：

- 交易问题优先查交易机器人只读状态。
- 尝试 OpenCLAW。
- OpenCLAW 超时或失败时，如果有 tradingBotStatus，返回本地交易状态 fallback。

结论：

- OpenCLAW adapter 结构存在。
- 用户反馈 OpenCLAW 对话仍不可用，可能是网关真实回答超时或前端语音尚未提供 transcript。
- 先不要把 OpenCLAW 与 G2 麦克风一起排障，必须分阶段。

## 11. 交易只读状态

相关文件：

```text
services/api-server/src/tradingBotAdapter.ts
services/api-server/src/server.ts
```

当前状态：

- `getTradingBotStatus()` 支持真实接口和 mock。
- 没有 `TRADING_BOT_API_BASE` 时返回 mock：

```text
online: true
mode: paper
strategyName: mock-momentum
symbols: BTCUSDT, ETHUSDT
todayPnlPct: 1.2
openPositions: 2
openOrders: 1
riskLevel: normal
source: mock
```

结论：

- 用户反馈第三个交易数据正常，符合当前 mock/fallback 状态。
- 后续接真实交易系统时必须明确显示 `source=real` 或 `source=mock`。

## 12. 当前最小修复集合建议

### 修复 1：先恢复网页视觉识别闭环

目标：

```text
点击网页视觉识别 -> 点击拍照识别 -> file/camera fallback -> /vision -> 显示结果
```

不要同时修 R1、G2 麦克风、OpenCLAW。

重点检查：

- `#vision-capture-action` 是否可见且可点击。
- `runCaptureFlow()` 是否被调用。
- `capturePhoto()` 是否能触发 file input。
- `recognizeImage()` 是否请求正确后端。
- 错误是否清晰显示。

### 修复 2：把 G2 首页/视觉页入口逻辑梳理清楚

目标：

```text
R1 首页选择视觉 -> enterVisionPage()
enterVisionPage 负责预热相机
预热成功后 R1 单击立即截帧
```

重点：

- 不要让 `runR1CaptureFlow()` 直接调用 `handleVisionR1Intent('click')` 导致第一次只是进入准备。
- 首页进入视觉页时就调用 `enterVisionPage()`。

### 修复 3：语音页只保留 G2 MicProbe 主显示

目标：

```text
R1 进入天禄问答 -> voice_idle
R1 单击 -> voice_mic_probe
只显示 PCM bytes/chunks
不自动触发浏览器麦克风
```

重点：

- 屏蔽自动 browser SpeechRecognition。
- 手机/蓝牙麦克风兜底单独做按钮和文案。

### 修复 4：/audio mock-asr 验收

目标：

```text
G2 PCM bytes 能到 /audio?mode=probe
再手动切 /audio?mode=mock-asr
返回固定 transcript
进入 /ask fallback
```

## 13. 给 GPT 的审计问题

请 GPT 优先审计：

1. 当前 `main.ts` 里首页、二级页、R1 控制是否混乱，最小改法是什么？
2. `camera.ts` 和 `cameraStream.ts` 是否应该合并或明确分工？
3. 网页视觉识别 P0 应该保留 file input fallback 还是优先 stream camera？
4. G2 端是否应该统一走 `GlassRenderer`，逐步移除 `display.ts` 主路径？
5. `speech.ts` 是否应从主流程中完全降级为 optional fallback？
6. `/audio?mode=probe` 与 `/audio?mode=mock-asr` 前端是否需要单独调试按钮？
7. 为了今天跑通，最少需要改哪 3 个函数？

## 14. 当前不建议做的事

暂时不要做：

- 重新设计复杂眼镜 UI。
- 接真实 ASR。
- 深度修 OpenCLAW。
- 接真实交易 API。
- 做观察模式。
- 做自动交易动作。
- 同时大改前端和后端。

## 15. 下一步建议给 Codex 的任务

建议下一条 Codex 任务：

```text
只修网页视觉识别闭环。
不要动 G2 MicProbe、ASR、OpenCLAW、交易接口。
目标是网页点击视觉识别后，可以拍照或选图，压缩上传 /vision，并显示结果。
完成后运行 typecheck/build，并把结果追加到 TIMED_PROGRESS_LOG.md 和 docs/gpt-advisor/test-reports/。
```

