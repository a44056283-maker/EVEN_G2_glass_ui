# EVEN Hub v0.5.18 拍照预览与历史照片热修报告

生成时间：2026-05-05 16:55 Asia/Shanghai

## 结论

- 构建状态：TEST_BUILD_READY
- 上架状态：NOT APPROVED FOR STORE RELEASE
- 修复原因：v0.5.17 已接入图片预览和历史照片字段，但真机反馈仍不可见。本轮增强为拍照即落历史，并增加 G2 图片数据格式兜底。

## 修复内容

1. 拍照获取图片后立即写入视觉历史，状态为“照片已采集，正在上传识别”。
2. AI 识别完成后更新同一条历史记录，不再等识别成功后才创建历史。
3. 历史记录新增 `updateHistoryItem()`，支持原地更新同一条记录。
4. G2 图片预览发送增加两种格式兜底：
   - JPEG base64
   - data URL base64
5. G2 图片发送队列失败后不会污染后续发送队列。
6. localStorage 继续只保存缩略图摘要，完整采集照片仅保存在 IndexedDB。

## 版本与包

- 插件版本：0.5.18
- 项目内 EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- 桌面 EHPK：`/Users/luxiangnan/Desktop/g2-vision-voice-assistant-v0.5.18-photo-preview-history-hotfix.ehpk`
- SHA256：`03489f4c670d7cb1b9ec21c2262ceb12143600555b070bf4b90ce77217b69e27`
- 大小：85066 bytes

## 验证

- `npm --workspace apps/evenhub-plugin run pack`：通过，版本递增到 0.5.18。
- `tsc --noEmit -p apps/evenhub-plugin/tsconfig.json`：通过。
- `tsc -p packages/shared/tsconfig.json --noEmit`：通过。
- `tsc -p packages/vision-adapter/tsconfig.json --noEmit`：通过。
- `tsc -p services/api-server/tsconfig.json --noEmit`：通过。

## 必测清单

1. 安装确认插件版本为 0.5.18。
2. 拍照后立即打开“历史”页，视觉历史应出现“照片已采集”记录。
3. 点击“查看采集照片”，应能看到采集照片。
4. 等 AI 识别完成后，同一条历史记录应更新为识别答案。
5. G2 端拍照后应尝试显示图片预览。
6. 若 G2 图片预览仍失败，识别流程和手机历史照片仍必须成功。

未通过任一项时继续修复，不允许上架正式版。
