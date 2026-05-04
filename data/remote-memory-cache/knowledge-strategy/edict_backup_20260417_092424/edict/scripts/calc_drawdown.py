#!/usr/bin/env python3
"""
最大回撤计算脚本
公式: max_drawdown = max(peak - trough) / peak
"""

import json
import sys
from datetime import datetime
from typing import List, Dict, Any
from typing import Optional

def calc_max_drawdown(equity_curve: List[Dict]) -> Dict[str, Any]:
    """
    计算最大回撤
    
    Args:
        equity_curve: 净值曲线列表，每条记录需包含 date 和 equity 字段
    
    Returns:
        包含最大回撤及相关数据的字典
    """
    if len(equity_curve) < 2:
        return {
            "status": "error",
            "message": "数据不足，无法计算最大回撤（需要至少2天数据）",
            "maxDrawdown": None
        }
    
    # 按日期排序
    sorted_curve = sorted(equity_curve, key=lambda x: x.get("date", ""))
    
    if not sorted_curve:
        return {"error": "无数据"}
    
    peak = sorted_curve[0]["equity"]
    max_drawdown = 0
    max_drawdown_pct = 0
    trough_date = None
    trough_equity = None
    peak_date = sorted_curve[0].get("date", "")
    
    drawdown_data = []
    
    for item in sorted_curve:
        equity = item["equity"]
        date = item.get("date", "")
        
        if equity > peak:
            peak = equity
            peak_date = date
        
        drawdown = peak - equity
        drawdown_pct = drawdown / peak if peak > 0 else 0
        
        drawdown_data.append({
            "date": date,
            "equity": equity,
            "peak": peak,
            "peakDate": peak_date,
            "drawdown": round(drawdown, 4),
            "drawdownPct": round(drawdown_pct, 4)
        })
        
        if drawdown_pct > max_drawdown_pct:
            max_drawdown = drawdown
            max_drawdown_pct = drawdown_pct
            trough_date = date
            trough_equity = equity
    
    return {
        "status": "success",
        "maxDrawdown": round(max_drawdown_pct, 4),
        "maxDrawdownAmount": round(max_drawdown, 4),
        "peakEquity": round(peak, 4),
        "troughEquity": round(trough_equity, 4) if trough_equity else None,
        "peakDate": peak_date,
        "troughDate": trough_date,
        "dataPoints": len(equity_curve),
        "drawdownData": drawdown_data[-10:] if len(drawdown_data) > 10 else drawdown_data,  # 最近10条
        "calculatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def load_equity_curve(filepath: str) -> List[Dict]:
    """从JSON文件加载净值曲线"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "equityCurve" in data:
            return data["equityCurve"]
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
        print("=== 最大回撤计算器 ===")
        test_curve = [
            {"date": "2026-03-10", "equity": 100000},
            {"date": "2026-03-11", "equity": 102000},
            {"date": "2026-03-12", "equity": 105000},
            {"date": "2026-03-13", "equity": 103000},
            {"date": "2026-03-14", "equity": 98000},   # 回撤
            {"date": "2026-03-15", "equity": 97000},   # 最大回撤点
            {"date": "2026-03-16", "equity": 99000},
            {"date": "2026-03-17", "equity": 106000},  # 创新高
            {"date": "2026-03-18", "equity": 108000},
        ]
        result = calc_max_drawdown(test_curve)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    
    filepath = sys.argv[1]
    curve = load_equity_curve(filepath)
    if curve:
        result = calc_max_drawdown(curve)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
