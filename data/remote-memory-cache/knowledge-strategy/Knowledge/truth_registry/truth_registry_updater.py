#!/usr/bin/env python3
"""
Truth Registry Updater - Task 3
交易结果反馈闭环 - 验证知识库规则的有效性

使用方法:
    python3 truth_registry_updater.py              # 更新今日交易结果
    python3 truth_registry_updater.py --dry-run   # 模拟运行
    python3 truth_registry_updater.py --status    # 查看当前状态
"""

import json
import os
import sys
import requests
import base64
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

TRUTH_REGISTRY_DIR = Path.home() / ".openclaw/workspace-tianlu/Knowledge/truth_registry"
TRUTH_REGISTRY_FILE = TRUTH_REGISTRY_DIR / "truth_registry.json"

# 机器人API配置
BOT_PORTS = {
    9090: ("gate", "freqtrade:freqtrade"),
    9091: ("gate", "freqtrade:freqtrade"),
    9092: ("gate", "freqtrade:freqtrade"),
    9093: ("okx", "admin:Xy@06130822"),
    9094: ("okx", "admin:Xy@06130822"),
    9095: ("okx", "admin:Xy@06130822"),
    9096: ("okx", "admin:Xy@06130822"),
    9097: ("okx", "admin:Xy@06130822"),
}


def load_registry() -> Dict:
    """加载现有注册表"""
    TRUTH_REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    if TRUTH_REGISTRY_FILE.exists():
        with open(TRUTH_REGISTRY_FILE) as f:
            return json.load(f)
    return {"validated": [], "invalidated": [], "last_updated": None}


def save_registry(registry: Dict) -> None:
    """保存注册表"""
    registry["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(TRUTH_REGISTRY_FILE, 'w') as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


def get_bot_trades(port: int, auth: str) -> List[Dict]:
    """获取机器人近期交易"""
    try:
        auth_header = 'Basic ' + base64.b64encode(auth.encode()).decode()
        r = requests.get(f'http://localhost:{port}/api/v1/status', 
                        headers={'Authorization': auth_header}, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"   ⚠️ 端口 {port} 连接失败: {e}")
    return []


def extract_trade_result(trade: Dict, bot_name: str) -> Optional[Dict]:
    """从交易中提取结果"""
    # 计算盈亏
    try:
        profit_ratio = trade.get("profit_ratio", 0) or 0
        stake = trade.get("stake_amount", 0) or 0
        profit_abs = profit_ratio * stake
        
        return {
            "trade_id": trade.get("trade_id", "unknown"),
            "bot": bot_name,
            "pair": trade.get("pair", "UNKNOWN"),
            "direction": "做多" if trade.get("is_short", False) else "做空",
            "entry_price": trade.get("open_rate", 0),
            "exit_price": trade.get("close_rate", None),
            "profit_ratio": profit_ratio,
            "profit_abs": profit_abs,
            "open_time": trade.get("open_date", None),
            "close_time": trade.get("close_date", None),
            "is_winning": profit_ratio > 0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        print(f"   ⚠️ 解析交易失败: {e}")
        return None


def update_from_trades(registry: Dict, dry_run: bool = False) -> Dict:
    """从机器人API更新交易结果"""
    new_validated = []
    new_invalidated = []
    
    for port, (exchange, auth) in BOT_PORTS.items():
        bot_name = f"bot_{port}"
        print(f"📊 查询 {bot_name} ({exchange})...")
        
        trades = get_bot_trades(port, auth)
        
        if not trades:
            print(f"   无持仓")
            continue
        
        for trade in trades:
            result = extract_trade_result(trade, bot_name)
            if result:
                print(f"   {result['pair']} {result['direction']} "
                      f"{'+' if result['is_winning'] else ''}{result['profit_ratio']*100:.2f}%")
                
                entry = {
                    "rule": f"{result['pair']} {result['direction']}",
                    "from": f"{result['bot']} @ {result['open_time']}",
                    "result": f"{'盈利' if result['is_winning'] else '亏损'}"
                             f"{'+' if result['profit_abs'] >= 0 else ''}{result['profit_abs']:.2f}U",
                    "profit_ratio": result['profit_ratio'],
                    "profit_abs": result['profit_abs'],
                    "pair": result['pair'],
                    "direction": result['direction'],
                    "timestamp": result['timestamp'],
                    "trade_id": result['trade_id']
                }
                
                # 根据盈亏分类
                if result['is_winning']:
                    new_validated.append(entry)
                else:
                    new_invalidated.append(entry)
    
    if dry_run:
        print(f"\n🔍 Dry Run - 不会写入文件")
        print(f"   将添加 {len(new_validated)} 条validated, {len(new_invalidated)} 条invalidated")
        return registry
    
    # 更新注册表
    registry["validated"].extend(new_validated)
    registry["invalidated"].extend(new_invalidated)
    
    # 去重: 相同trade_id不重复
    seen_validated = set()
    seen_invalidated = set()
    registry["validated"] = [
        v for v in registry["validated"] 
        if v["trade_id"] not in seen_validated and not seen_validated.add(v["trade_id"])
    ]
    registry["invalidated"] = [
        v for v in registry["invalidated"] 
        if v["trade_id"] not in seen_invalidated and not seen_invalidated.add(v["trade_id"])
    ]
    
    save_registry(registry)
    
    # 输出统计
    total_validated = len(registry["validated"])
    total_invalidated = len(registry["invalidated"])
    total = total_validated + total_invalidated
    win_rate = total_validated / total * 100 if total > 0 else 0
    
    print(f"\n📈 Truth Registry 更新完成")
    print(f"   总交易: {total}")
    print(f"   盈利(validated): {total_validated}")
    print(f"   亏损(invalidated): {total_invalidated}")
    print(f"   胜率: {win_rate:.1f}%")
    
    return registry


def show_status(registry: Dict) -> None:
    """显示状态"""
    validated = registry.get("validated", [])
    invalidated = registry.get("invalidated", [])
    total = len(validated) + len(invalidated)
    win_rate = len(validated) / total * 100 if total > 0 else 0
    
    print(f"\n📊 Truth Registry 状态")
    print(f"   文件: {TRUTH_REGISTRY_FILE}")
    print(f"   总记录: {total}")
    print(f"   盈利规则: {len(validated)}")
    print(f"   亏损规则: {len(invalidated)}")
    print(f"   胜率: {win_rate:.1f}%")
    print(f"   最后更新: {registry.get('last_updated', '从未')}")
    
    if validated:
        print(f"\n🟢 最近盈利规则:")
        for v in validated[-3:]:
            print(f"   - {v['rule']}: {v['result']}")
    
    if invalidated:
        print(f"\n🔴 最近亏损规则:")
        for v in invalidated[-3:]:
            print(f"   - {v['rule']}: {v['result']}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Truth Registry 更新器")
    parser.add_argument("--dry-run", action="store_true", help="模拟运行")
    parser.add_argument("--status", action="store_true", help="查看状态")
    args = parser.parse_args()
    
    registry = load_registry()
    
    if args.status:
        show_status(registry)
    elif args.dry_run:
        update_from_trades(registry, dry_run=True)
    else:
        update_from_trades(registry)
