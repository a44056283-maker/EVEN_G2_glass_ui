# MiniMax 能力接入路线图

当前产品新定位：`天禄 G2 助手`。详细基线见 `docs/tianlu-g2-assistant-latest-shape.md`。

## P0：先跑通眼镜主流程

- `MiniMax-M2.7-highspeed`：短回答、总结、问答。
- `coding-plan-vlm`：手机拍照真实图片理解。
- `Text to Speech HD`：中文朗读，手机或蓝牙耳机播放。

## P1：搜索增强

- `coding-plan-search`：联网搜索 MCP。
- 用途：识别商品后查价格、识别菜单后查解释、识别建筑/设备后查资料。
- 规则：必须由用户明确触发，不默认每次识别都搜索。

## P2：语音输入

- G2 麦克风 PCM 16kHz mono 16bit。
- ASR 做 adapter，不绑定单一服务。
- 默认 push-to-talk，避免持续录音。
- V1 先实现网页按钮“呼叫天禄”，使用浏览器 SpeechRecognition 识别“你好天禄 + 问题”，再调用 `/ask`。
- 如果 Even App/微信 WebView 返回 `not-allowed`，先用 `getUserMedia` 诊断原始麦克风是否可用：若麦克风可用但 SpeechRecognition 不可用，说明容器禁用了浏览器语音转文字，下一步接后端 ASR。
- 已新增 G2 麦克风采集：Even Hub SDK `bridge.audioControl(true)` 接收 `audioEvent.audioPcm`，录制约 4 秒 PCM 后 POST `/transcribe`。当前后端 ASR 仍是 stub，下一步接真实 ASR。

## P3：生成类工具

- `image-01`：生成参考图、说明图、视觉 mockup。
- `Hailuo`：生成演示视频。
- `music` / `lyrics`：娱乐或内容创作工具。

这些能力不进入 V0 默认链路，避免延迟、成本和交互复杂度过高。

## P4：交易系统只读增强

- 目标：在 G2 上语音查看白名单币种价格、机器人在线状态、持仓与盈亏摘要。
- 边界：只读，不下单、不平仓、不改仓、不推送机器人命令。
- 默认：审核包关闭实时交易功能，只保留记忆检索和交易规则问答。
- 内部测试：通过 `TRADING_READONLY_ENABLED=true` 打开只读交易网关。
- 详细方案见 `docs/trading-readonly-integration-plan.md`。

## 额度保护

- V0 点击一次最多调用：1 次 VLM + 1 次文本 + 1 次 TTS。
- 视频抽帧版必须有最小 10 秒上传间隔。
- 连续观察模式必须有开关和状态提示。
- 搜索、图片生成、音乐、视频必须由用户明确触发。
