# GPT 桌面版审计交接文件

项目：天禄 G2 运维助手 / G2 Vision AI

根目录：

```text
/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/g2-vision-voice-assistant
```

生成时间：2026-05-02

用途：

```text
让 GPT 桌面版快速了解当前智能眼镜软件工程的全部结构、关键代码、脚本、当前阶段、已知问题和审计重点。
```

重要说明：

1. 本文件不包含真实 API key、token、密码。
2. `.env` 存在但不得直接复制给第三方模型。
3. GPT 桌面版如需审计，请优先读取本文件和下方列出的文档。
4. Codex 负责执行代码修改、构建、打包；GPT 负责审计方案、指出链路问题、协助校正脚本。

---

## 1. 当前产品定义

软件名称：

```text
天禄 G2 运维助手
```

当前插件名称：

```text
G2 Vision AI / g2-视觉-语音助手
```

插件包名：

```text
com.luxiangnan.g2visionvoice
```

公网访问：

```text
https://g2-vision.tianlu2026.org
```

目标设备：

```text
Even Realities G2 智能眼镜 + R1 戒指 + iPhone 16 Pro Max
```

核心原则：

```text
G2 眼镜端不是 HTML/CSS。
G2 眼镜端必须通过 Even Hub SDK containers 渲染 576 x 288 UI。
手机网页 UI 只负责调试、设置、日志、权限与预览。
G2 本体没有摄像头和扬声器。
视觉输入来自手机摄像头。
语音输出来自手机扬声器或蓝牙耳机。
G2 麦克风主链路是 audioControl(true) -> audioEvent.audioPcm -> WebSocket -> 后端 ASR。
交易系统第一版只读，不执行下单、平仓、改杠杆、改策略、提现。
```

---

## 2. 当前总控文档

优先读这些：

```text
AGENTS.md
docs/codex-execution-plan-v1.md
docs/current-state.md
docs/architecture.md
docs/glass-ui-design.md
docs/acceptance-checklist.md
docs/tianlu-g2-assistant-latest-shape.md
docs/trading-readonly-integration-plan.md
docs/real-integration-audit-20260501.md
```

外部执行手册在工程上级目录：

```text
/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/天禄 G2 运维助手 - Codex 执行手册 v1.txt
```

---

## 3. 当前阶段计划

完整顺序：

```text
阶段 0：仓库审计与工程规则
阶段 1：GlassRenderer + TL OS 眼镜 HUD
阶段 2：R1/G2 输入调试
阶段 3：R1 相机控制整改
阶段 4：G2 Mic Probe
阶段 5：ASR adapter
阶段 6：/ask + OpenCLAW + 交易只读 fallback
阶段 7：视觉增强 OCR / 屏幕读取 / 观察模式
阶段 8：设备诊断中心 + Runbook
阶段 9：测试、打包、EHPK、SHA256
```

当前已完成/部分完成：

```text
阶段 0：已完成。
阶段 1：已做 TL OS 单 TextContainer HUD，仍需真机显示验收。
阶段 2：已加入输入调试格式和设备诊断入口，仍需 R1 真机事件验证。
阶段 3：下一步重点，先恢复网页相机拍照识别稳定链路。
```

最近打包产物：

```text
apps/evenhub-plugin/g2-vision-voice-assistant.ehpk
apps/evenhub-plugin/g2-视觉-语音助手.ehpk
```

最近 SHA256：

```text
af1652cb52497ec312fa0ae8c46047f8e325ad03b4829b4b43cebadfd5336520
```

---

## 4. 顶层工程结构

```text
apps/evenhub-plugin/       Even Hub 插件，包含手机网页 UI、G2 Glass UI、R1/G2 输入、相机、语音入口
services/api-server/       当前 G2 Bridge 后端，对应执行手册里的 services/g2-bridge
packages/                  MiniMax、ASR、视觉、交易、记忆等适配包
docs/                      项目文档
scripts/                   集成冒烟测试脚本
data/remote-memory-cache/  天禄记忆与交易系统历史记忆缓存
logs/                      本地服务日志
store-assets/              商店素材
```

---

## 5. 前端 Even Hub 插件关键路径

入口：

