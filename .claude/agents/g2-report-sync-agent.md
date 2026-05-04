---
description: G2 报告同步代理
---

# G2 报告同步代理

## 职责

同步报告到 GitHub 和 iCloud。

## 核心任务

1. **GitHub 同步**
   - git add .
   - git commit -m "fix: ..."
   - git push origin main

2. **iCloud 同步**
   - 复制到 outbox
   - 记录 SHA256

3. **审核状态跟踪**
   - 写入 CURRENT_STATUS.md
   - 更新 MODULE_UPGRADE_WORKFLOW.md

## 关键路径

- `docs/gpt-advisor/bundles/`
- `~/Library/Mobile Documents/com~apple~CloudDocs/Tianlu-G2-Claude-Reports/outbox/`

## 验收标准

- [ ] GitHub push 成功
- [ ] iCloud outbox 有备份
- [ ] CURRENT_STATUS.md 已更新