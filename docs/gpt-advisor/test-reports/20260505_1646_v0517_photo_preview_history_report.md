# EVEN Hub v0.5.17 拍照预览与采集照片历史测试报告

生成时间：2026-05-05 16:46 Asia/Shanghai

## 结论

- 构建状态：TEST_BUILD_READY
- 上架状态：NOT APPROVED FOR STORE RELEASE
- 修复目标：拍照后眼镜端显示图片预览，并在历史记录中保留采集照片。

## 修复内容

1. 眼镜端新增图片预览能力：
   - 使用 EVEN Hub SDK `ImageContainerProperty`
   - 调用 `updateImageRawData`
   - 预览图压缩到 288 x 144 以内
   - 图片发送串行排队，避免并发传输
2. 拍照采集成功后，G2 先显示图片预览，再继续自动上传识别。
3. 预览发送失败时自动降级为文字确认，不阻塞识别链路。
4. 视觉历史新增 `imageDataUrl`，IndexedDB 保存采集照片。
5. 历史记录中新增“查看采集照片 / 收起采集照片”按钮。
6. localStorage 镜像不保存原图，只保存摘要和少量缩略图，避免配额导致历史空白。

## 验证

- `npm --workspace apps/evenhub-plugin run pack`：通过，版本递增到 0.5.17。
- `tsc --noEmit -p apps/evenhub-plugin/tsconfig.json`：通过。
- `tsc -p packages/shared/tsconfig.json --noEmit`：通过。
- `tsc -p services/api-server/tsconfig.json --noEmit`：通过。

## 版本与包

- 插件版本：0.5.17
- 项目内 EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- 桌面 EHPK：`/Users/luxiangnan/Desktop/g2-vision-voice-assistant-v0.5.17-photo-preview-history-test.ehpk`
- SHA256：`3c820f63e99a4b770c8d5da16b9623a4474027f1e079391587986159b732370b`
- 大小：84872 bytes

## 必测清单

1. 眼镜端拍照后出现照片预览，而不是只有文字提示。
2. 预览后自动进入识别流程。
3. 连续拍照 3 次，G2 预览不闪退、不卡死。
4. 手机端视觉历史出现记录和缩略图。
5. 点击“查看采集照片”可以看到本次采集照片。
6. 刷新手机页面后，IndexedDB 中的采集照片仍可查看。
7. 如果 G2 图片预览失败，仍应显示文字确认并继续识别。

未通过任一项时继续修复，不允许上架正式版。
