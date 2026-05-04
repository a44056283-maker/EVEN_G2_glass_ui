#!/usr/bin/env python3
"""
兵部 · 28定律触发进度监控
基于帕累托原则：20%的仓位贡献80%的亏损（或盈亏）
触发条件：当最亏损的N个仓位占总亏损的比例超过阈值
"""

import json
import time
import logging
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict
import sqlite3

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [28定律] %(levelname)s %(message)s'
)
log = logging.getLogger('pareto')

WORKSPACE = Path(__file__).parent.parent
DATA_DIR = WORKSPACE / 'data'
DB_PATH = DATA_DIR / 'pareto.db'
ALERT_LOG = DATA_DIR / 'logs' / 'pareto_alerts.jsonl'
ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)

# ---------- 28定律阈值 ----------
TOP_LOSS_RATIO = 0.20    # 前20%的仓位
LOSS_CONTRIBUTION_THRESHOLD = 0.80  # 贡献80%的亏损
Pareto_TRIGGER_RATIO = 0.80  # 28定律触发比例（可调）

# ---------- 汇总报告路径 ----------
SUMMARY_FILE = DATA_DIR / 'reports' / 'pareto_summary.json'


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS position_snapshot (
        ts INTEGER, bot TEXT, exchange TEXT, symbol TEXT,
        direction TEXT, leverage REAL, margin REAL,
        unrealizedPnl REAL, entryPrice REAL, currentPrice REAL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS pareto_trigger_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts INTEGER, totalLoss REAL, triggeredPositions INTEGER,
        totalPositions INTEGER, lossContribution REAL, alertLevel TEXT
    )''')
    conn.commit()
    conn.close()


def get_db():
    return sqlite3.connect(DB_PATH)


def load_all_positions() -> List[dict]:
    """
    加载所有交易机器人的仓位数据
    数据源：各bot的仓位快照（demo使用模拟数据）
    实际对接：户部hubu的持仓数据 或 各交易所API
    """
    # TODO: 实际运行时从户部数据源或交易所API获取
    # positions = load_hubu_positions() 或直接从各bot API拉取

    # 模拟所有bot的仓位数据
    all_positions = [
        # bot 9090 (Gate.io)
        {'bot': '9090', 'exchange': 'Gate.io', 'symbol': 'BTCUSDT', 'direction': 'LONG', 'leverage': 1.0, 'margin': 65000, 'unrealizedPnl': -150},
        {'bot': '9090', 'exchange': 'Gate.io', 'symbol': 'ETHUSDT', 'direction': 'LONG', 'leverage': 1.0, 'margin': 35000, 'unrealizedPnl': 200},
        {'bot': '9090', 'exchange': 'Gate.io', 'symbol': 'SOLUSDT', 'direction': 'LONG', 'leverage': 2.0, 'margin': 5000, 'unrealizedPnl': -800},  # 主要亏损源
        # bot 9091 (Gate.io)
        {'bot': '9091', 'exchange': 'Gate.io', 'symbol': 'BNBUSDT', 'direction': 'LONG', 'leverage': 1.0, 'margin': 20000, 'unrealizedPnl': 300},
        {'bot': '9091', 'exchange': 'Gate.io', 'symbol': 'ADAUSDT', 'direction': 'LONG', 'leverage': 3.0, 'margin': 5000, 'unrealizedPnl': -1200},  # 主要亏损源
        {'bot': '9091', 'exchange': 'Gate.io', 'symbol': 'XRPUSDT', 'direction': 'SHORT', 'leverage': 2.0, 'margin': 8000, 'unrealizedPnl': 150},
        # bot 9092 (Gate.io 8x)
        {'bot': '9092', 'exchange': 'Gate.io', 'symbol': 'DOGE-USDT', 'direction': 'LONG', 'leverage': 8.0, 'margin': 875, 'unrealizedPnl': -312.5},  # 主要亏损源
        {'bot': '9092', 'exchange': 'Gate.io', 'symbol': 'SOL-USDT', 'direction': 'LONG', 'leverage': 8.0, 'margin': 8437.5, 'unrealizedPnl': 187.5},
        # bot 9093 (OKX)
        {'bot': '9093', 'exchange': 'OKX', 'symbol': 'DOGE-USDT', 'direction': 'SHORT', 'leverage': 5.0, 'margin': 2000, 'unrealizedPnl': -500},  # 主要亏损源
        {'bot': '9093', 'exchange': 'OKX', 'symbol': 'ETH-USDT', 'direction': 'LONG', 'leverage': 3.0, 'margin': 3000, 'unrealizedPnl': 100},
    ]
    return all_positions


def analyze_pareto(positions: List[dict]) -> dict:
    """
    分析28定律：
    - 按亏损额排序（前20%的仓位）
    - 计算这些仓位占总亏损的比例
    - 若超过80%，触发28定律告警
    """
    ts = int(time.time())

    # 过滤有亏损的仓位
    losing_positions = [p for p in positions if p['unrealizedPnl'] < 0]
    winning_positions = [p for p in positions if p['unrealizedPnl'] >= 0]

    if not losing_positions:
        log.info("无亏损仓位，28定律分析跳过")
        return {'triggered': False, 'message': '无亏损仓位'}

    # 按亏损额排序（亏得最多的排前面）
    losing_sorted = sorted(losing_positions, key=lambda x: x['unrealizedPnl'])

    total_loss = sum(p['unrealizedPnl'] for p in losing_positions)
    total_loss_abs = abs(total_loss)

    # 计算前20%的仓位数
    top_n = max(1, int(len(losing_sorted) * TOP_LOSS_RATIO))

    # 前20%亏损仓位的亏损总额
    top_loss = sum(p['unrealizedPnl'] for p in losing_sorted[:top_n])
    top_loss_abs = abs(top_loss)

    # 计算亏损贡献比
    loss_contribution = top_loss_abs / total_loss_abs if total_loss_abs > 0 else 0

    # 判断是否触发
    triggered = loss_contribution >= Pareto_TRIGGER_RATIO

    result = {
        'ts': ts,
        'triggered': triggered,
        'totalPositions': len(positions),
        'losingPositions': len(losing_positions),
        'topPositions': top_n,
        'totalLoss': round(total_loss, 2),
        'topLoss': round(top_loss, 2),
        'lossContribution': round(loss_contribution, 4),
        'topLosers': [p['symbol'] for p in losing_sorted[:top_n]],
        'triggerThreshold': Pareto_TRIGGER_RATIO,
        'level': None,
        'message': ''
    }

    if triggered:
        result['level'] = 'P0'
        result['message'] = (f'🚨 28定律触发！前{top_n}个仓位({TOP_LOSS_RATIO:.0%})'
                             f'贡献了{loss_contribution:.0%}的总亏损(${top_loss:.2f}/总亏损${total_loss_abs:.2f})')
        log.warning(result['message'])
    elif loss_contribution >= 0.60:  # 接近触发
        result['level'] = 'P2'
        result['message'] = (f'🟠 28定律预警：前{top_n}个仓位贡献{loss_contribution:.0%}亏损，'
                             f'接近{Pareto_TRIGGER_RATIO:.0%}触发线')
        log.warning(result['message'])
    else:
        result['level'] = 'OK'
        result['message'] = f'✅ 28定律正常：前{top_n}仓位贡献{loss_contribution:.0%}亏损，在安全范围'
        log.info(result['message'])

    return result


def save_snapshot(positions: List[dict]):
    """保存仓位快照到数据库"""
    conn = get_db()
    ts = int(time.time())
    for p in positions:
        conn.execute(
            '''INSERT INTO position_snapshot
               (ts, bot, exchange, symbol, direction, leverage, margin, unrealizedPnl, entryPrice, currentPrice)
               VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (ts, p['bot'], p['exchange'], p['symbol'], p['direction'],
             p.get('leverage', 1.0), p['margin'], p['unrealizedPnl'],
             p.get('entryPrice', 0), p.get('currentPrice', 0))
        )
    conn.commit()
    conn.close()


