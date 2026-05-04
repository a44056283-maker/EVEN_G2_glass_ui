---
description: 读取 GPT 审批意见并执行整改
---

请读取 CLAUDE.md。

GPT review 文件路径：

$ARGUMENTS

本轮任务：
1. 读取 GPT review
2. 判断状态：APPROVED / NEEDS_FIX / BLOCKED
3. 如果 APPROVED：
   - 不修改代码
   - 更新 CURRENT_STATUS.md 和 NEXT_ACTIONS.md
   - 把 review 复制到 docs/gpt-advisor/reviews/applied/
4. 如果 NEEDS_FIX：
   - 只修 review 指定问题
   - 不扩大范围
   - 不修改禁止事项
   - 运行 npm run typecheck
   - 运行 npm run build
   - 运行 npm run pack:g2
   - 生成新的 test report
   - 生成新的 review bundle
5. 如果 BLOCKED：
   - 不修改代码
   - 输出阻塞原因和需要用户提供的信息

完成后输出：
1. 执行了哪些整改
2. 修改文件列表
3. 测试结果
4. EHPK 路径
5. SHA256
6. 新 bundle 路径