```text
apps/evenhub-plugin/index.html
apps/evenhub-plugin/src/main.ts
apps/evenhub-plugin/src/style.css
apps/evenhub-plugin/app.json
apps/evenhub-plugin/package.json
apps/evenhub-plugin/vite.config.ts
apps/evenhub-plugin/tsconfig.json
```

当前 `app.json` 权限：

```text
camera
album
g2-microphone
network whitelist: https://g2-vision.tianlu2026.org
```

注意：

```text
当前 app.json 没有 phone-microphone。
如果后续实现手机/蓝牙耳机麦克风 fallback，需要新增 phone-microphone 并实现真实录音上传 ASR。
```

---

## 6. G2 眼镜端 Glass UI 文件

眼镜端核心渲染：

```text
apps/evenhub-plugin/src/glass/GlassRenderer.ts
apps/evenhub-plugin/src/glass/glassScreens.ts
apps/evenhub-plugin/src/glass/glassText.ts
apps/evenhub-plugin/src/glass/glassTheme.ts
apps/evenhub-plugin/src/glass/glassLayout.ts
apps/evenhub-plugin/src/glass/glassInput.ts
apps/evenhub-plugin/src/glass/glassInputDebug.ts
apps/evenhub-plugin/src/glass/glassMicProbe.ts
```

当前 GlassRenderer 状态：

```text
已回到稳定单 TextContainer 主路径。
全屏 576 x 288。
containerID: 1
containerName: main
isEventCapture: 1
```

当前 Glass 页面：

```text
home
vision_preparing
vision_ready
vision_captured
vision_uploading
voice_idle
voice_mic_probe
voice_no_pcm
voice_transcript
trading_status
risk_alert
reply
diagnostics
settings
debug_input
error
```

审计重点：

```text
G2 端不要使用手机网页 DOM/CSS。
真机如果空白，优先检查 container 数量、TextContainer 属性、isEventCapture、文本长度。
```

---

## 7. 手机网页 UI 文件

```text
apps/evenhub-plugin/index.html
apps/evenhub-plugin/src/style.css
apps/evenhub-plugin/src/main.ts
```

当前网页结构：

```text
顶部主页区域：四个一级入口
视觉识别
天禄问答
交易状态
设置
```

当前已修正：

```text
一级入口只切换当前版块，不再直接执行拍照/刷新。
二级版块按当前入口显示，其他版块隐藏。
R1/键盘选择过滤不可见按钮，避免选中隐藏子模块。
```

审计重点：

```text
网页 UI 要像参考图一样：主页在上，点击一级入口后显示对应二级页面。
不要把所有子模块全部堆在首页。
```

---

## 8. 输入与 R1/G2 控制文件

```text
apps/evenhub-plugin/src/events.ts
apps/evenhub-plugin/src/input/normalizeEvenInputEvent.ts
apps/evenhub-plugin/src/glass/glassInputDebug.ts
apps/evenhub-plugin/src/main.ts
```

关键点：

```text
CLICK_EVENT = 0。
部分 SDK/protobuf 情况下 eventType 可能为 undefined，所以代码使用 eventType ?? CLICK_EVENT。
同时解析 textEvent、listEvent、sysEvent。
调试显示 Envelope / Type / Source / State。
```

R1/G2 输入设计：

```text
首页：上下切换一级入口，单击进入。
视觉 ready：单击拍照。
视觉 captured：双击发送，上滑重拍，下滑取消。
语音 idle：单击进入 Mic Probe。
交易状态：单击刷新。
设置/诊断：显示输入事件。
```

当前风险：

```text
R1 真机 source 尚未完全确认，需要在 diagnostics/debug_input 中实测。
```

---

## 9. 相机与视觉文件

旧相机/网页拍照：

```text
apps/evenhub-plugin/src/camera.ts
```

流式相机/R1 截帧：

```text
apps/evenhub-plugin/src/camera/cameraStream.ts
```

主调用位置：

```text
apps/evenhub-plugin/src/main.ts
```

视觉 API：

```text
apps/evenhub-plugin/src/api.ts
apps/evenhub-plugin/src/api/g2BridgeApi.ts
services/api-server/src/server.ts   # POST /vision
```

当前状态：

