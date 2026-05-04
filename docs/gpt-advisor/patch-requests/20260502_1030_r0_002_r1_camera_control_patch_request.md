# R0-002 / P0-002 R1 复用稳定视觉识别链路整改任务

创建时间：2026-05-02 10:30

## 本轮目标

让 R1 戒指复用 R0-001 已经稳定的网页视觉识别闭环，实现：

- R1 单击拍照。
- R1 双击发送。
- R1 上滑重拍。
- R1 下滑取消。

## 本轮禁止事项

- 不改 G2 麦克风。
- 不改 ASR。
- 不改 OpenCLAW。
- 不改交易机器人接口。
- 不改 MiniMax VLM/TTS 业务逻辑。
- 不大改手机网页 UI。
- 不大改 Glass UI。
- 不让 R1 触发 file input。
- 不新增第二套 `/vision` fetch 逻辑。

## 需要复用的 R0-001 视觉识别函数

- `runCaptureFlow(prompt?, preparedImage?)`
- `recognizeImage(image, prompt)`
- `setVisionResultPanel(...)`
- `safeGlassShow(...)`
- `speakIfEnabled(...)`

## 本轮验收标准

- [ ] captured 状态下 R1 单击不发送、不重拍，只提示“双击发送”。
- [ ] captured 状态下 R1 双击才发送 pendingCapturedImage。
- [ ] captured 状态下 R1 上滑重拍。
- [ ] captured 状态下 R1 下滑取消。
- [ ] R1 不触发 file input。
- [ ] 手机网页能显示 R1 / Camera Debug 状态。
- [ ] typecheck/build/pack 通过。
