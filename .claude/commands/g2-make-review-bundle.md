---
description: 生成给 GPT 审批的 Claude 完工报告包，并复制到 iCloud outbox
---

请读取 CLAUDE.md。

任务名：

$ARGUMENTS

请执行：

bash scripts/gpt-advisor/prepare_review_bundle.sh "$ARGUMENTS"

然后输出：
1. 本地 bundle zip 路径
2. iCloud outbox 路径
3. latest_review_bundle.zip 路径
4. SHA256
5. 下一步让用户上传哪个文件给 GPT 审批
