#!/usr/bin/env python3
"""
Agent Bus · 消息总线（静默版）
- 用 urllib 代替 requests，彻底避免依赖警告
- 无消息时完全静默零输出
"""
import json, urllib.request, uuid
from datetime import datetime
from pathlib import Path

INBOX_DIR    = Path("/Users/luxiangnan/edict/data/agent_inbox")
QUEUE_FILE   = INBOX_DIR / "pending_messages.json"
WEBHOOK_MAP  = INBOX_DIR / "webhook_map.json"
LOG_FILE     = Path("/Users/luxiangnan/edict/data/logs/agent_bus.log")
GROUP_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/632c7bfc-e3a1-4ba3-b763-72bdac398b4e"

def _log(msg):
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except: pass

def _load(path):
    try: return json.loads(path.read_text())
    except: return None

def _save(path, data):
    tmp = str(path) + ".tmp"
    Path(tmp).write_text(json.dumps(data, ensure_ascii=False, indent=2))
    Path(tmp).replace(path)

def _send(webhook, msg):
    try:
        payload = json.dumps({"msg_type": "text", "content": {"text": msg}}).encode()
        req = urllib.request.Request(webhook, data=payload,
                                    headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status == 200
    except: return False

if __name__ == "__main__":
    queue  = _load(QUEUE_FILE) or {"messages": [], "last_processed_id": ""}
    msgs   = queue.get("messages", [])
    last   = queue.get("last_processed_id", "")
    pending = [m for m in msgs if m.get("id", "") > last]

    if not pending:
        raise SystemExit(0)  # 完全静默

    wmap = _load(WEBHOOK_MAP) or {}
    ok   = 0
    for m in pending:
        dst = m.get("recipient", "GROUP")
        wh  = GROUP_WEBHOOK if dst == "GROUP" else wmap.get(dst, "")
        txt = (f"【{m['sender']}】\n{m['content']}" if dst == "GROUP"
                else f"【{m['sender']}】→【{dst}】\n{m['content']}")
        if wh and _send(wh, txt):
            ok += 1
            last = m.get("id", last)
            _log(f"OK {m['sender']}→{dst}")

    queue["last_processed_id"] = last
    _save(QUEUE_FILE, queue)
    print(ok)  # 只有消息时才输出数字