```text
网页相机链路下一步需要优先修复。
目前顶层“视觉识别”只进入视觉子版块。
真正拍照应由二级动作触发。
```

下一步目标：

```text
先让网页上的“拍照识别 / 直接拍照”稳定调用相机并完成 /vision。
再进入 R1 控制相机。
```

---

## 10. 语音与麦克风文件

G2 MicProbe：

```text
apps/evenhub-plugin/src/glass/glassMicProbe.ts
apps/evenhub-plugin/src/voice/g2MicStream.ts
apps/evenhub-plugin/src/g2-mic.ts
```

浏览器语音历史路径：

```text
apps/evenhub-plugin/src/speech.ts
```

注意：

```text
SpeechRecognition / webkitSpeechRecognition 不能作为主链路。
navigator.mediaDevices.getUserMedia({ audio: true }) 不能作为 G2 麦克风主链路。
G2 主链路必须走 bridge.audioControl(true) -> event.audioEvent.audioPcm。
```

后端音频：

```text
services/api-server/src/server.ts   # WebSocket /audio
services/api-server/src/asrAdapter.ts
```

当前 `/audio` 模式：

```text
probe
mock-asr
asr
```

当前问题：

```text
G2 真机 PCM bytes/chunks 尚未稳定验收。
ASR_PROVIDER / MINIMAX_ASR_ENDPOINT 仍需真实确认。
```

---

## 11. 后端 API 服务路径

入口：

```text
services/api-server/src/server.ts
services/api-server/package.json
```

适配器：

```text
services/api-server/src/asrAdapter.ts
services/api-server/src/openclaw.ts
services/api-server/src/tradingBotAdapter.ts
```

已有接口：

```text
GET  /health
POST /vision
GET  /audio       WebSocket
POST /ask
POST /tts
POST /transcribe
GET  /asr/status
GET  /memory/search
GET  /trading/overview
GET  /openclaw/status
```

审计重点：

```text
/ask 必须 fallback，不得因 OpenCLAW timeout 空白。
OpenCLAW 只能后端调用，前端不得直连 localhost。
交易系统第一版只读。
```

---

## 12. OpenCLAW / 交易系统相关

后端文件：

```text
services/api-server/src/openclaw.ts
services/api-server/src/tradingBotAdapter.ts
docs/trading-readonly-integration-plan.md
docs/real-integration-audit-20260501.md
```

公网/配置参考：

```text
OPENCLAW_BASE_URL=https://even2026.tianlu2026.org
TRADING_BASE_URL=https://console.tianlu2026.org
TRADING_RISK_BASE_URL=http://192.168.13.48:7891
```

注意：

```text
本文件不包含真实 token。
OpenCLAW / 交易系统 token 只应保留在 .env 或后端安全环境中。
```

---

## 13. 环境变量概览

文件：

```text
.env.example
.env
```

不要泄露 `.env`。

主要变量：

```text
PORT
PUBLIC_API_BASE
G2_BRIDGE_SESSION_TOKEN
G2_AUDIO_FINALIZE_MS

MINIMAX_API_KEY
MINIMAX_BASE_URL
MINIMAX_TEXT_MODEL
MINIMAX_TTS_MODEL
MINIMAX_TTS_VOICE_ID

VISION_PROVIDER
VISION_HTTP_ENDPOINT
VISION_HTTP_API_KEY

ASR_PROVIDER
ASR_HTTP_URL
ASR_HTTP_API_KEY
MINIMAX_ASR_ENDPOINT
MINIMAX_ASR_MODEL

TRADING_READONLY_ENABLED
TRADING_BASE_URL
TRADING_BOT_API_BASE
TRADING_BOT_READONLY_TOKEN
TRADING_RISK_BASE_URL
TRADING_ALLOWED_SYMBOLS
TRADING_CACHE_TTL_MS

OPENCLAW_ENABLED
OPENCLAW_BASE_URL
OPENCLAW_GATEWAY_TOKEN
OPENCLAW_AGENT_MODEL
OPENCLAW_ENDPOINT
OPENCLAW_AGENT_NAME
OPENCLAW_TIMEOUT_MS

VITE_G2_BRIDGE_HTTP_URL
VITE_G2_BRIDGE_WS_URL
VITE_G2_SESSION_TOKEN
```

