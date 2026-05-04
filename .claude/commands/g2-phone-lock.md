---
description: 修复手机网页 Phone UI 锁页隔离，防止页面混杂龟缩
---

请读取 CLAUDE.md。

任务：Phone UI 锁页隔离。

要求：
1. Phone UI 4 页：vision / voice / trading / openclaw
2. Glass UI 独立，不共享状态
3. 手机 tab 点击只切页，不触发 G2 业务
4. 页面显示由 registry 单点控制
5. 不改 Glass UI 主结构
6. 不改业务逻辑

执行 typecheck/build/pack:g2，并写报告。
