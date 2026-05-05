# v0.5.19 G2 灰度低分辨率预览 SDK 路径报告

时间：2026-05-05 17:15

## 结论

本版本按官方 Even Hub SDK 的图片建议调整眼镜端拍照预览发送路径：优先使用 `updateImageRawData` 推荐的 `number[]`，并在发送前将图片压缩到 G2 图片容器限制内的低分辨率灰度 JPEG 字节数组。

本版本状态：允许上传测试，不批准正式上架。

## 变更

- 版本号：0.5.19
- 眼镜端预览容器仍使用 `ImageContainerProperty`，尺寸保持 288 x 144。
- 图片发送继续走串行队列，避免 SDK 明确禁止的并发图片传输。
- `updateImageRawData` 发送顺序：
  1. 288 x 144 灰度低质量 JPEG `number[]`
  2. 288 x 144 灰度 base64
  3. 288 x 144 灰度 data URL
  4. 192 x 96 灰度低质量 JPEG `number[]`
  5. 192 x 96 灰度 base64
  6. 192 x 96 灰度 data URL
  7. 原始 base64
  8. 原始 data URL
- 若全部失败，错误会记录每种 payload 的 SDK 返回结果，便于判断是 `imageSizeInvalid`、`imageToGray4Failed` 还是 `sendFailed`。

## 官方 SDK 依据

- `ImageContainerProperty` 支持图片容器，宽度范围 20-288，高度范围 20-144。
- 图片容器创建后必须调用 `updateImageRawData` 才会显示实际图片。
- `ImageRawDataUpdate.imageData` 支持 `number[] | string | Uint8Array | ArrayBuffer`，并推荐 `number[]`。
- 官方说明要求图片传输不能并发，必须队列化。
- 官方说明提示图片尽量色彩单一，眼镜内存有限，不应频繁发送。

## 验证

- `node node_modules/typescript/bin/tsc --noEmit -p apps/evenhub-plugin/tsconfig.json`：通过
- `node node_modules/typescript/bin/tsc -p packages/shared/tsconfig.json --noEmit`：通过
- `node node_modules/typescript/bin/tsc -p services/api-server/tsconfig.json --noEmit`：通过
- `node ../../node_modules/typescript/bin/tsc -p tsconfig.json`：通过
- `esbuild` 前端构建：通过
- EvenHub CLI pack：通过

说明：当前 Codex 会话的 PATH 没有系统 `npm`，且 Codex App 自带 Node 加载 Rollup 原生模块时遇到 macOS 签名限制，因此本轮使用本地 `esbuild` 生成前端产物，再使用官方 EvenHub CLI 打包。

## 产物

- EHPK：`/Users/luxiangnan/Desktop/g2-vision-voice-assistant-v0.5.19-g2-gray-preview-sdk-test.ehpk`
- SHA256：`e84cd982f76d78b7c5eb9d44cbd9a3e27d7fced060f9c81e0d294de7b9a1d6bc`

## 真机验收重点

1. 上传 v0.5.19 后确认设置页版本号为 0.5.19。
2. 新拍照 3 次，观察眼镜端是否出现灰度预览。
3. 如果不显示，查看运行错误里 `G2 image preview failed` 的 payload 返回结果。
4. 新拍照 3 次后检查历史记录是否立即出现缩略图。
5. 视觉识别完成后检查同一条历史是否从“照片已采集，正在上传识别”更新为 AI 结果。

