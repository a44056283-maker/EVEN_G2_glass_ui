# EVEN Hub v0.5.15 历史记录全量修复测试报告

生成时间：2026-05-05 16:34 Asia/Shanghai

## 结论

- 构建状态：TEST_BUILD_READY
- 上架状态：NOT APPROVED FOR STORE RELEASE
- 修复目标：彻底修复手机端各类目历史记录和全部历史记录不可达、不可见或保存失败后静默空白的问题。

## 修复内容

1. 新增手机端“历史”书签入口。
2. 新增独立历史页 `history-panel-all`，纳入页面锁页机制。
3. 历史页同时显示：
   - 全部历史
   - 视觉历史
   - 语音历史
   - 交易历史
   - OpenCLAW 历史
   - 设置历史
4. OpenCLAW 对话记录改为写入 `openclaw` 类目，不再混入 `voice`。
5. IndexedDB 成功保存后仍写入 localStorage 摘要镜像，避免 WebView/权限波动导致刷新后空白。
6. localStorage 备用保存增加图片字段降级策略：图片过大时保留文字、答案、时间和类目，不能整包失败。

## 验证

- `npm --workspace apps/evenhub-plugin run pack`：通过，版本递增到 0.5.15。
- `tsc --noEmit -p apps/evenhub-plugin/tsconfig.json`：通过。
- `tsc -p packages/shared/tsconfig.json --noEmit`：通过。
- `tsc -p packages/vision-adapter/tsconfig.json --noEmit`：通过。
- `tsc -p services/api-server/tsconfig.json --noEmit`：通过。

## 版本与包

- 插件版本：0.5.15
- 项目内 EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- 桌面 EHPK：`/Users/luxiangnan/Desktop/g2-vision-voice-assistant-v0.5.15-history-fix-test.ehpk`
- SHA256：`c086c96332e9dd9123133cdf12b1ecd12d9c1402ac6aa364ff50c4217b38d728`
- 大小：84050 bytes

## 必测清单

每轮真机至少验证：

1. 视觉识别 3 次后，视觉历史和全部历史均出现记录。
2. 语音问答 3 次后，语音历史和全部历史均出现记录。
3. 交易只读 3 次后，交易历史和全部历史均出现记录。
4. OpenCLAW 问答 2 次后，OpenCLAW 历史和全部历史均出现记录。
5. 进入“历史”书签，全部历史和分类历史均可见。
6. 刷新手机页面后，历史记录仍保留。
7. 清空历史后，全部分类和全部历史均显示为空态。

未通过任一项时继续修复，不允许上架正式版。
