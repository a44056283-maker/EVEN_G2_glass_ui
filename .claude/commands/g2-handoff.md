---
description: 生成当前项目交接文档给 GPT/Claude 继续接手
---

请读取 CLAUDE.md。

生成交接文件：
docs/gpt-advisor/handoffs/YYYYMMDD_HHMM_local_project_snapshot_for_gpt.md

内容包含：
1. 当前项目状态
2. 已修复事项
3. 未解决问题
4. 当前 P0
5. 最近修改文件
6. 测试结果
7. EHPK 路径与 SHA256
8. 下一步建议

不要输出 .env、API key、token、密码、交易密钥或私钥。
