#!/usr/bin/env python3
"""
胜率与盈亏比计算脚本
胜率 = 盈利交易次数 / 总交易次数
盈亏比 = 平均盈利金额 / 平均亏损金额
"""

import json
import sys
from datetime import datetime
from typing import List, Dict, Any
import statistics

def calc_winrate(trades: List[Dict]) -> Dict[str, Any]:
    """
    计算胜率
    
    Args:
        trades: 交易记录列表，每条记录需包含 profit 字段（盈利为正，亏损为负）
    
    Returns:
        包含胜率及相关统计数据的字典
    """
    if not trades:
        return {
            "status": "error",
            "message": "无交易数据",
            "winRate": None
        }
    
    total = len(trades)
    winners = [t for t in trades if t.get("profit", 0) > 0]
    losers = [t for t in trades if t.get("profit", 0) < 0]
    break_even = [t for t in trades if t.get("profit", 0) == 0]
    
    win_rate = len(winners) / total if total > 0 else 0
    lose_rate = len(losers) / total if total > 0 else 0
    break_even_rate = len(break_even) / total if total > 0 else 0
    
    return {
        "status": "success",
        "winRate": round(win_rate, 4),
        "loseRate": round(lose_rate, 4),
        "breakEvenRate": round(break_even_rate, 4),
        "totalTrades": total,
        "winningTrades": len(winners),
        "losingTrades": len(losers),
        "breakEvenTrades": len(break_even),
        "calculatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def calc_profit_loss_ratio(trades: List[Dict]) -> Dict[str, Any]:
    """
    计算盈亏比
    
    Args:
        trades: 交易记录列表
    
    Returns:
        包含盈亏比及相关统计数据的字典
    """
    if not trades:
        return {
            "status": "error",
            "message": "无交易数据",
            "profitLossRatio": None
        }
    
    winners = [t["profit"] for t in trades if t.get("profit", 0) > 0]
    losers = [t["profit"] for t in trades if t.get("profit", 0) < 0]
    
    if not winners:
        return {
            "status": "error",
            "message": "无盈利交易，无法计算盈亏比",
            "profitLossRatio": None
        }
    
    if not losers:
        return {
            "status": "error",
            "message": "无亏损交易，无法计算盈亏比",
            "profitLossRatio": None
        }
    
    avg_profit = statistics.mean(winners)
    avg_loss = abs(statistics.mean(losers))  # 取绝对值
    ratio = avg_profit / avg_loss if avg_loss > 0 else 0
    
    return {
        "status": "success",
        "profitLossRatio": round(ratio, 4),
        "avgProfit": round(avg_profit, 4),
        "avgLoss": round(avg_loss, 4),
        "winningTrades": len(winners),
        "losingTrades": len(losers),
        "calculatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def calc_winrate_and_plratio(trades: List[Dict]) -> Dict[str, Any]:
    """同时计算胜率和盈亏比"""
    winrate_result = calc_winrate(trades)
    plratio_result = calc_profit_loss_ratio(trades)
    
    combined = {
        "status": "success" if winrate_result["status"] == "success" and plratio_result["status"] == "success" else "partial",
        "winRate": winrate_result.get("winRate"),
        "profitLossRatio": plratio_result.get("profitLossRatio"),
        "details": {
            "winrate": winrate_result,
            "plratio": plratio_result
        },
        "calculatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    return combined


def load_trades(filepath: str) -> List[Dict]:
    """从JSON文件加载交易记录"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "trades" in data:
            return data["trades"]
        else:
            return []
    except FileNotFoundError:
        print(f"文件不存在: {filepath}")
        return []
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        return []


def main():
    if len(sys.argv) < 2:
        # 示例数据测试
        print("=== 胜率与盈亏比计算器 ===")
        test_trades = [
            {"tradeId": "T001", "profit": 1500},
            {"tradeId": "T002", "profit": -800},
            {"tradeId": "T003", "profit": 2200},
            {"tradeId": "T004", "profit": -500},
            {"tradeId": "T005", "profit": 1800},
            {"tradeId": "T006", "profit": -1200},
            {"tradeId": "T007", "profit": 900},
            {"tradeId": "T008", "profit": 0},  # 保本
        ]
        result = calc_winrate_and_plratio(test_trades)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    
    filepath = sys.argv[1]
    trades = load_trades(filepath)
    if trades:
        result = calc_winrate_and_plratio(trades)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
