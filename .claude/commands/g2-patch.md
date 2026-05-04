---
description: 对指定 G2 模块执行最小补丁、测试、打包、写报告
---

请读取 CLAUDE.md。

用户指定补丁任务：$ARGUMENTS

执行规则：
1. 先审计
2. 再最小修改
3. 不扩大范围
4. 不修改禁止事项
5. 跑 typecheck/build/pack:g2
6. 写 test report
7. 输出 EHPK 路径和 SHA256

报告写入：
docs/gpt-advisor/test-reports/YYYYMMDD_HHMM_$ARGUMENTS_report.md
