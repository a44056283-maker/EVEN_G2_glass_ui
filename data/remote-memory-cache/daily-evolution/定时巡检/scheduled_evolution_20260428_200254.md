# 6小时定时进化巡检 2026-04-28 20:00:27

- 状态: ok_with_issues
- 三轮测试: 3 轮
- 机器人注册: 12 / 12
- 异常命令端口: []
- L5回放刷新: {'ok': False, 'latency_s': 0.25, 'error': 'HTTP Error 500: INTERNAL SERVER ERROR'}
- 参数注册刷新: {'ok': True, 'latency_s': 0.012, 'error': None, 'count': 104, 'refreshed': True}

## 问题清单
- [medium] replay_samples: HTTP Error 500: INTERNAL SERVER ERROR
- [medium] bt2_run: Command '['/Library/Frameworks/Python.framework/Versions/3.14/Resources/Python.app/Contents/MacOS/Python', '/Users/luxiangnan/freqtrade_console/bt_tools/backtest_core/run_backtest.py', '--pair', 'BTC/USDT', '--exchange', 'gate', '--output', '/Users/luxiangnan/freqtrade_console/bt_tools/backtest_core/reports/bt_dc6b8234.json', '--days', '30']' timed out after 90 seconds

## 自动修复记录
- 9099 控制台健康
- 已尝试拉起缺失执行代理: [8081, 8082, 8083, 8084, 9090, 9091, 9092, 9093, 9094, 9095, 9096, 9097]

## 回测模块完工提醒
- 回测模块是当前L5主线任务。
- 2天稳定版: 修BT2轮询、结果目录、1970时间异常、9099展示。
- 3-5天闭环版: 打通L5样本、真实订单盈亏、滑点、提前平仓、V6.5候选池。
- 7-10天机构雏形版: walk-forward、分市场状态、订单生命周期、回测/实盘一致性审计。

JSON报告: `/Users/luxiangnan/Desktop/每日进化日志/定时巡检/scheduled_evolution_20260428_200254.json`
