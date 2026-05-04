# 天禄 G2 运维助手架构

## 总体定位

`天禄 G2 运维助手` 是一个单一 Even Hub 插件加一个后端桥接服务，不再拆成多个零散软件。

```text
Even G2 / R1
  - 576 x 288 Glass UI
  - R1/G2 输入
  - G2 麦克风 PCM

iPhone Even App WebView
  - 手机网页 UI
  - 手机摄像头
  - 手机/蓝牙耳机播放
  - 调试、设置、日志

G2 Bridge API
  - /vision
  - /audio WebSocket
  - /ask
  - /tts
  - /asr/status
  - /trading/overview
  - /openclaw/status

Runtime Adapters
  - MiniMax VLM/Text/TTS
  - ASR adapter
  - OpenCLAW adapter
  - Trading readonly adapter
  - Tianlu memory adapter
```

## 前端分层

```text
apps/evenhub-plugin/src/main.ts
  控制器与事件编排

apps/evenhub-plugin/src/glass/
  眼镜端 576 x 288 UI
  不能依赖 HTML/CSS

apps/evenhub-plugin/src/camera/
  手机摄像头预热、截帧

apps/evenhub-plugin/src/voice/
  G2 PCM / WebSocket

apps/evenhub-plugin/src/input/
  R1/G2 输入 normalize 与 debug

apps/evenhub-plugin/src/api/
  前端只访问 G2 Bridge 后端
```

## 后端分层

当前后端目录为 `services/api-server`，承担执行手册里的 `services/g2-bridge` 角色。

```text
services/api-server/src/server.ts
  Fastify server and routes

services/api-server/src/asrAdapter.ts
  PCM -> transcript adapter

services/api-server/src/openclaw.ts
  Backend-only OpenCLAW calls

services/api-server/src/tradingBotAdapter.ts
  Trading bot readonly status
```

## 安全边界

1. G2 本体没有摄像头，视觉输入来自手机摄像头。
2. G2 本体没有扬声器，TTS 输出来自手机或蓝牙耳机。
3. G2 麦克风主路径必须是 `audioControl(true)` + `audioEvent.audioPcm`。
4. 前端不直连 OpenCLAW。
5. 交易系统第一版只读。
6. 所有 key/token 只放后端环境变量。
