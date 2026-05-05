# EVEN Hub v0.5.16 语音定位上下文测试报告

生成时间：2026-05-05 16:40 Asia/Shanghai

## 结论

- 构建状态：TEST_BUILD_READY
- 上架状态：NOT APPROVED FOR STORE RELEASE
- 修复目标：除交易状态外，将实时定位上下文加入视觉识别和呼叫天禄问答链路。

## 修复内容

1. `AskRequest` 增加 `capturedAt` 和 `locationContext`。
2. 手机端 `askAssistant()` 支持传入定位上下文。
3. 呼叫天禄普通问答会读取定位开关并附加实时定位上下文。
4. 图片追问会附加实时定位上下文。
5. 后端 `/ask` 会把非交易问题的提问时间和实时位置上下文加入 prompt。
6. 后端交易意图强制过滤位置上下文，不进入交易只读 prompt。
7. 定位开关默认开启，用户仍可在设置页关闭。

## 隐私与边界

- 定位失败不阻塞问答。
- 位置仅作为当前回答辅助，不写入长期记忆。
- 后端 prompt 明确要求不得输出精确坐标。
- 交易状态不使用实时定位。

## 验证

- `npm --workspace apps/evenhub-plugin run pack`：通过，版本递增到 0.5.16。
- `tsc --noEmit -p apps/evenhub-plugin/tsconfig.json`：通过。
- `tsc -p packages/shared/tsconfig.json --noEmit`：通过。
- `tsc -p packages/vision-adapter/tsconfig.json --noEmit`：通过。
- `tsc -p services/api-server/tsconfig.json --noEmit`：通过。

## 版本与包

- 插件版本：0.5.16
- 项目内 EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- 桌面 EHPK：`/Users/luxiangnan/Desktop/g2-vision-voice-assistant-v0.5.16-location-voice-test.ehpk`
- SHA256：`075cd076d4e740f24ae4baed1f367ee6cc52242c6b60398c62fdfdb1551b0783`
- 大小：84157 bytes

## 必测清单

1. 设置页确认“视觉识别加入粗略定位”默认开启。
2. 首次呼叫天禄时系统请求定位权限。
3. 问“我附近有什么/我现在适合去哪”时，回答结合位置上下文。
4. 问“BTC 价格/交易状态/持仓风险”时，不出现位置相关内容。
5. 定位权限拒绝后，呼叫天禄仍能回答，并提示定位不可用。
6. 视觉识别和图片追问仍能正常加入定位上下文。

未通过任一项时继续修复，不允许上架正式版。
