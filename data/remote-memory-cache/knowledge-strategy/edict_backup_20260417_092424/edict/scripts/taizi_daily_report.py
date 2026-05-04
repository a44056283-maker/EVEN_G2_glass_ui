#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
太子（天禄）· 真实数据采集脚本
从交易所和机器人API获取真实的余额、盈亏、胜率等信息
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
import requests

# 配置
EDICT_DATA = Path("/Users/luxiangnan/edict/data")
REPORTS_DIR = EDICT_DATA / "reports" / "daily"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# 飞书通知webhook
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"

# 兵部API（7891端口）
BINGBU_API = "http://127.0.0.1:7891"


def fetch_balances():
    """获取各Bot真实账户余额"""
    try:
        r = requests.get(f"{BINGBU_API}/api/bingbu/balances", timeout=10)
        data = r.json()
        return data.get("balances", []), data.get("total", 0)
    except Exception as e:
        print(f"[太子] 获取余额失败: {e}")
        return [], 0


def fetch_positions():
    """获取各Bot实时持仓和盈亏"""
    try:
        r = requests.get(f"{BINGBU_API}/api/bingbu/positions", timeout=10)
        data = r.json()
        return data.get("positions", [])
    except Exception as e:
        print(f"[太子] 获取持仓失败: {e}")
        return []


def fetch_live_status():
    """获取Bot在线状态"""
    try:
        r = requests.get(f"{BINGBU_API}/api/live-status", timeout=10)
        return r.json()
    except Exception as e:
        print(f"[太子] 获取状态失败: {e}")
        return {}


def calculate_drawdown(current_total: float) -> dict:
    """从历史日报计算最大回撤"""
    import os
    from datetime import datetime, timedelta

    equity_curve = []
    # 读取最近30天的日报
    reports_dir = REPORTS_DIR
    today = datetime.now()

    for i in range(30):
        d = today - timedelta(days=i)
        fname = reports_dir / f"real_report_{d.strftime('%Y%m%d')}.json"
        if fname.exists():
            try:
                with open(fname) as f:
                    r = json.load(f)
                total = r.get("metrics", {}).get("total_balance", 0)
                if total > 0:
                    equity_curve.append({"date": d.strftime("%Y-%m-%d"), "equity": total})
            except Exception:
                pass

    # 加入今日数据
    equity_curve.append({"date": today.strftime("%Y-%m-%d"), "equity": current_total})

    if len(equity_curve) < 2:
        return {"drawdown": None, "drawdown_pct": "—", "data_points": len(equity_curve)}

    # 计算max drawdown
    sorted_curve = sorted(equity_curve, key=lambda x: x["date"])
    peak = sorted_curve[0]["equity"]
    max_dd = 0
    for item in sorted_curve:
        if item["equity"] > peak:
            peak = item["equity"]
        dd_pct = (peak - item["equity"]) / peak if peak > 0 else 0
        if dd_pct > max_dd:
            max_dd = dd_pct

    return {
        "drawdown": round(max_dd, 4),
        "drawdown_pct": f"{max_dd:.2%}",
        "data_points": len(sorted_curve),
        "equity_curve": sorted_curve[-10:]  # 最近10条
    }


def calculate_metrics(positions, balances, current_total):
    """计算真实绩效指标"""
    total_pnl = 0
    total_balance = sum(b.get("balance", 0) for b in balances)
    winning_trades = 0
    total_trades = 0
    
    # 计算浮动盈亏
    for pos in positions:
        unrealized = pos.get("unrealized_pnl", 0)
        total_pnl += unrealized
        
        # 统计交易笔数（按持仓币种计算）
        if pos.get("amount", 0) > 0:
            total_trades += 1
            if unrealized > 0:
                winning_trades += 1
    
    # 计算胜率
    win_rate = round(winning_trades / total_trades * 100, 2) if total_trades > 0 else 0

    # 计算回撤
    dd_info = calculate_drawdown(total_balance)
    
    return {
        "total_balance": total_balance,
        "unrealized_pnl": round(total_pnl, 2),
        "win_rate": win_rate,
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "drawdown": dd_info.get("drawdown"),
        "drawdown_pct": dd_info.get("drawdown_pct", "—"),
    }


def send_daily_report(metrics, balances, positions, status):
    """发送真实日报到飞书群"""
    bots_text = ""
    for cfg in status.get("bots", []):
        label = cfg.get("label", "?")
        online = cfg.get("online", False)
        emoji = "✅" if online else "❌"
        bots_text += f"{emoji} {label} "
    
    positions_text = ""
    for pos in positions[:10]:  # 只显示前10个持仓
        pair = pos.get("id", "?")
        pnl = pos.get("unrealized_pnl", 0)
        emoji = "🟢" if pnl >= 0 else "🔴"
        positions_text += f"{emoji} {pair}: {pnl}\n"
    
    msg = f"""📊 **【太子】真实日报 · {datetime.now().strftime('%Y-%m-%d')}**
━━━━━━━━━━━━━━━━━━━━

💰 **账户总余额:** ${metrics['total_balance']:,.2f}
📈 **浮动盈亏:** ${metrics['unrealized_pnl']:,.2f}
🎯 **胜率:** {metrics['win_rate']}%
📊 **持仓数:** {metrics['total_trades']}

━━━━━━━━━━━━━━━━━━━━

🤖 **Bot状态:**
{bots_text}

📊 **实时持仓（前10）:**
{positions_text or '  无持仓'}

━━━━━━━━━━━━━━━━━━━━

*数据来源：交易所API实时采集*"""

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"📊 太子真实日报 · {datetime.now().strftime('%m/%d')}"},
                "template": "blue"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": msg}}
            ]
        }
    }
    
    try:
        requests.post(FEISHU_WEBHOOK, json=card, timeout=10)
        print("[太子] 日报已发送")
    except Exception as e:
        print(f"[太子] 发送失败: {e}")


def main():
    print(f"[太子] {datetime.now().strftime('%H:%M:%S')} 开始采集真实数据...")
    
    # 1. 获取余额
    balances, total = fetch_balances()
    print(f"  余额: ${total:,.2f}")
    
    # 2. 获取持仓
    positions = fetch_positions()
    print(f"  持仓: {len(positions)}个")
    
    # 3. 获取状态
    status = fetch_live_status()
    
    # 4. 计算指标
    # 用当前余额作为临时total，后面calculate_metrics会重新计算
    temp_total = sum(b.get("balance", 0) for b in balances)
    metrics = calculate_metrics(positions, balances, temp_total)
    print(f"  胜率: {metrics['win_rate']}%")
    if metrics.get('drawdown') is not None:
        print(f"  回撤: {metrics['drawdown_pct']}")
    
    # 5. 保存日报
    report = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "metrics": metrics,
        "balances": balances,
        "positions_count": len(positions),
        "status": status
    }
    
    report_file = REPORTS_DIR / f"real_report_{datetime.now().strftime('%Y%m%d')}.json"
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"  已保存: {report_file}")
    
    # 6. 发送飞书
    send_daily_report(metrics, balances, positions, status)
    
    return report


if __name__ == "__main__":
    main()