当前 `.env.example` 注意点：

```text
ASR_HTTP_URL / ASR_HTTP_API_KEY 有重复定义，后续应清理。
```

---

## 14. 常用命令

进入目录：

```bash
cd "/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/g2-vision-voice-assistant"
```

Node 工具路径：

```bash
export PATH="/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/.tools/node-v22.22.2-darwin-arm64/bin:$PATH"
```

前端开发：

```bash
npm run dev:plugin
```

后端开发：

```bash
npm run dev:api
```

前端类型检查：

```bash
npm --workspace apps/evenhub-plugin run typecheck
```

后端类型检查：

```bash
npm --workspace services/api-server run typecheck
```

全工程类型检查：

```bash
npm run typecheck
```

前端构建：

```bash
npm --workspace apps/evenhub-plugin run build
```

全工程构建：

```bash
npm run build
```

打包 EHPK：

```bash
npm run pack:g2
cp apps/evenhub-plugin/g2-vision-voice-assistant.ehpk apps/evenhub-plugin/g2-视觉-语音助手.ehpk
shasum -a 256 apps/evenhub-plugin/g2-vision-voice-assistant.ehpk apps/evenhub-plugin/g2-视觉-语音助手.ehpk
```

真实集成冒烟：

```bash
npm run test:real
```

---

## 15. 当前最新构建记录

最近一次通过：

```text
npm --workspace apps/evenhub-plugin run typecheck
npm --workspace apps/evenhub-plugin run build
npm --workspace apps/evenhub-plugin run pack
```

最新 EHPK：

```text
apps/evenhub-plugin/g2-vision-voice-assistant.ehpk
apps/evenhub-plugin/g2-视觉-语音助手.ehpk
```

最新 SHA256：

```text
af1652cb52497ec312fa0ae8c46047f8e325ad03b4829b4b43cebadfd5336520
```

---

## 16. GPT 桌面版建议审计顺序

请 GPT 桌面版按以下顺序审计，不要一次审计所有模块：

```text
1. 网页一级/二级版块结构是否清晰。
2. 网页相机拍照识别链路是否恢复。
3. R1/G2 输入调试是否能在真机上显示 source/type。
4. R1 控制相机是否只做截帧/确认，不触发权限弹窗。
5. G2 MicProbe 是否真的收到 PCM bytes/chunks。
6. /audio probe/mock-asr/asr 三模式是否清晰。
7. /ask fallback 是否稳定返回交易状态。
8. OpenCLAW / 交易只读是否没有任何真实交易动作。
9. EHPK 打包和真机测试路径是否可重复。
```

---

## 17. GPT 与 Codex 协作方式

推荐工作流：

```text
1. Codex 修改工程并运行命令。
2. Codex 输出：改动文件、命令结果、EHPK、SHA256、未解决问题。
3. 用户把本文件和 Codex 输出交给 GPT 桌面版审计。
4. GPT 输出具体问题、建议改哪些文件、建议怎么验证。
5. 用户把 GPT 审计意见贴回 Codex。
6. Codex 按阶段落地修改并再次打包。
```

权限说明：

```text
Codex 不能直接接管 GPT 桌面版的本地权限。
Codex 也不能把自己的工具权限“交换”给 GPT 桌面版。
双方共享工作内容的方式是：文件交接、审计意见粘贴、脚本/日志/测试结果同步。
```

如果后续需要更自动化的桥接，可以新建：

```text
scripts/export_for_gpt_review.sh
scripts/import_gpt_review_notes.sh
docs/gpt-review-notes/
```

---

## 18. 当前最重要的下一步

下一步不要碰语音和 OpenCLAW，先修：

```text
网页视觉识别子版块：
拍照识别 / 直接拍照 -> 获取图片 -> POST /vision -> 显示结果 -> 朗读 fallback
```

验收：

```text
手机网页点击“视觉识别”只进入视觉子版块。
点击二级“拍照识别”能打开相机或文件 fallback。
拍照后能上传 /vision。
返回结果显示在网页和 G2 reply 页面。
如果 TTS 失败，文字显示不能失败。
```

