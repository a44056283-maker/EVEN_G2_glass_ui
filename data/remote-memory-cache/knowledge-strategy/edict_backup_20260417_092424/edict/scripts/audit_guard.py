#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
太子（天禄）· 审批审查
职责：审核兵部告警 → 评估是否提报父亲审批
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime
from datetime import datetime
from pathlib import Path

TAIZI_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"
PENDING_FILE = "/Users/luxiangnan/edict/data/pending_approvals.json"
LOG_FILE = "/Users/luxiangnan/edict/data/logs/taizi_audit.log"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except:
        pass

def load_pending():
    if os.path.exists(PENDING_FILE):
        try:
            with open(PENDING_FILE) as f:
                return json.load(f)
        except:
            return []
    return []

def save_pending(items):
    os.makedirs(os.path.dirname(PENDING_FILE), exist_ok=True)
    with open(PENDING_FILE, "w") as f:
        json.dump(items, f, ensure_ascii=False)

def add_pending(alert_id, alert_type, bot, pair, reason, severity):
    """添加待审核项"""
    pending = load_pending()
    item = {
        "id": alert_id,
        "type": alert_type,
        "bot": bot,
        "pair": pair,
        "reason": reason,
        "severity": severity,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "pending"
    }
    # 检查是否已存在
    for p in pending:
        if p.get("id") == alert_id:
            return False
    pending.append(item)
    save_pending(pending)
    return True

def approve(alert_id):
    """批准执行"""
    pending = load_pending()
    for p in pending:
        if p.get("id") == alert_id:
            p["status"] = "approved"
            p["approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_pending(pending)
            log(f"✅ 批准: {alert_id}")
            return True
    return False

def reject(alert_id):
    """否决执行"""
    pending = load_pending()
    for p in pending:
        if p.get("id") == alert_id:
            p["status"] = "rejected"
            p["rejected_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_pending(pending)
            log(f"❌ 否决: {alert_id}")
            return True
    return False

def send_to_bingbu(msg):
    """发送指令到汇报群"""
    import requests
    REPORT_GROUP = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"
    try:
        requests.post(REPORT_GROUP, json={
            "msg_type": "text",
            "content": {"text": f"🔔 太子指令\n{msg}"}
        }, timeout=5)
    except:
        pass

def audit_and_notify():
    """审核待处理告警，发送催办给太子"""
    pending = load_pending()
    if not pending:
        log("无待审核告警")
        return
    
    log(f"待审核告警: {len(pending)}条")
    
    # 按严重程度排序
    severity_order = {"critical": 0, "high": 1, "normal": 2}
    pending.sort(key=lambda x: severity_order.get(x.get("severity", "normal"), 3))
    
    report = f"📋 太子待审核\n共{len(pending)}项:\n\n"
    for p in pending:
        emoji = "🔴" if p.get("severity") == "critical" else "🟠" if p.get("severity") == "high" else "🟡"
        report += f"{emoji} [{p.get('id')}]\n"
        report += f"   {p.get('bot')} - {p.get('pair')}\n"
        report += f"   {p.get('reason')}\n\n"
    
    log(report)
    
    # 发送到太子飞书
    import requests
    try:
        requests.post(TAIZI_WEBHOOK, json={
            "msg_type": "text",
            "content": {"text": report}
        }, timeout=5)
    except:
        pass

def manual_unfreeze(reason: str = "手动解冻"):
    """手动解除冻结"""
    FREEZE_FILE = Path("/Users/luxiangnan/edict/data/bingbu_freeze.json")
    INTERV_FILE = Path("/Users/luxiangnan/edict/data/bingbu_intervention.json")
    STATE_FILE = Path("/Users/luxiangnan/edict/data/bingbu_intervention_state.json")

    # 记录解冻
    interventions = []
    if INTERV_FILE.exists():
        interventions = json.loads(INTERV_FILE.read_text())
    interventions.insert(0, {
        "id": len(interventions) + 1,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": "manual_unfreeze",
        "reason": reason,
        "result": "success"
    })
    INTERV_FILE.write_text(json.dumps(interventions[:200], ensure_ascii=False, indent=2))

    # 更新状态文件
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
        state["is_frozen"] = False
        state["last_action"] = "manual_unfreeze"
        state["last_action_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))

    # 删除冻结标记
    if FREEZE_FILE.exists():
        FREEZE_FILE.unlink()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 手动解冻完成 | 原因: {reason}")
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "audit":
            audit_and_notify()
        elif sys.argv[1] == "approve" and len(sys.argv) > 2:
            approve(sys.argv[2])
        elif sys.argv[1] == "reject" and len(sys.argv) > 2:
            # 通过monitor_sentiment.py执行（会记录被否决事件）
            import subprocess
            r = subprocess.run(
                ["python3", "/Users/luxiangnan/edict/scripts/monitor_sentiment.py",
                 "reject", sys.argv[2]],
                capture_output=True, text=True, timeout=10
            )
            print(r.stdout.strip() if r.stdout else "执行完成")

        elif sys.argv[1] == "approve" and len(sys.argv) > 2:
            # 通过monitor_sentiment.py执行（执行冻结）
            import subprocess
            r = subprocess.run(
                ["python3", "/Users/luxiangnan/edict/scripts/monitor_sentiment.py",
                 "approve", sys.argv[2]],
                capture_output=True, text=True, timeout=15
            )
            print(r.stdout.strip() if r.stdout else "执行完成")
        elif sys.argv[1] == "unfreeze":
            reason = sys.argv[2] if len(sys.argv) > 2 else "手动解冻"
            manual_unfreeze(reason)
        elif sys.argv[1] == "status":
            FREEZE_FILE = Path("/Users/luxiangnan/edict/data/bingbu_freeze.json")
            INTERV_FILE = Path("/Users/luxiangnan/edict/data/bingbu_intervention.json")
            PENDING_FILE = Path("/Users/luxiangnan/edict/data/pending_approvals.json")
            if FREEZE_FILE.exists():
                freeze = json.loads(FREEZE_FILE.read_text())
                last = freeze.get("last_freeze_at", None)
                cooldown = freeze.get("cooldown_minutes", 30)
                if last and last != "?":
                    from datetime import datetime as dt
                    try:
                        elapsed = (dt.now() - dt.strptime(last, "%Y-%m-%d %H:%M:%S")).total_seconds()
                        remaining = max(0, cooldown * 60 - elapsed)
                        print(f"冻结状态: 🔴 已冻结 | 上次冻结: {last} | Cooldown剩余: {int(remaining//60)}分钟")
                    except ValueError:
                        print(f"冻结状态: 🔴 已冻结 | 上次冻结时间无效: {last}")
                else:
                    print(f"冻结状态: 🔴 已冻结 | 但无有效时间记录")
            else:
                print("冻结状态: ✅ 未冻结")
            pending = json.loads(PENDING_FILE.read_text()) if PENDING_FILE.exists() else []
            pending_active = [p for p in pending if p.get("status") == "pending"]
            print(f"待审批: {len(pending_active)} 个")
        else:
            print("用法: audit_guard.py [audit|approve|reject|unfreeze|status] [id]")
    else:
        print("用法: audit_guard.py [audit|approve|reject|unfreeze|status] [id]")
