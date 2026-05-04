# R1 视觉识别控制最小补丁报告

时间：2026-05-02 10:37

## 本轮范围

本轮只修 R1 视觉控制：

- R1 视觉页事件逻辑。
- 相机 ready 检查与手机端启用相机入口。
- R1 captured 状态确认发送逻辑。
- 视觉页 G2 文案。
- 图片截帧最大边压缩。

未修改：

- G2 麦克风 / MicProbe
- ASR
- OpenCLAW
- 交易机器人接口
- TTS 业务逻辑
- 整体 Glass UI

## 修改文件

- `apps/evenhub-plugin/index.html`
- `apps/evenhub-plugin/src/main.ts`
- `apps/evenhub-plugin/src/camera/cameraStream.ts`
- `apps/evenhub-plugin/src/glass/glassScreens.ts`
- `docs/gpt-advisor/patch-requests/20260502_1030_r0_002_r1_camera_control_patch_request.md`

## 关键修复点

1. `handleG2ControlEvent()` 先解析 intent，再做普通事件防抖。
2. `double_click` 不再被 180ms 普通点击防抖吞掉。
3. 纯 `audioEvent` 才直接返回；如果事件同时带输入 envelope，仍继续处理输入。
4. 视觉页内不再调用 `moveControlFocus()` / `announceFocusedControl()`。
5. 视觉页内不再用 `executeCurrentG2Bookmark()` 作为返回，新增显式返回首页逻辑。
6. `captured` 状态下 R1 单击只提示，不发送、不重拍。
7. `captured` 状态下只有 R1 双击发送。
8. R1 拍照后 600ms 内的双击不上传，防止误双击直接发送。
9. R1 不触发 file input。
10. R1 截帧时不再调用 `ensureCameraReady()`，只从已 ready 的 stream 截帧。
11. 手机网页新增 Camera / R1 Debug 状态区域。
12. `captureFrameFromCameraStream()` 增加最大边 1280 压缩。

## 最终状态机规则

| 状态 | R1 单击 | R1 双击 | R1 上滑 previous | R1 下滑 next |
| --- | --- | --- | --- | --- |
| `idle` | 进入视觉页 | 返回首页 | 提示 | 返回首页 |
| `needs_phone_activation` | 提示手机启用相机 | 返回首页 | 提示 | 返回首页 |
| `camera_ready` | 拍照 | 返回首页 | 提示 | 返回首页 |
| `captured` | 只提示双击发送 | 600ms 后发送 | 重拍 | 取消回 ready |
| `uploading` | 忽略 | 忽略 | 忽略 | 忽略 |
| `result` | 继续拍照/回 ready | 返回首页 | 提示 | 返回首页 |
| `error` | 重试进入视觉页 | 返回首页 | 提示 | 返回首页 |

## R1 行为表

- 首页：上下滑切换菜单，单击进入。
- 视觉 ready：单击拍照，下滑返回。
- 视觉 captured：双击发送，上滑重拍，下滑取消，单击仅提示。
- 视觉 uploading：全部输入忽略。
- 视觉 result：单击继续，下滑/双击返回。

## 相机权限处理

- R1 进入视觉页时只检查 `getCameraStreamStatus().ready`。
- 如果相机流未 ready，G2 显示“请在手机上点击启用 R1 相机”。
- 手机网页二级按钮“启用R1相机”调用 `ensureCameraReady()`，由真实 DOM 点击触发相机权限。
- R1 截帧时只从已 ready 的 video stream 截帧，不触发权限弹窗。

## 图片压缩

`captureFrameFromCameraStream()` 增加：

- `MAX_IMAGE_EDGE = 1280`
- 超过 1280 时按比例缩放 canvas。
- JPEG quality = 0.72。
- 返回 `width`、`height`、`dataUrl`，用于调试显示。

## Camera / R1 Debug 面板

手机网页视觉模块新增：

- `r1VisionState`
- `cameraStatus`
- `stream active`
- `videoSize`
- `pendingCapturedImage`
- `lastInput`
- `lastCaptureAt`
- `lastUploadAt`
- `lastVisionError`

## 测试结果

命令：

```bash
export PATH="/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/.tools/node-v22.22.2-darwin-arm64/bin:$PATH"
npm run typecheck
npm run build
npm run pack:g2
```

结果：

- `npm run typecheck`：通过。
- `npm run build`：通过。
- `npm run pack:g2`：通过。

## EHPK

路径：

- `apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- `apps/evenhub-plugin/g2-视觉-语音助手.ehpk`

SHA256：

```text
b6f9496eb16e42b7a5fca1fc63a60823cb4109e986e8e64573c366c43b057ee4
```

## 未解决问题

1. 仍需真机记录 R1 单击、双击、上滑、下滑的真实 envelope/type/source。
2. 若 Even App 容器仍不允许手机端按钮启用 `getUserMedia`，需要换成 file input 或 Even SDK 官方相机能力。
3. R1 电量读取仍未解决，本轮不处理。
4. G2 麦克风、ASR、OpenCLAW 仍未进入本轮。

## 下一步建议

先真机测试本轮：

1. 手机端点击“启用R1相机”。
2. R1 进入视觉页。
3. R1 单击拍照。
4. 立刻双击不应上传，只提示确认。
5. 等 600ms 后双击上传。
6. 单击不上传。
7. 上滑重拍。
8. 下滑取消。

若通过，进入 `R0-003：R1 输入真实日志表 + Glass 结果显示稳定`。

## 2026-05-02 追加修正

根据用户确认的 R1 行为规划，已调整：

- R1 在首页单击“视觉识别”后，`enterVisionPage()` 会立即调用 `ensureCameraReady()` 自动启动手机后置摄像头。
- 如果自动启动失败，才进入 `vision_needs_phone_activation`，提示手机端点击“启用R1相机”作为兜底。
- 保留其余行为：
  - `vision_ready`：单击拍照，下滑返回首页，上滑提示，双击不作为主要动作。
  - `vision_captured`：双击确认发送，上滑重拍，下滑取消，单击只提示。
  - `vision_uploading`：忽略输入。
  - `vision_result`：单击继续拍照，下滑/双击返回首页。
  - `vision_error`：单击重试，下滑返回首页。

验证重新通过：

- `npm run typecheck`
- `npm run build`
- `npm run pack:g2`

最新 EHPK SHA256：

```text
08d1b5c432b41b908a13dc265704ee6fcdecf4e38977ded02f17dff292205609
```
