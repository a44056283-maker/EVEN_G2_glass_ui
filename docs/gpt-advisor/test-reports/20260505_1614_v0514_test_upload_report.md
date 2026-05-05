# EVEN Hub v0.5.14 P1 测试上传交接报告

生成时间：2026-05-05 16:14 Asia/Shanghai

## 结论

- 构建状态：TEST_BUILD_READY
- 上架状态：NOT APPROVED FOR STORE RELEASE
- 用途：v0.5.13 P1 full fix 后的递增测试版，供 EVEN Hub 上传测试与真机三轮验收。

## 版本与包

- 插件版本：0.5.14
- 项目内 EHPK：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- 桌面 EHPK：`/Users/luxiangnan/Desktop/g2-vision-voice-assistant-v0.5.14-p1-test.ehpk`
- SHA256：`14456c9344344fca9e64fc5aaa28f442be4e91c15147c0b40e60004d563ab526`
- 大小：83557 bytes

## 本轮安全处理

- 用户要求的 `git status --short | grep -E "\.env|token|secret|key|private|mnemonic|seed"`：无命中。
- 用户要求的 `git ls-files | grep -E "(^|/)\.env|token|secret|private|mnemonic|seed"`：仅命中已跟踪 `.venv-local-whisper-asr` 第三方包文件名假阳性，例如 tokenizer/private/seed 命名。
- 额外真实敏感值扫描发现历史缓存资料中存在 `sk-...` 形式明文 key，已在本轮红action：
  - `data/remote-memory-cache/knowledge-strategy/AI子代理文档/天眼AI_Agent工作流_天禄实现版.md`
  - `data/remote-memory-cache/knowledge-strategy/edict_backup_20260417_092424/edict/scripts/qintianjian/minimax_client.py`
- OpenCLAW token 优先级已确认：`OPENCLAW_GATEWAY_TOKEN ?? OPENCLAW_TOKEN`
- 未将真实 OpenCLAW token 写入源码、报告、日志或 EHPK。

## 验证

- `npm --workspace apps/evenhub-plugin run pack`：通过，已递增并打包 v0.5.14。
- `tsc -p packages/shared/tsconfig.json --noEmit`：通过。
- `tsc -p packages/vision-adapter/tsconfig.json --noEmit`：通过。
- `tsc -p services/api-server/tsconfig.json --noEmit`：通过。

## 真机三轮验收清单

每轮必须完成：

1. 启动眼镜端 5 分钟不闪退。
2. 视觉识别 5 次。
3. 取消拍照 2 次。
4. 定位识图 3 次。
5. 照片历史保存 3 次。
6. 语音触发视觉 3 次。
7. 交易白名单价格 3 次。
8. 交易标签切换 3 次。
9. OpenCLAW 记忆问答 2 次。
10. 历史记录刷新 2 次。

未通过任一项时继续修复，不允许上架正式版。
