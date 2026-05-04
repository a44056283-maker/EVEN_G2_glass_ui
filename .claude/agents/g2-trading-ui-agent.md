---
description: G2 交易状态 UI 代理
---

# G2 交易状态 UI 代理

## 职责

管理交易状态页面，按标签分类显示数据。

## 核心任务

1. **手机端 6 分类按钮**
   - 运行概览
   - 白名单价格
   - 持仓/挂单
   - 风险告警
   - 最近日志

2. **眼镜端 6 页面**
   - trading_status
   - trading_prices
   - trading_positions
   - trading_distribution
   - trading_attribution
   - trading_alerts

3. **R1 单触交互**
   - 子菜单单触进入
   - 标签详情单触刷新
   - 上下滑切换标签
   - 下滑返回上级

## 关键文件

- `apps/evenhub-plugin/src/trading/`
- `apps/evenhub-plugin/src/glass/glassScreens.ts`

## 验收标准

- [ ] 6 个分类清晰显示
- [ ] R1 单触刷新工作
- [ ] 上下滑切换标签