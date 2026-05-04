#!/usr/bin/env python3
"""
夏普比率计算脚本
计算公式: Sharpe = (平均日收益 - 无风险利率) / 日收益标准差
"""

import json
import sys
from datetime import datetime
from typing import List, Dict, Any
import statistics

def calc_sharpe_ratio(daily_returns: List[float], risk_free_rate: float = 0.03, trading_days: int = 250) -> Dict[str, Any]:
    """
    计算夏普比率
    
    Args:
        daily_returns: 每日收益率列表
        risk_free_rate: 年化无风险利率，默认 3%
        trading_days: 年化交易日天数，默认 250
    
    Returns:
        包含夏普比率及相关统计数据的字典
    """
    if len(daily_returns) < 2:
        return {
            "status": "error",
            "message": "数据不足，无法计算夏普比率（需要至少2天数据）",
            "sharpeRatio": None
        }
    
    avg_daily_return = statistics.mean(daily_returns)
    std_daily_return = statistics.stdev(daily_returns)
    
    if std_daily_return == 0:
        return {
            "status": "error",
            "message": "标准差为0，无法计算夏普比率",
            "sharpeRatio": None
        }
    
    daily_risk_free = risk_free_rate / trading_days
    excess_return = avg_daily_return - daily_risk_free
    sharpe = excess_return / std_daily_return
    
    # 年化夏普比率
    annualized_sharpe = sharpe * (trading_days ** 0.5)
    
    return {
        "status": "success",
        "sharpeRatio": round(annualized_sharpe, 4),
        "dailySharpe": round(sharpe, 6),
        "avgDailyReturn": round(avg_daily_return, 6),
        "stdDailyReturn": round(std_daily_return, 6),
        "dailyRiskFree": round(daily_risk_free, 6),
        "excessReturn": round(excess_return, 6),
        "dataDays": len(daily_returns),
        "riskFreeRate": risk_free_rate,
        "tradingDays": trading_days,
        "calculatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def load_daily_returns(filepath: str) -> List[float]:
    """从JSON文件加载每日收益率"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [d["dailyReturn"] for d in data]
    except FileNotFoundError:
        print(f"文件不存在: {filepath}")
        return []
    except (KeyError, json.JSONDecodeError) as e:
        print(f"数据格式错误: {e}")
        return []


def main():
    if len(sys.argv) < 2:
        # 示例数据测试
        print("=== 夏普比率计算器 ===")
        test_returns = [0.01, -0.005, 0.023, -0.012, 0.018, 0.007, -0.003, 0.015, -0.008, 0.012]
        result = calc_sharpe_ratio(test_returns)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    
    filepath = sys.argv[1]
    returns = load_daily_returns(filepath)
    if returns:
        result = calc_sharpe_ratio(returns)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
