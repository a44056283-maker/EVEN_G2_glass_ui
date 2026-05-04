#!/usr/bin/env python3
"""
太子·JJC任务汇报脚本
每2小时向飞书汇报太子新建的JJC任务状态
"""
import json, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

TASKS_FILE = Path("/Users/luxiangnan/edict/data/tasks_source.json")
WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"

def send_feishu(title: str, message: str) -> bool:
    payload = json.dumps({
        "msg_type": "text",
        "content": {"text": f"**{title}**\n{message}"}
    }).encode("utf-8")
    req = urllib.request.Request(WEBHOOK, data=payload,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"send_feishu failed: {e}")
        return False

def main():
    tasks = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
    
    # 获取太子最近创建/处理的任务
    now = datetime.now(timezone.utc)
    recent_tasks = []
    for t in tasks:
        if not t.get("id", "").startswith("JJC-"):
            continue
        # 检查是否由太子创建或处理
        flow = t.get("flow_log", [])
        if not flow:
            continue
        # 取最近一条flow
        last = flow[-1]
        try:
            last_at = datetime.fromisoformat(last["at"].replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
            age_hours = (now - last_at).total_seconds() / 3600
            if age_hours < 26:  # 过去26小时
                recent_tasks.append(t)
        except Exception:
            pass
    
    if not recent_tasks:
        send_feishu("太子·JJC任务汇报", "📋 过去24小时无新增JJC任务，静默。")
        return
    
    lines = ["📋 **太子·JJC任务汇报**（过去24小时）", "", 
             f"共 {len(recent_tasks)} 项任务：", ""]
    
    for t in recent_tasks:
        lines.append(f"• **{t['id']}** [{t.get('state', '?')}]")
        lines.append(f"  {t.get('title', '?')}")
    
    send_feishu("太子·JJC任务汇报", "\n".join(lines))

if __name__ == "__main__":
    main()
