# 天禄 G2 运维助手

Even Realities G2 + R1 + 手机摄像头 + 天禄交易系统的智能眼镜运维助手。

项目最终定位不是单一“视觉语音助手”，而是：

- iPhone 16 Pro Max 或其他手机摄像头负责拍照/抽帧
- Even G2 负责小屏显示、G2 麦克风输入、镜腿事件
- R1 戒指负责菜单选择、确认和轻量交互
- MiniMax / 本地 ASR / OpenCLAW 负责语音、问答、TTS 和推理
- 9099 交易控制台只读接口负责实时价格、持仓、机器人状态、M1-M5 / L5 数据
- 手机扬声器或蓝牙耳机负责播放回答

## 当前模块

1. 视觉识别：手机拍照/相册选图、带问题识图、识别历史、继续追问。
2. 呼叫天禄：G2 原生麦克风、手机/耳机麦克风兜底、本地 ASR、语音意图路由。
3. 交易状态：公网 9099 控制台只读聚合、实时价格、持仓、机器人状态、M1-M5 / L5 评测。
4. 设置诊断：权限检查、G2/R1 设备信息、网络与后端连通性诊断。

## 项目结构

```text
apps/evenhub-plugin       Even Hub 插件前端
apps/web-console          后续调试控制台预留
services/api-server       Node.js API 后端
packages/minimax-adapter  MiniMax M2.7 + TTS 适配
packages/vision-adapter   视觉模型适配
packages/asr-adapter      ASR 适配
packages/shared           共享类型
docs/                     安装、G2、MiniMax、隐私文档
```

## 当前环境要求

需要 Node.js 22+ 和 npm。API key 只放在后端 `.env`，不要写入 Even Hub 前端。

## 当前进度口径

- 代码功能完成度：约 45%
- 真机稳定可审核完成度：约 35-40%
- 当前优先级：先稳定“呼叫天禄”语音闭环，再整理交易状态与眼镜端 UI。
