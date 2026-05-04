#!/usr/bin/env python3
"""
尚书省 · 每日朝会简报生成脚本
自动生成三省六部工作日程并发送飞书通知
"""
import json
from datetime import datetime, timedelta

TEMPLATE = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌅 {date} 三省六部工作日程
太子令：按V3版本各司其职
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏛️ 中书省（策略研发）- 中书令
  09:00 参数优化检查 → param_optimizer.py
  10:30 策略回测分析 → param_optimizer.py
  14:00 信号分类审查 → taizi_triage.py
  15:30 策略调整提案
  17:00 ✅ 向尚书省汇报

🚪 门下省（审核监督）- 门下侍中
  09:00 自动审查 → auto_review.py
  11:00 提案审核
  14:00 风险评估 → auto_review.py
  16:00 审批决策
  17:30 ✅ 向尚书省汇报

📜 尚书省（统筹调度）- 尚书令
  08:00 派发早间任务
  10:00 配置同步 → sync_agent_config.py
  12:00 看板更新 → kanban_update.py
  18:00 汇总各部汇报
  20:00 👑 向太子汇报

💰 户部（财务）- 户部尚书
  08:00 每日交易摘要 → daily_trade_summary.py
  10:00 胜率统计 → calc_winrate.py
  11:00 夏普率计算 → calc_sharpe.py
  12:00 回撤分析 → calc_drawdown.py
  14:00 资金日报 → daily_report.py
  16:00 风险度评估
  17:00 ✅ 向尚书省汇报

📊 吏部（绩效）- 吏部尚书
  10:00 绩效统计
  14:00 目标追踪
  16:00 生成绩效报告
  17:00 ✅ 向尚书省汇报

⚔️ 兵部（风控）- 兵部尚书
  08:00 综合巡查 → bingbu_patrol.py
  09:00 下单审计 → bingbu_order_audit.py
  每5分钟 实时监控 → real_time_guard.py
  12:00 异常检查
  18:00 终盘巡检 → bingbu_patrol.py
  19:00 ✅ 向尚书省汇报

⚖️ 刑部（审计）- 刑部尚书
  09:00 交易审计 → audit_guard.py
  10:00 8倍杠杆检查 → monitor_8x_leverage.py
  14:00 审计报告 → audit_guard.py
  16:00 审批决策
  17:00 ✅ 向尚书省汇报

🛠️ 工部（运维）- 工部尚书
  08:00 系统巡检
  09:00 综合监控 → monitor_consolidated.py
  10:00 高波动监控 → monitor_highvol.py
  12:00 数据刷新 → refresh_live_data.py
  14:00 系统检查
  16:00 帕累托分析 → monitor_pareto.py
  18:00 ✅ 向尚书省汇报

🎭 礼部（外联）- 礼部尚书
  08:00 早间新闻 → fetch_morning_news.py
  09:00 交易播报 → send_trade_alert.py
  12:00 午间新闻 → fetch_morning_news.py
  14:00 情绪监控 → monitor_sentiment.py
  18:00 晚间播报 → send_trade_alert.py
  19:00 ✅ 向尚书省汇报

🔭 钦天监（数据）- 钦天监正
  10:00 数据分析
  14:00 市场研究
  16:00 竞品分析 → monitor_highvol.py
  18:00 数据归档
  19:00 ✅ 向尚书省汇报

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
各部酉时(18:00)前向尚书省汇报完成情况。
尚书省戌时(20:00)向太子汇总汇报。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

def main():
    today = datetime.now()
    chinese_date = f"{today.year}年{today.month}月{today.day}日"
    
    briefing = TEMPLATE.format(date=chinese_date)
    
    # 输出到文件
    output_path = "/Users/luxiangnan/edict/data/daily_briefing.md"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(briefing)
    
    print(f"✅ 朝会简报已生成: {output_path}")
    print(briefing)

if __name__ == "__main__":
    main()
