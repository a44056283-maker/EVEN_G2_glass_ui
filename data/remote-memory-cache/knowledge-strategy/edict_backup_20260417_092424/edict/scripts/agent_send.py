#!/usr/bin/env python3
"""
Agent Send · 发送消息到消息总线
用法: python3 agent_send.py <sender> <recipient> <content>
示例: python3 agent_send.py 兵部 尚书省 发现BTC异常波动

特殊recipient:
  GROUP  - 发到群里（所有人可见）
  ALL    - 广播给所有人
"""
import json, sys, uuid
from pathlib import Path

INBOX_DIR  = Path("/Users/luxiangnan/edict/data/agent_inbox")
QUEUE_FILE = INBOX_DIR / "pending_messages.json"

WEBHOOK_MAP = {
    "尚书省": "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0",
    "中书省": "https://open.feishu.cn/open-apis/bot/v2/hook/c03400f7-5ce5-4205-acfe-a6959e418d7e",
    "门下省": "https://open.feishu.cn/open-apis/bot/v2/hook/10163f03-8169-45cc-9f80-c5a01220ff8f",
    "吏部": "https://open.feishu.cn/open-apis/bot/v2/hook/7f5ef738-0262-45aa-bd15-5f03e3e07ee5",
    "工部": "https://open.feishu.cn/open-apis/bot/v2/hook/75f0a953-5054-434b-a43a-4ab25f6ba310",
    "兵部": "https://open.feishu.cn/open-apis/bot/v2/hook/cd349c33-afef-413a-977b-936f5a1559dc",
    "户部": "https://open.feishu.cn/open-apis/bot/v2/hook/bb3a28da-12d8-4f5d-97db-d1fcb86578c7",
    "礼部": "https://open.feishu.cn/open-apis/bot/v2/hook/64aed36a-93a7-4626-bbb3-c290fd134397",
    "刑部": "https://open.feishu.cn/open-apis/bot/v2/hook/a1b4c0d0-2ea0-4fb0-a9e5-d30e8573df18",
    "太子": "https://open.feishu.cn/open-apis/bot/v2/hook/f3c066e1-0624-411a-ac25-26bb74f9f3d3",
    "钦天监": "https://open.feishu.cn/open-apis/bot/v2/hook/e9e7cc70-b512-4601-b77e-3b4624dd8a6c",
    "天禄": "https://open.feishu.cn/open-apis/bot/v2/hook/632c7bfc-e3a1-4ba3-b763-72bdac398b4e",
}

def load_queue():
    try:
        return json.loads(QUEUE_FILE.read_text())
    except:
        return {"messages": [], "last_processed_id": ""}

def save_queue(data):
    tmp = str(QUEUE_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(data, ensure_ascii=False, indent=2))
    Path(tmp).replace(QUEUE_FILE)

def send(sender, recipient, content):
    queue = load_queue()
    msg = {
        "id": str(uuid.uuid4())[:8],
        "sender": sender,
        "recipient": recipient,
        "content": content,
        "timestamp": __import__("datetime").datetime.now().strftime("%H:%M")
    }
    queue["messages"].append(msg)
    save_queue(queue)
    
    recipients = [recipient] if recipient != "ALL" else list(WEBHOOK_MAP.keys())
    print(f"📤 [{sender}] → [{recipient}]: {content[:60]}")
    print(f"✅ 消息已入队，等待Bus发送")
    return msg["id"]

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("用法: python3 agent_send.py <发送者> <接收者> <内容>")
        print("       python3 agent_send.py 兵部 GROUP 发现BTC剧烈波动请关注")
        print("       python3 agent_send.py 天禄 ALL 系统正常")
        sys.exit(1)
    
    sender    = sys.argv[1]
    recipient = sys.argv[2].upper()
    content   = " ".join(sys.argv[3:])
    
    msg_id = send(sender, recipient, content)
    print(f"   消息ID: {msg_id}")
