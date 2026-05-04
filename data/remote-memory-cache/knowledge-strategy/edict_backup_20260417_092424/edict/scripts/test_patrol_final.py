#!/usr/bin/env python3
"""测试巡查卡片原生按钮效果"""
import sys, json, urllib.request
sys.path.insert(0, "/Users/luxiangnan/edict/scripts")
from bingbu_patrol import build_card

WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"

positions = {
    'count': 2, 'total_pnl': 88.5,
    'positions': [
        {'pair': 'BTC/USDT:USDT', 'side': 'LONG', 'amount': '0.5', 'leverage': '10',
         'current_price': '67000', 'exchange': 'Gate.io', 'unrealized_pnl': 55.2},
        {'pair': 'ETH/USDT:USDT', 'side': 'SHORT', 'amount': '2', 'leverage': '5',
         'current_price': '3200', 'exchange': 'OKX', 'unrealized_pnl': 33.3},
    ]
}
sentiment = {'sentiment_signal': 'NEUTRAL', 'sentiment_confidence': 65,
             'fear_greed_value': 55, 'fear_greed_label': 'Neutral'}
bot_status = {9090: '🟢正常', 9091: '🟢正常', 9092: '🔴离线', 9093: '🟢正常'}
intervention = {'action': 'freeze', 'reason': '测试干预', 'timestamp': '2026-03-28 14:30'}
freeze = {'frozen': False, 'frozen_pairs': []}

card = build_card(positions, sentiment, bot_status, intervention, freeze)
payload = json.dumps(card, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(WEBHOOK, data=payload, headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=10) as r:
    result = json.loads(r.read())
code = result.get("StatusCode", -1)
print(f"{'✅' if code == 0 else '❌'} 巡查卡片原生按钮测试: code={code}")
