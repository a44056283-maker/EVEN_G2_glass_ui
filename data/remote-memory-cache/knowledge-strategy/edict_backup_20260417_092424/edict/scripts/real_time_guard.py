#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
兵部 · 实时风控（直接调用Bot API获取实际持仓）
"""

import json
import os
import requests
from datetime import datetime

BINGBU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"
LOG_FILE = "/Users/luxiangnan/edict/data/logs/bingbu_guard.log"

# Bot认证
BOT_AUTH = {
    9090: ("freqtrade", "freqtrade"),
    9091: ("freqtrade", "freqtrade"),
    9092: ("freqtrade", "freqtrade"),
    9093: ("admin", "Xy@06130822"),
    9094: ("admin", "Xy@06130822"),
    9095: ("admin", "Xy@06130822"),
    9096: ("admin", "Xy@06130822"),
    9097: ("admin", "Xy@06130822"),
}

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(f"[{ts}] [{level}] {msg}\n")
    except:
        pass

def send_alert(msg, urgency="normal"):
    emoji = "🔴" if urgency == "critical" else "🟠" if urgency == "high" else "🟡"
    try:
        requests.post(BINGBU_WEBHOOK, json={
            "msg_type": "text",
            "content": {"text": f"{emoji} {msg}"}
        }, timeout=5)
    except Exception as e:
        log(f"飞书发送失败: {e}", "ERROR")

def get_bot_positions(port):
    """直接从Bot API获取实际持仓"""
    auth = BOT_AUTH.get(port)
    if not auth:
        return []
    try:
        r = requests.get(f"http://localhost:{port}/api/v1/balance", auth=auth, timeout=5)
        if r.status_code == 200:
            data = r.json()
            positions = []
            for c in data.get("currencies", []):
                if c.get("is_position") and c.get("position", 0) > 0:
                    positions.append({
                        "pair": c.get("currency"),
                        "amount": c.get("position"),
                    })
            return positions
    except:
        pass
    return []

def get_bot_autopilot_status(port):
    """获取自动驾驶状态"""
    auth = BOT_AUTH.get(port)
    if not auth:
        return False
    try:
        r = requests.get(f"http://localhost:{port}/api/v1/autopilot/status", auth=auth, timeout=3)
        if r.status_code == 200:
            return r.json().get("enabled", False)
    except:
        pass
    return False

def run_guard():
    log("=== 兵部实时风控启动 ===")
    
    report_lines = []
    total_bots = 0
    total_positions = 0
    
    for port in [9090, 9091, 9092, 9093, 9094, 9095, 9096, 9097]:
        auth = BOT_AUTH.get(port)
        if not auth:
            continue
            
        # 检查bot是否在线
        try:
            r = requests.get(f"http://localhost:{port}/api/v1/ping", auth=auth, timeout=3)
            if r.status_code != 200:
                log(f"Bot-{port} 不在线", "WARN")
                continue
        except:
            log(f"Bot-{port} 连接失败", "ERROR")
            continue
        
        # 获取持仓
        positions = get_bot_positions(port)
        ap_enabled = get_bot_autopilot_status(port)
        
        if not positions and not ap_enabled:
            continue
            
        total_bots += 1
        total_positions += len(positions)
        
        ap_str = "🟢自动驾驶" if ap_enabled else "⚠️手动"
        report_lines.append(f"Bot-{port} {ap_str} {len(positions)}笔持仓:")
        
        for pos in positions:
            pair = pos.get("pair", "?").replace("BTC/USDT:USDT","BTC").replace("ETH/USDT:USDT","ETH").replace("SOL/USDT:USDT","SOL").replace("DOGE/USDT:USDT","DOGE")
            amount = pos.get("amount", 0)
            report_lines.append(f"  · {pair} {amount}")
    
    if report_lines:
        header = f"📊 兵部实时播报\n时间: {datetime.now().strftime('%H:%M:%S')}\n共{total_bots}个Bot {total_positions}笔持仓\n"
        report = header + "\n".join(report_lines)
        log(report)
        send_alert(report)
    else:
        log("无持仓或全部离线", "WARN")
    
    return {"status": "OK", "bots": total_bots, "positions": total_positions}

if __name__ == "__main__":
    result = run_guard()
    print(json.dumps(result, ensure_ascii=False, indent=2))
