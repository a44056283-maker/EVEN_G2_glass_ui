#!/usr/bin/env python3
"""
External Signals Fetcher - Task 4
外部数据自动接入 - 资金费率/多空比/恐惧贪婪

使用方法:
    python3 external_signals_fetcher.py           # 获取最新数据
    python3 external_signals_fetcher.py --watch  # 持续监控(每5分钟)
"""

import json
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

SIGNALS_DIR = Path.home() / ".openclaw/workspace-tianlu/Knowledge/external_signals"
SIGNALS_FILE = SIGNALS_DIR / "external_signals.json"

# 警报阈值
THRESHOLDS = {
    "funding_rate_positive": 0.0001,   # 资金费率 > 0.01%
    "funding_rate_negative": -0.0001, # 资金费率 < -0.01%
    "long_short_ratio_high": 1.5,      # 多空比 > 1.5
    "long_short_ratio_low": 0.67,      # 多空比 < 0.67
    "fear_greed_extreme_fear": 25,      # 恐惧贪婪 < 25
    "fear_greed_extreme_greed": 75,     # 恐惧贪婪 > 75
}


def fetch_binance_funding_rate() -> Optional[Dict]:
    """获取Binance资金费率"""
    try:
        # Binance U本位合约资金费率
        url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            # 取前10个交易对的平均资金费率
            rates = [float(item["lastFundingRate"]) for item in data[:10] 
                    if item.get("lastFundingRate")]
            if rates:
                avg_rate = sum(rates) / len(rates)
                return {
                    "value": avg_rate,
                    "raw": data[:3],  # 前3个交易对详情
                    "exchange": "binance",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
    except Exception as e:
        print(f"   ⚠️ Binance资金费率获取失败: {e}")
    return None


def fetch_binance_long_short_ratio() -> Optional[Dict]:
    """获取Binance多空比"""
    try:
        # Binance 大户持仓比例
        url = "https://www.binance.com/futures/data/topLongShortPositionRatio"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data:
                latest = data[-1]  # 最新数据
                return {
                    "long_short_ratio": float(latest.get("longShortRate", 0)),
                    "symbol": latest.get("symbol", "BTC"),
                    "exchange": "binance",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
    except Exception as e:
        print(f"   ⚠️ Binance多空比获取失败: {e}")
    return None


def fetch_fear_greed() -> Optional[Dict]:
    """获取恐惧贪婪指数"""
    try:
        # Alternative.me API
        url = "https://api.alternative.me/fng/"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("data"):
                latest = data["data"][0]
                return {
                    "value": int(latest.get("value", 50)),
                    "classification": latest.get("value_classification", "Neutral"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
    except Exception as e:
        print(f"   ⚠️ 恐惧贪婪指数获取失败: {e}")
    return None


def generate_alerts(signals: Dict, thresholds: Dict) -> List[Dict]:
    """根据阈值生成警报"""
    alerts = []
    
    # 资金费率警报
    funding = signals.get("funding_rate", {})
    if funding:
        rate = funding.get("value", 0)
        if rate > thresholds["funding_rate_positive"]:
            alerts.append({
                "type": "funding_rate_high",
                "severity": "warning",
                "message": f"资金费率偏高({rate*100:.3f}%), 多头付息",
                "trigger": f"funding_rate > {thresholds['funding_rate_positive']}",
                "action": "触发场景12分析"
            })
        elif rate < thresholds["funding_rate_negative"]:
            alerts.append({
                "type": "funding_rate_low",
                "severity": "warning", 
                "message": f"资金费率偏低({rate*100:.3f}%), 空头付息",
                "trigger": f"funding_rate < {thresholds['funding_rate_negative']}",
                "action": "关注空头信号"
            })
    
    # 多空比警报
    ls_ratio = signals.get("long_short_ratio", {})
    if ls_ratio:
        ratio = ls_ratio.get("long_short_ratio", 1.0)
        if ratio > thresholds["long_short_ratio_high"]:
            alerts.append({
                "type": "long_short_overheated",
                "severity": "warning",
                "message": f"多空比过高({ratio:.2f}), 市场过热",
                "trigger": f"long_short_ratio > {thresholds['long_short_ratio_high']}",
                "action": "过热预警, 谨慎追多"
            })
        elif ratio < thresholds["long_short_ratio_low"]:
            alerts.append({
                "type": "long_short_oversold",
                "severity": "info",
                "message": f"多空比过低({ratio:.2f}), 市场恐慌",
                "trigger": f"long_short_ratio < {thresholds['long_short_ratio_low']}",
                "action": "极端恐慌机会, 关注反弹"
            })
    
    # 恐惧贪婪警报
    fg = signals.get("fear_greed", {})
    if fg:
        value = fg.get("value", 50)
        if value < thresholds["fear_greed_extreme_fear"]:
            alerts.append({
                "type": "fear_greed_extreme_fear",
                "severity": "critical",
                "message": f"极度恐慌({value}), 可能是买入机会",
                "trigger": f"fear_greed < {thresholds['fear_greed_extreme_fear']}",
                "action": "极端恐慌机会, 分批建仓"
            })
        elif value > thresholds["fear_greed_extreme_greed"]:
            alerts.append({
                "type": "fear_greed_extreme_greed",
                "severity": "warning",
                "message": f"极度贪婪({value}), 警惕回调",
                "trigger": f"fear_greed > {thresholds['fear_greed_extreme_greed']}",
                "action": "过热预警, 考虑止盈"
            })
    
    return alerts


def fetch_all_signals() -> Dict:
    """获取所有外部信号"""
    print("📡 正在获取外部信号...")
    
    signals = {
        "funding_rate": None,
        "long_short_ratio": None,
        "fear_greed": None,
        "alerts": [],
        "fetch_time": datetime.now(timezone.utc).isoformat()
    }
    
    # 获取各数据源
    fr = fetch_binance_funding_rate()
    if fr:
        signals["funding_rate"] = fr
        print(f"   ✅ 资金费率: {fr['value']*100:.4f}%")
    
    ls = fetch_binance_long_short_ratio()
    if ls:
        signals["long_short_ratio"] = ls
        print(f"   ✅ 多空比: {ls['long_short_ratio']:.2f}")
    
    fg = fetch_fear_greed()
    if fg:
        signals["fear_greed"] = fg
        print(f"   ✅ 恐惧贪婪: {fg['value']} ({fg['classification']})")
    
    # 生成警报
    signals["alerts"] = generate_alerts(signals, THRESHOLDS)
    
    if signals["alerts"]:
        print(f"\n🚨 警报 ({len(signals['alerts'])}条):")
        for alert in signals["alerts"]:
            print(f"   [{alert['severity'].upper()}] {alert['message']}")
    
    return signals


def save_signals(signals: Dict) -> None:
    """保存信号到文件"""
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    with open(SIGNALS_FILE, 'w') as f:
        json.dump(signals, f, ensure_ascii=False, indent=2)
    print(f"\n💾 已保存到: {SIGNALS_FILE}")


def load_signals() -> Dict:
    """加载最新信号"""
    if SIGNALS_FILE.exists():
        with open(SIGNALS_FILE) as f:
            return json.load(f)
    return {}


def show_signals(signals: Dict) -> None:
    """显示信号状态"""
    print(f"\n📊 外部信号状态")
    print(f"   文件: {SIGNALS_FILE}")
    print(f"   更新时间: {signals.get('fetch_time', '未知')}")
    
    fr = signals.get("funding_rate", {})
    if fr:
        print(f"   资金费率: {fr.get('value', 0)*100:.4f}%")
    
    ls = signals.get("long_short_ratio", {})
    if ls:
        print(f"   多空比: {ls.get('long_short_ratio', 0):.2f}")
    
    fg = signals.get("fear_greed", {})
    if fg:
        print(f"   恐惧贪婪: {fg.get('value', '?')} ({fg.get('classification', '')})")
    
    alerts = signals.get("alerts", [])
    if alerts:
        print(f"\n🚨 待处理警报 ({len(alerts)}条):")
        for alert in alerts:
            print(f"   [{alert['severity'].upper()}] {alert['message']}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="外部信号获取器")
    parser.add_argument("--watch", action="store_true", help="持续监控(每5分钟)")
    parser.add_argument("--status", action="store_true", help="查看当前状态")
    args = parser.parse_args()
    
    if args.status:
        signals = load_signals()
        show_signals(signals)
    elif args.watch:
        print("🔄 开始持续监控 (Ctrl+C 退出)")
        while True:
            signals = fetch_all_signals()
            save_signals(signals)
            print("\n⏰ 5分钟后再次获取...")
            time.sleep(300)
    else:
        signals = fetch_all_signals()
        save_signals(signals)
