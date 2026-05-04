# 6小时定时进化巡检 2026-04-30 23:32:23

- 状态: ok_with_issues
- 三轮测试: 3 轮
- 机器人注册: 12 / 12
- 异常命令端口: []
- L5回放刷新: {'ok': True, 'latency_s': 0.741, 'error': None, 'materialized': 2000}
- 参数注册刷新: {'ok': True, 'latency_s': 0.031, 'error': None, 'count': 105, 'refreshed': True}

## 问题清单
- [medium] l5_market_intel: L5存在降级/单源覆盖: {'triple': 10, 'single': 2, 'dual': 3}
- [medium] l5_market_intel: 接口延时偏高: 18.643s
- [medium] l5_market_intel: L5存在降级/单源覆盖: {'triple': 10, 'single': 1, 'dual': 4}
- [medium] l5_market_intel: 接口延时偏高: 15.929s
- [medium] l5_market_intel: L5存在降级/单源覆盖: {'triple': 10, 'single': 1, 'dual': 4}

## 自动修复记录
- 9099 控制台健康
- 已尝试拉起缺失执行代理: [8081, 8082, 8083, 8084]

## 回测模块完工提醒
- 回测模块是当前L5主线任务。
- 2天稳定版: 修BT2轮询、结果目录、1970时间异常、9099展示。
- 3-5天闭环版: 打通L5样本、真实订单盈亏、滑点、提前平仓、V6.5候选池。
- 7-10天机构雏形版: walk-forward、分市场状态、订单生命周期、回测/实盘一致性审计。

JSON报告: `/Users/luxiangnan/Desktop/每日进化日志/定时巡检/scheduled_evolution_20260430_233357.json`
