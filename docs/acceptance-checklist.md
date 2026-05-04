# 验收清单

依据：`天禄 G2 运维助手 - Codex 执行手册 v1`

## 0. 仓库审计

- [x] 输出项目目录结构。
- [x] 标记前端入口、后端入口、G2 渲染、输入、相机、语音文件。
- [x] 搜索 SpeechRecognition、getUserMedia audio、localhost、OpenCLAW endpoint、innerHTML 等路径。
- [x] 创建 `AGENTS.md`。
- [x] 创建 `docs/current-state.md`。
- [x] 创建本验收清单。

## 1. GlassRenderer / TL OS HUD

- [x] G2 首页使用 TL OS HUD，不是手机网页样式。
- [x] 每页 8-10 行以内。
- [ ] 每页能在 576 x 288 simulator 截图中读清楚。
- [ ] 无重叠、无空白、无过长文本。
- [x] 动态状态使用 `textContainerUpgrade`。
- [ ] 真机显示稳定，不因多容器导致空白。

## 2. R1/G2 输入调试

- [ ] `debug_input` 能显示 R1 单击。
- [ ] `debug_input` 能显示 R1 双击。
- [ ] `debug_input` 能显示 R1 上滑。
- [ ] `debug_input` 能显示 R1 下滑。
- [ ] G2 镜腿输入也能显示。
- [x] 日志包含 envelope/type/source/state。
- [x] CLICK_EVENT = 0 / undefined 均能处理。

## 3. R1 相机控制

- [ ] 手机 DOM 按钮能启用相机。
- [ ] `videoWidth/videoHeight > 0`。
- [ ] `vision_ready` 状态下 R1 单击立即截帧。
- [ ] `vision_captured` 状态下 R1 双击发送。
- [ ] R1 上滑重拍。
- [ ] R1 下滑取消。
- [ ] R1 不触发 `getUserMedia` 权限弹窗。

## 4. G2 Mic Probe

- [ ] `voice_mic_probe` 显示 PCM bytes/chunks。
- [ ] 对眼镜说话 bytes 增长。
- [ ] `/audio?mode=probe` 返回 `audio_debug`。
- [ ] 不出现 browser mic not-allowed。

## 5. ASR

- [ ] `/audio?mode=mock-asr` 返回固定 transcript。
- [ ] `/audio?mode=asr` 未配置时返回明确错误。
- [ ] `/asr/status` 显示 provider/available/reason。
- [ ] 不依赖 browser SpeechRecognition。

## 6. /ask 与交易只读

- [ ] `curl /ask` 可以返回交易状态。
- [ ] OpenCLAW timeout 时返回 local fallback。
- [ ] G2 能显示短摘要。
- [ ] 不执行真实交易动作。
- [ ] audit log 记录 userId/text/source/openclawStatus。

## 7. 视觉增强

- [ ] `/vision` 支持基础拍照识别。
- [ ] OCR 模式可读文字。
- [ ] screen/bot-screen 模式可提取屏幕状态。
- [ ] observe 模式可启动/停止，并有限流。

## 8. 诊断与 Runbook

- [ ] G2 诊断页显示关键状态。
- [ ] 手机网页显示详细诊断。
- [ ] 每个错误能对应 runbook。

## 9. 打包

- [x] 当前阶段 `npm --workspace apps/evenhub-plugin run typecheck` 通过。
- [x] 当前阶段 `npm --workspace apps/evenhub-plugin run build` 通过。
- [x] 当前阶段 `npm --workspace apps/evenhub-plugin run pack` 通过。
- [x] EHPK 路径和 SHA256 已记录。
- [ ] 真机主流程通过：R1 拍照 -> 发送 -> G2 显示结果。
