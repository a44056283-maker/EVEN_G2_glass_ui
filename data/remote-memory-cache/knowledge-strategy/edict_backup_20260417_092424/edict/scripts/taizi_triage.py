#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
太子 · 舆情巡检脚本
定时任务：每日巡检 + 实时消息分拣
"""

import sys
import json
import os
import requests
from datetime import datetime

WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"
AGENTS_FILE = "/Users/luxiangnan/.openclaw/workspace-taizi/data/agents.json"
HUB_OUTPUT = "/Users/luxiangnan/freqtrade/scripts/tianlu_data_hub/data/hub_output.json"
LOG_FILE = "/Users/luxiangnan/edict/data/logs/taizi.log"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except:
        pass

def send_feishu(report: str):
    """发送巡检报告到飞书"""
    try:
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"📊 太子巡检 {datetime.now().strftime('%m-%d %H:%M')}"},
                    "template": "blue"
                },
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": report.replace("\n", "\n")}},
                    {"tag": "hr"},
                    {"tag": "div", "text": {"tag": "lark_md", "content": f"⏰ 巡检时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}}
                ]
            }
        }
        r = requests.post(WEBHOOK, json=card, timeout=10)
        log(f"飞书通知: {r.json().get('msg', 'unknown')}")
    except Exception as e:
        log(f"飞书通知失败: {e}")

def load_hub():
    """读取hub_output.json"""
    if os.path.exists(HUB_OUTPUT):
        try:
            with open(HUB_OUTPUT) as f:
                return json.load(f)
        except:
            return None
    return None

def load_agents():
    try:
        with open(AGENTS_FILE) as f:
            return json.load(f)
    except:
        return []

def check_bot_status(port):
    """检查Bot存活"""
    import requests
    try:
        r = requests.get(f"http://localhost:{port}/api/v1/ping", timeout=3)
        return r.json().get("status", "unknown") == "pong"
    except:
        return False

def patrol():
    """每日巡检"""
    hub = load_hub()
    agents = load_agents()
    
    report = f"📊 太子巡检报告 {datetime.now().strftime('%m-%d %H:%M')}\n"
    report += f"监控Agent数: {len(agents)}\n\n"
    
    # 检查钦天监
    if hub:
        hub_time = hub.get("hub_time", "N/A")
        hub_status = hub.get("status", "unknown")
        report += f"🔭 钦天监: {hub_status} ({hub_time})\n"
        
        # 检查各division状态
        divs = hub.get("divisions", {})
        for name, div in divs.items():
            # 优先用div的status，否则根据是否有数据判断
            status = div.get("status")
            if not status:
                # 根据是否有实际数据判断（检查常见数据字段）
                has_data = any(k in div for k in ['source_okx', 'source_gate', 'source', 'fear_greed', 'newsapi_articles', 'chain'])
                status = "OK" if has_data else "ERROR"
            elapsed = div.get("elapsed_s", 0)
            report += f"  ├{name}: {status} ({elapsed}s)\n"
        
        # Bot状态
        bots = hub.get("divisions", {}).get("market", {}).get("data", {}).get("bots", {})
        if bots:
            for port, info in bots.items():
                is_running = info.get("is_running", False)
                emoji = "✅" if is_running else "❌"
                report += f"  {emoji} Bot-{port}: {'运行中' if is_running else '已停止'}\n"
    else:
        report += "🔭 钦天监: 未连接\n"
    
    # Bot巡检
    for port in [9090, 9091, 9092, 9093, 9094, 9095, 9096, 9097]:
        if check_bot_status(port):
            report += f"✅ Bot-{port} 存活\n"
        else:
            report += f"❌ Bot-{port} 无响应\n"
    
    log(report)
    send_feishu(report)
    return report

def triage_message(msg):
    """实时消息分拣"""
    keywords = {
        "bug": ["错误", "崩溃", "失败", "error"],
        "urgent": ["紧急", "P0", "立即"],
        "trade": ["开仓", "平仓", "止损", "止盈"],
    }
    for dept, words in keywords.items():
        if any(w in msg for w in words):
            return dept
    return "general"

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "patrol":
        print(patrol())
    else:
        print("太子待命")
