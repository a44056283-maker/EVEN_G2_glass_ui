#!/usr/bin/env python3
"""
每日子代理汇报生成器
由 crontab 调用: 0 10 * * * python3 /Users/luxiangnan/edict/scripts/daily_agent_report.py

每天 10:00 生成各部日报到各自 workspace/memory/tasks/ 目录
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path

TODAY = datetime.now().strftime("%Y-%m-%d")
REPORTS_DIR = Path.home() / ".openclaw"

# 各部门报告模板
TEMPLATES = {
    "shangshu": """# 尚书省日报 {date}

## 尚书 · 调度监督

### 调度状态
- V6.5 规则部署状态确认
- 各省部协调

### 今日工作
- [ ] 待填充

### 状态
- 状态：🟡 进行中
""",
    "hubu": """# 户部日报 {date}

## 户部 · 资金管理

### 账户状态
- 各账户余额：待查询

### ATR 实现
- 状态：待确认

### 待处理
- [ ] 待填充
""",
    "bingbu": """# 兵部日报 {date}

## 兵部 · 风控监控

### 风控状态
- 各账户风控状态：待确认

### 待处理
- [ ] 待填充
""",
    "xingbu": """# 刑部日报 {date}

## 刑部 · 合规审计

### 审计状态
- 规则一致性：待确认

### 待处理
- [ ] 待填充
""",
    "qintianjian": """# 钦天监日报 {date}

## 钦天监 · 舆情监控

### 舆情状态
- 当前舆情：待确认

### 监控状态
- monitor_sentiment.py 运行状态：待确认

### 待处理
- [ ] 待填充
""",
    "gongbu": """# 工部日报 {date}

## 工部 · 系统运维

### 系统状态
- 天下要闻：待确认
- 各机器人状态：待确认

### 今日工作
- [ ] 待填充

### 状态
- 状态：🟡 进行中
""",
    "tianlu": """# 中书省日报 {date}

## 中书省 · 太子审批

### 今日汇总
- 各部汇报汇总：待确认

### 审批状态
- 待处理审批：待确认

### 状态
- 状态：🟡 进行中
""",
}

def get_yesterday():
    from datetime import timedelta
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

def main():
    # 生成今日日报（供当日Dashboard展示）
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = get_yesterday()
    print(f"[汇报] 生成 {today} 各部日报...")

    for dept, template in TEMPLATES.items():
        workspace = REPORTS_DIR / f"workspace-{dept}" / "memory" / "tasks"
        workspace.mkdir(parents=True, exist_ok=True)
        # 优先写今日日报
        report_file = workspace / f"daily_report_{today}.md"

        content = template.format(date=today)
        report_file.write_text(content, encoding="utf-8")
        print(f"  ✅ {dept}: {report_file.name}")

    print(f"[汇报] 完成！共 {len(TEMPLATES)} 部")

if __name__ == "__main__":
    main()
