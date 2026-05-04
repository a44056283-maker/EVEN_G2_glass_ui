#!/usr/bin/env python3
"""
日报生成脚本
生成资金日报、成交日报、持仓日报、风控日报
执行时间: 每日 15:05
"""

import json
import os
import sys
from datetime import datetime, date
from typing import Dict, List, Any, Optional

WORKSPACE = "/Users/luxiangnan/.openclaw/workspace-hubu"
DATA_DIR = f"{WORKSPACE}/data"
REPORTS_DIR = f"{DATA_DIR}/reports/daily"


def generate_capital_report(trade_date: str, capital_data: Dict) -> Dict[str, Any]:
    """生成资金日报"""
    return {
        "reportType": "capital",
        "reportDate": trade_date,
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data": {
            "openingBalance": capital_data.get("openingBalance", 0),
            "closingBalance": capital_data.get("closingBalance", 0),
            "frozenMargin": capital_data.get("frozenMargin", 0),
            "availableCapital": capital_data.get("availableCapital", 0),
            "realizedPnl": capital_data.get("realizedPnl", 0),
            "unrealizedPnl": capital_data.get("unrealizedPnl", 0),
            "netValue": capital_data.get("netValue", 0),
            "alertLevel": capital_data.get("alertLevel", "OK")
        },
        "alerts": capital_data.get("alerts", [])
    }


def generate_trade_report(trade_date: str, trades: List[Dict]) -> Dict[str, Any]:
    """生成成交日报"""
    total_fees = sum(t.get("fee", 0) for t in trades)
    total_pnl = sum(t.get("profit", 0) for t in trades)
    
    return {
        "reportType": "trade",
        "reportDate": trade_date,
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "totalTrades": len(trades),
            "totalVolume": sum(t.get("volume", 0) for t in trades),
            "totalFees": round(total_fees, 2),
            "totalPnl": round(total_pnl, 2),
            "avgPnlPerTrade": round(total_pnl / len(trades), 2) if trades else 0
        },
        "trades": trades
    }


def generate_position_report(trade_date: str, positions: List[Dict]) -> Dict[str, Any]:
    """生成持仓日报"""
    total_unrealized_pnl = sum(p.get("unrealizedPnl", 0) for p in positions)
    
    return {
        "reportType": "position",
        "reportDate": trade_date,
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "totalPositions": len(positions),
            "totalUnrealizedPnl": round(total_unrealized_pnl, 2),
            "longPositions": len([p for p in positions if p.get("direction") == "LONG"]),
            "shortPositions": len([p for p in positions if p.get("direction") == "SHORT"])
        },
        "positions": positions
    }


def generate_risk_report(trade_date: str, risk_data: Dict) -> Dict[str, Any]:
    """生成风控日报"""
    return {
        "reportType": "risk",
        "reportDate": trade_date,
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "metrics": {
            "maxDrawdown": risk_data.get("maxDrawdown", 0),
            "dailyLoss": risk_data.get("dailyLoss", 0),
            "positionConcentration": risk_data.get("positionConcentration", 0),
            "leverage": risk_data.get("leverage", 1.0)
        },
        "breachEvents": risk_data.get("breachEvents", []),
        "warnings": risk_data.get("warnings", []),
        "alertLevel": risk_data.get("alertLevel", "OK")
    }


def save_reports(reports: Dict[str, Any], trade_date: str) -> bool:
    """保存所有报表到指定日期目录"""
    date_dir = f"{REPORTS_DIR}/{trade_date}"
    os.makedirs(date_dir, exist_ok=True)
    
    filenames = {
        "capital": "capital_report.json",
        "trade": "trade_report.json",
        "position": "position_report.json",
        "risk": "risk_report.json"
    }
    
    try:
        for report_type, content in reports.items():
            if report_type in filenames:
                filepath = f"{date_dir}/{filenames[report_type]}"
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(content, f, ensure_ascii=False, indent=2)
                print(f"✓ 已保存: {filepath}")
        return True
    except Exception as e:
        print(f"保存报表失败: {e}")
        return False


def load_demo_data(trade_date: str) -> Dict[str, Any]:
    """加载演示数据（实际使用时替换为真实数据源）"""
    return {
        "capital": {
            "openingBalance": 1000000,
            "closingBalance": 1012350,
            "frozenMargin": 150000,
            "availableCapital": 862350,
            "realizedPnl": 12350,
            "unrealizedPnl": -2500,
            "netValue": 1009850,
            "alertLevel": "OK",
            "alerts": []
        },
        "trades": [
            {"tradeId": "T20260320-001", "symbol": "BTCUSDT", "direction": "LONG", "volume": 0.5, "price": 65000, "profit": 1500, "fee": 32.5, "time": "09:30:15"},
            {"tradeId": "T20260320-002", "symbol": "ETHUSDT", "direction": "SHORT", "volume": 2.0, "price": 3500, "profit": -800, "fee": 14.0, "time": "10:15:22"},
            {"tradeId": "T20260320-003", "symbol": "BNBUSDT", "direction": "LONG", "volume": 10.0, "price": 420, "profit": 2200, "fee": 8.4, "time": "11:05:33"},
            {"tradeId": "T20260320-004", "symbol": "BTCUSDT", "direction": "SHORT", "volume": 0.3, "price": 65500, "profit": -500, "fee": 19.65, "time": "13:45:10"},
            {"tradeId": "T20260320-005", "symbol": "ADAUSDT", "direction": "LONG", "volume": 5000, "price": 0.58, "profit": 1800, "fee": 5.8, "time": "14:22:45"},
        ],
        "positions": [
            {"symbol": "BTCUSDT", "direction": "LONG", "volume": 0.5, "avgPrice": 64800, "currentPrice": 64500, "unrealizedPnl": -150, "margin": 50000},
            {"symbol": "BNBUSDT", "direction": "LONG", "volume": 10.0, "avgPrice": 415, "currentPrice": 418, "unrealizedPnl": 30, "margin": 50000},
            {"symbol": "ADAUSDT", "direction": "LONG", "volume": 5000, "avgPrice": 0.55, "currentPrice": 0.57, "unrealizedPnl": 100, "margin": 50000},
        ],
        "risk": {
            "maxDrawdown": 0.023,
            "dailyLoss": 0.005,
            "positionConcentration": 0.33,
            "leverage": 1.0,
            "breachEvents": [],
            "warnings": [],
            "alertLevel": "OK"
        }
    }


def main():
    # 获取交易日期，默认为今天
    trade_date = date.today().strftime("%Y-%m-%d")
    if len(sys.argv) > 1:
        trade_date = sys.argv[1]
    
    print(f"=== 日报生成器 ===")
    print(f"交易日期: {trade_date}")
    print()
    
    # 加载数据（演示模式使用内置数据）
    data = load_demo_data(trade_date)
    
    # 生成各类报表
    print("正在生成报表...")
    reports = {
        "capital": generate_capital_report(trade_date, data["capital"]),
        "trade": generate_trade_report(trade_date, data["trades"]),
        "position": generate_position_report(trade_date, data["positions"]),
        "risk": generate_risk_report(trade_date, data["risk"])
    }
    
    # 保存报表
    print()
    if save_reports(reports, trade_date):
        print(f"\n✓ 全部报表生成完成")
        print(f"报表目录: {REPORTS_DIR}/{trade_date}/")
    else:
        print(f"\n✗ 报表生成失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
