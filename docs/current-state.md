# 当前状态审计

审计日期：2026-05-02

依据：`../天禄 G2 运维助手 - Codex 执行手册 v1.txt`

## 产品目标

当前项目应收束为单一软件：

```text
天禄 G2 运维助手
```

由一个 Even Hub 插件和一个后端桥接服务组成，覆盖视觉识别、R1 控制、G2 麦克风、天禄问答、OpenCLAW、交易系统只读状态、风险告警、设备诊断和运行手册。

## 项目结构

```text
apps/evenhub-plugin/       Even Hub 插件前端、手机网页、G2 Glass UI、R1/G2 输入
services/api-server/       当前 G2 Bridge 后端，负责 /vision /audio /ask /tts /asr/status 等
packages/                  MiniMax、ASR、视觉、交易、记忆等适配包
docs/                      项目文档
scripts/                   集成冒烟测试脚本
store-assets/              商店素材
data/remote-memory-cache/  天禄记忆与交易系统历史记忆缓存
```

说明：执行手册里的 `services/g2-bridge` 在当前仓库中对应 `services/api-server`。

## 前端入口

- `apps/evenhub-plugin/index.html`
- `apps/evenhub-plugin/src/main.ts`
- `apps/evenhub-plugin/src/style.css`

## 眼镜端渲染相关文件

- `apps/evenhub-plugin/src/glass/GlassRenderer.ts`
- `apps/evenhub-plugin/src/glass/glassScreens.ts`
- `apps/evenhub-plugin/src/glass/glassText.ts`
- `apps/evenhub-plugin/src/glass/glassTheme.ts`
- `apps/evenhub-plugin/src/glass/glassLayout.ts`
- `apps/evenhub-plugin/src/display.ts`

当前状态：已有 `GlassRenderer`，但仍存在旧 `display.ts` 与新 `glass/` 并行的历史包袱。近期已临时回退成单 TextContainer 稳定显示。

## 手机网页 UI 文件

- `apps/evenhub-plugin/index.html`
- `apps/evenhub-plugin/src/style.css`
- `apps/evenhub-plugin/src/main.ts`

## R1/G2 输入处理

- `apps/evenhub-plugin/src/events.ts`
- `apps/evenhub-plugin/src/input/normalizeEvenInputEvent.ts`
- `apps/evenhub-plugin/src/glass/glassInputDebug.ts`
- `apps/evenhub-plugin/src/main.ts`

当前状态：已有 normalize 与 debug 页入口，但还需要按阶段 2 用真机记录 envelope/type/source。

## 相机控制

- `apps/evenhub-plugin/src/camera.ts`
- `apps/evenhub-plugin/src/camera/cameraStream.ts`
- `apps/evenhub-plugin/src/main.ts`

当前状态：网页端已增加直接拍照/选择照片 fallback。R1 视觉流程已有状态机雏形，但仍需按阶段 3 分离为 `cameraController` / `visionController` 并固定“手机预热、R1 只截帧”的流程。

## 语音 / G2 麦克风

- `apps/evenhub-plugin/src/glass/glassMicProbe.ts`
- `apps/evenhub-plugin/src/voice/g2MicStream.ts`
- `apps/evenhub-plugin/src/g2-mic.ts`
- `apps/evenhub-plugin/src/speech.ts`
- `services/api-server/src/asrAdapter.ts`
- `services/api-server/src/server.ts` 的 `/audio` WebSocket

当前状态：G2 MicProbe 路径存在；旧浏览器 SpeechRecognition 代码仍在 `speech.ts` 中，但已从主要入口降级。阶段 4 需要专门验收 PCM bytes/chunks。

## 后端接口

当前后端：`services/api-server/src/server.ts`

已有接口：

- `GET /health`
- `POST /vision`
- `GET /audio` WebSocket，支持 `mode=probe | mock-asr | asr`
- `POST /ask`
- `POST /tts`
- `POST /transcribe`
- `GET /asr/status`
- `GET /memory/search`
- `GET /trading/overview`
- `GET /openclaw/status`

适配文件：

- `services/api-server/src/asrAdapter.ts`
- `services/api-server/src/openclaw.ts`
- `services/api-server/src/tradingBotAdapter.ts`

## app.json 权限

文件：`apps/evenhub-plugin/app.json`

当前权限：

- `camera`
- `album`
- `g2-microphone`
- `network`，白名单：`https://g2-vision.tianlu2026.org`

缺口：

- 尚未加入 `phone-microphone`。如果后续实现手机/蓝牙耳机录音 fallback，需要加入；如果不实现，应保持不加，避免审核质疑。

## .env.example 缺口

文件：`.env.example`

已有主要变量：

- `VITE_G2_BRIDGE_HTTP_URL`
- `VITE_G2_BRIDGE_WS_URL`
- `VITE_G2_SESSION_TOKEN`
- `MINIMAX_*`
- `ASR_*`
- `OPENCLAW_*`
- `TRADING_*`

问题：

- `ASR_HTTP_URL` 与 `ASR_HTTP_API_KEY` 出现重复定义。
- `OPENCLAW_TIMEOUT_MS=20000` 与执行手册建议的 6000ms 不一致，可在阶段 6 统一。
- `MINIMAX_GROUP_ID` 未列出，若账号需要 group_id 后续补充。

## 错误路径搜索结果

### Browser SpeechRecognition

存在于：

- `apps/evenhub-plugin/src/speech.ts`

当前判断：保留为实验/兜底代码可以，但不得作为主链路。主要入口已改为 G2 MicProbe。

### getUserMedia({ audio: true })

存在于：

- `apps/evenhub-plugin/src/speech.ts`

当前判断：不应由默认语音入口触发。后续若实现 phone-microphone fallback，应改为录音上传 ASR，而不是 Web Speech。

### 前端 localhost / 127.0.0.1

存在于：

- `apps/evenhub-plugin/vite.config.ts`
- `apps/evenhub-plugin/package.json` 的 simulator/dev 脚本

当前判断：这是本地开发代理，生产前端代码不应直连 localhost；可保留开发配置。

### OpenCLAW /v1/chat/completions / /v1/responses

存在于：

- `services/api-server/src/openclaw.ts`

当前判断：正确位置在后端，不在前端。

### innerHTML

存在于：

- `apps/evenhub-plugin/src/history.ts`
- `apps/evenhub-plugin/src/main.ts`

当前判断：仅手机网页 DOM 列表使用，不是 G2 眼镜 UI；可保留。

## 当前可用能力

- 手机网页视觉识别基本链路存在。
- MiniMax VLM/文本/TTS 适配存在。
- G2 GlassRenderer 存在，但真机稳定性仍需优先。
- `/audio` WebSocket 支持 probe/mock-asr/asr。
- `/ask` 已具备 OpenCLAW 尝试与本地 fallback。
- 交易只读 mock/real adapter 存在。

## 当前主要失败点

1. 眼镜端多容器 HUD 在真机上显示不稳定，已临时回退到单容器。
2. R1 相机控制还未完成“手机预热、R1 只截帧”的严格分层。
3. G2 麦克风是否能收到 PCM 仍需真机阶段验收。
4. ASR 真实服务未确认，MiniMax ASR endpoint 为空。
5. OpenCLAW 真实问答链路可能 timeout。
6. 交易系统真实只读接口需要现场确认。

## 下一阶段建议

严格进入阶段 1：整理 GlassRenderer + TL OS HUD，优先稳定显示，不再尝试未经真机验证的复杂多容器布局。
