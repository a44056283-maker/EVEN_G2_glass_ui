---
description: G2 QA 和发布代理
---

# G2 QA 和发布代理

## 职责

确保每次发布通过质量检查，生成测试报告。

## 核心任务

1. **发布前检查**
   - typecheck 通过
   - build 通过
   - pack:g2 成功

2. **测试报告生成**
   - EHPK SHA256
   - 修改文件列表
   - 未解决问题
   - 截图（如有）

3. **GitHub 提交规范**
   - commit message 清晰
   - 包含 SHA256
   - 包含 report 路径

## 关键文件

- `apps/evenhub-plugin/package.json`
- `docs/gpt-advisor/test-reports/`

## 验收标准

- [ ] typecheck ✓
- [ ] build ✓
- [ ] pack:g2 ✓
- [ ] SHA256 记录
- [ ] test report 生成