def save_trigger_log(result: dict):
    """保存28定律触发日志"""
    conn = get_db()
    conn.execute(
        '''INSERT INTO pareto_trigger_log
           (ts, totalLoss, triggeredPositions, totalPositions, lossContribution, alertLevel)
           VALUES (?,?,?,?,?,?)''',
        (result['ts'], result['totalLoss'], result['topPositions'],
         result['totalPositions'], result['lossContribution'], result['level'])
    )
    conn.commit()
    conn.close()

    # 追加到告警日志
    with open(ALERT_LOG, 'a') as f:
        f.write(json.dumps(result, ensure_ascii=False) + '\n')


def save_summary(result: dict):
    """保存最新汇总"""
    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_FILE, 'w') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def monitor_pareto():
    """执行28定律监控"""
    log.info("=== 28定律监控开始 ===")
    positions = load_all_positions()
    save_snapshot(positions)

    result = analyze_pareto(positions)
    save_trigger_log(result)
    save_summary(result)

    log.info(f"=== 28定律监控完成: {result['message']} ===")
    return result


def monitor_loop(interval: int = 60):
    while True:
        monitor_pareto()
        time.sleep(interval)


if __name__ == '__main__':
    init_db()
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'loop':
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 60
        log.info(f"启动28定律循环监控，每{interval}秒")
        monitor_loop(interval)
    else:
        monitor_pareto()
