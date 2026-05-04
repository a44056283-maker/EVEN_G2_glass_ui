#!/usr/bin/env python3
"""
兵部 · 量化交易统一监控脚本
整合：高波动监控 + 8x杠杆监控 + 28定律触发进度
"""

import sys
import time
from pathlib import Path

# 添加scripts目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from monitor_highvol import monitor_cycle as highvol_monitor, HIGH_VOL_COINS
from monitor_8x_leverage import monitor_8x as leverage_monitor
from monitor_pareto import monitor_pareto as pareto_monitor, init_db as pareto_init_db
from monitor_sentiment import monitor_sentiment as sentiment_monitor

WORKSPACE = Path(__file__).parent.parent
OUTPUT_FILE = WORKSPACE / 'data' / 'reports' / 'bingbu_unified_status.json'
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)


def run_unified():
    """执行统一监控，返回汇总报告"""
    import json
    from datetime import datetime

    report = {
        'generatedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'department': '兵部',
        'monitors': {}
    }

    # 1. 高波动监控
    print(">>> 高波动币种监控...")
    try:
        highvol_alerts = highvol_monitor()
        report['monitors']['highvol'] = {
            'status': 'OK' if not highvol_alerts else 'ALERT',
            'alertCount': len(highvol_alerts),
            'alerts': highvol_alerts
        }
    except Exception as e:
        report['monitors']['highvol'] = {'status': 'ERROR', 'error': str(e)}

    # 2. 8x杠杆监控
    print(">>> 8x杠杆监控...")
    try:
        leverage_alerts = leverage_monitor()
        report['monitors']['8x_leverage'] = {
            'status': 'OK' if not leverage_alerts else 'ALERT',
            'alertCount': len(leverage_alerts),
            'alerts': leverage_alerts
        }
    except Exception as e:
        report['monitors']['8x_leverage'] = {'status': 'ERROR', 'error': str(e)}

    # 3. 28定律监控
    print(">>> 28定律触发进度...")
    try:
        pareto_init_db()
        pareto_result = pareto_monitor()
        report['monitors']['pareto_28'] = {
            'status': pareto_result.get('level', 'UNKNOWN'),
            'triggered': pareto_result.get('triggered', False),
            'lossContribution': pareto_result.get('lossContribution', 0),
            'topLosers': pareto_result.get('topLosers', []),
            'message': pareto_result.get('message', '')
        }
    except Exception as e:
        report['monitors']['pareto_28'] = {'status': 'ERROR', 'error': str(e)}

    # 4. 舆情监控
    print(">>> 舆情信号监控...")
    try:
        sentiment_alerts = sentiment_monitor()
        # 判断舆情告警级别
        alert_levels = [a.get("level", "INFO") for a in sentiment_alerts]
        if "P0" in alert_levels or "ALERT" in alert_levels:
            sent_status = "ALERT"
        elif any("WARN" in l for l in alert_levels):
            sent_status = "WARN"
        else:
            sent_status = "OK"
        report['monitors']['sentiment'] = {
            'status': sent_status,
            'alertCount': len(sentiment_alerts),
            'alerts': sentiment_alerts
        }
    except Exception as e:
        report['monitors']['sentiment'] = {'status': 'ERROR', 'error': str(e)}

    # 汇总状态
    all_status = [m['status'] for m in report['monitors'].values()]
    if 'ERROR' in all_status:
        report['overallStatus'] = 'ERROR'
    elif any('ALERT' in s or s in ('P0', 'P1') for s in all_status):
        report['overallStatus'] = 'ALERT'
    else:
        report['overallStatus'] = 'OK'

    # 写入文件
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 统一监控完成，状态: {report['overallStatus']}")
    print(f"   报告: {OUTPUT_FILE}")

    return report


if __name__ == '__main__':
    run_unified()
