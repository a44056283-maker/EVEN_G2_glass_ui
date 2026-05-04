#!/usr/bin/env python3
"""
动态干预系统 - 数据存储模块
记录每次干预决策和执行结果
"""

import json
import os
from datetime import datetime
from pathlib import Path

# 数据目录
DATA_DIR = Path("/Users/luxiangnan/edict/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

INTERVENTION_FILE = DATA_DIR / "bingbu_intervention.json"
LOG_FILE = DATA_DIR / "bingbu_intervention.log"


def load_interventions() -> list:
    """加载干预记录"""
    if INTERVENTION_FILE.exists():
        try:
            with open(INTERVENTION_FILE) as f:
                return json.load(f)
        except:
            return []
    return []


def save_interventions(interventions: list):
    """保存干预记录"""
    with open(INTERVENTION_FILE, "w") as f:
        json.dump(interventions, f, ensure_ascii=False, indent=2)


def add_intervention(action: str, reason: str, sentiment_data: dict, result: str = "pending", targets: list = None):
    """添加一条干预记录

    targets格式: [{"bot": "9090", "pair": "BTC/USDT", "side": "LONG", "pnl": -120.5}, ...]
    """
    interventions = load_interventions()

    record = {
        "id": len(interventions) + 1,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,  # "freeze"/"force_exit"/"inject_long"/"inject_long_pair"/"inject_short_pair"/"force_exit_pair"/"emergency_exit_all"/"none"
        "reason": reason,
        "sentiment": {
            "direction": sentiment_data.get("sentiment_direction", "NEUTRAL"),
            "confidence": sentiment_data.get("sentiment_confidence", 0),
            "urgency": sentiment_data.get("sentiment_urgency", 0),
            "black_swan": sentiment_data.get("black_swan_alert", False),
            "fear_greed": sentiment_data.get("fear_greed_value", 50)
        },
        "targets": targets or [],   # 受影响的交易对
        "result": result  # "pending"/"success"/"failed"
    }
    
    interventions.insert(0, record)  # 最新在最前
    
    # 只保留最近100条
    interventions = interventions[:100]
    
    save_interventions(interventions)
    log_intervention(record)
    
    return record


def log_intervention(record: dict):
    """写入日志文件"""
    ts = record["timestamp"]
    action = record["action"]
    reason = record["reason"]
    result = record["result"]
    targets = record.get("targets") or []
    target_str = " | ".join([f"{t.get('bot','?')}:{t.get('pair',t)}" for t in targets]) if targets else ""

    log_line = f"[{ts}] {action.upper()} | {reason}"
    if target_str:
        log_line += f" | 影响: {target_str}"
    log_line += f" | 结果: {result}\n"

    with open(LOG_FILE, "a") as f:
        f.write(log_line)


def get_recent_interventions(limit: int = 10) -> list:
    """获取最近N条干预记录"""
    return load_interventions()[:limit]


def get_history_by_date(date_str: str) -> list:
    """获取指定日期的干预记录"""
    interventions = load_interventions()
    return [i for i in interventions if i["timestamp"].startswith(date_str)]


if __name__ == "__main__":
    # 测试
    print("=== 干预记录测试 ===")
    
    # 模拟添加一条记录
    test_data = {
        "sentiment_direction": "LONG",
        "sentiment_confidence": 75,
        "sentiment_urgency": 8,
        "black_swan_alert": True,
        "fear_greed_value": 25
    }
    
    record = add_intervention(
        action="inject_long",
        reason="做多信号: 信心75, 紧急度8, 黑天鹅触发",
        sentiment_data=test_data,
        result="success"
    )
    
    print(f"添加记录: {record['id']}")
    print(f"最近记录: {get_recent_interventions(5)}")
