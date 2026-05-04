# R1 单触两步视觉识别测试报告

时间：2026-05-02 14:13

## 本轮范围

本轮只执行 R0-002c：R1 单触两步视觉识别流程。

没有新增“天禄视觉引擎”方案；没有修改 G2 麦克风、ASR、OpenCLAW、交易机器人接口；没有重构手机网页 UI 或 Glass UI。

## 修改文件

- `apps/evenhub-plugin/src/main.ts`
- `apps/evenhub-plugin/src/glass/glassScreens.ts`
- `apps/evenhub-plugin/src/display.ts`
- `apps/evenhub-plugin/src/camera/visionEngine.ts`
- `apps/evenhub-plugin/index.html`
- `apps/evenhub-plugin/package.json`
- `package-lock.json`

## R1 行为最终表

| 状态 | R1 单触 | R1 双击 | R1 上滑 | R1 下滑 |
| --- | --- | --- | --- | --- |
| `camera_ready` | 拍照 / 截帧 | 只提示，不上传 | 提示单触拍照 | 返回首页 |
| `captured` | 600ms 内只提示；600ms 后确认上传 | 不上传，只提示单触确认 | 重拍 | 取消，回 ready |
| `uploading` | 忽略 | 忽略 | 忽略 | 忽略 |
| `result` | 继续进入视觉识别 | 返回首页或忽略 | 提示结果完成 | 返回首页 |
| `error` | 重试进入视觉识别 | 返回首页或忽略 | 提示错误 | 返回首页 |

## 关键实现

- 新增 `uploadInFlight`，防止重复上传。
- 新增 `lastUploadSource`，上传来源会标记为 `r1-single-confirm`。
- `captured + click` 改为主上传路径。
- `captured + double_click` 不再上传，只提示“已拍照，请 R1 单触确认上传”。
- `captured + click` 加入 600ms 防误触窗口。
- 手机网页和眼镜提示文案已从“双击上传”改为“再次单触上传”。

## 调试字段

`Camera / R1 Debug` 现在包含：

- `r1VisionState`
- `visionEngine`
- `videoSize`
- `pendingCapturedImage`
- `msSinceLastCaptured`
- `uploadInFlight`
- `lastInput`
- `lastCaptureAt`
- `lastUploadAt`
- `lastUploadSource`
- `lastVisionError`

## 本机验证

- `npm run typecheck`：通过
- `npm run build`：通过
- `npx evenhub pack app.json dist -o g2-视觉-语音助手.ehpk`：通过

## 打包结果

EHPK：

`/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/g2-vision-voice-assistant/apps/evenhub-plugin/g2-视觉-语音助手.ehpk`

SHA256：

`99fefd64f8a0aeda6f850da4ad80eb4c7545a0d7d0acb58a4d2dd5a8761151c7`

版本：

`0.3.7`

## 真机待验收

1. R1 进入视觉识别并打开手机拍照入口。
2. 拍照返回插件后，`pendingCapturedImage=yes`。
3. 600ms 内 R1 单触不上传，只提示再次单触。
4. 600ms 后 R1 单触上传 `/vision`。
5. 调试字段显示 `lastUploadSource=r1-single-confirm`。
6. 网页和 G2 均显示识别结果。

## 未解决问题

- R1 不能直接控制 iOS/Even App 原生相机快门，这是当前官方 SDK / WebView 能力边界。
- 如果 Even App 原生相机界面打开后不转发 R1 事件，插件只能在拍照返回后接管上传确认。

## 下一步建议

进入真机验收。如果 `pendingCapturedImage=yes` 后 R1 单触仍不上传，下一步只查 `handleG2ControlEvent -> handleVisionR1Intent` 事件是否在 `captured` 状态下抵达。
