---
description: 对指定 G2 模块做只读审计，不修改代码
---

请读取 CLAUDE.md。

用户指定模块：$ARGUMENTS

本轮只读审计，不要修改代码。

必须输出：
1. 相关文件
2. 当前实现
3. 根因判断
4. 最小补丁方案
5. 风险点
6. 建议测试命令

审计报告写入：
docs/gpt-advisor/audits/YYYYMMDD_HHMM_$ARGUMENTS_audit.md
