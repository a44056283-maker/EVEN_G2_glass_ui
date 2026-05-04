#!/usr/bin/env python3
"""
中书省·旨意自动处理器（简化版）
功能：轮询 tasks_source.json，发现 Zhongshu 任务则上报并处理
实际的 subagent 调用由 cron job 的 agent 直接执行
"""

import os, sys, json, argparse
from datetime import datetime
from pathlib import Path

DATA_DIR = "/Users/luxiangnan/edict/data"
WORKSPACE = "/Users/luxiangnan/.openclaw/workspace-zhongshu"
KANBAN = "/Users/luxiangnan/edict/scripts/kanban_update.py"
LOG_FILE = f"{DATA_DIR}/logs/zhongshu_processor.log"
os.makedirs(f"{DATA_DIR}/logs", exist_ok=True)

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def _env():
    env = Path(WORKSPACE) / ".env"
    if env.exists():
        for line in env.read_text().strip().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

def send_feishu(text):
    _env()
    wh = os.environ.get("ZHONGSHU_WEBHOOK", "")
    if not wh or "${" in wh:
        log("[WARN] ZHONGSHU_WEBHOOK未配置")
        return False
    try:
        import urllib.request
        payload = json.dumps({
            "msg_type": "text",
            "content": {"text": text}
        }).encode("utf-8")
        req = urllib.request.Request(wh, data=payload,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            r = json.loads(resp.read())
            return r.get("StatusCode", 0) == 0
    except Exception as e:
        log(f"[ERROR] 飞书发送失败: {e}")
        return False

def run_cmd(cmd):
    import subprocess
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as e:
        return "", str(e), 1

def kanban(cmd, *args):
    return run_cmd(["python3", KANBAN, cmd] + list(args))

def load_tasks():
    try:
        with open(f"{DATA_DIR}/tasks_source.json", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def mark_reviewed(task_id):
    try:
        tasks = load_tasks()
        for t in tasks:
            if t.get("id") == task_id:
                t["menxia_reviewed"] = True
                t["menxia_decision"] = "pending"
                break
        with open(f"{DATA_DIR}/tasks_source.json", "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"[WARN] mark_reviewed失败: {e}")

def set_state(task_id, state, note=""):
    kanban("state", task_id, state, note)

def set_flow(task_id, fm, to, remark=""):
    kanban("flow", task_id, fm, to, remark)

def set_progress(task_id, stage, plan=""):
    kanban("progress", task_id, stage, plan)

def set_done(task_id, output, summary):
    kanban("done", task_id, output, summary)

def main():
    parser = argparse.ArgumentParser(description="中书省旨意自动处理器")
    parser.add_argument("--task-id", help="只处理指定任务ID")
    args = parser.parse_args()

    log("━━━ 中书省旨意处理器启动 ━━━")
    tasks = load_tasks()
    zhongshu = [t for t in tasks if t.get("state") == "Zhongshu"
                and not t.get("menxia_reviewed")]

    if not zhongshu:
        log("无待处理任务")
        print(json.dumps({"processed": 0, "tasks": []}))
        return

    log(f"发现 {len(zhongshu)} 个待处理任务:")
    for t in zhongshu:
        tid = t["id"]
        title = t.get("title", "")[:40]
        log(f"  - {tid}: {title}")

        # 标记为已受理（防止重复处理）
        mark_reviewed(tid)

        # 更新看板：起草中
        set_state(tid, "Zhongshu", "中书省正在起草方案")
        set_progress(tid, "正在起草执行方案", "起草方案🔄|提交审议|尚书执行|回奏皇上")
        send_feishu(f"📝 中书省接旨: {tid}\n方案: {title}\n\n正在起草...")

        # 生成简版方案
        scheme = f"目标: {title}。方案: 由尚书省协调六部执行。"
        log(f"  方案已起草: {scheme[:60]}")

        # 提交门下省审议
        set_state(tid, "Menxia", "方案已起草，提交门下省审议")
        set_flow(tid, "中书省", "门下省", "审议中")
        set_progress(tid, "已提交门下省审议", "起草方案✅|提交审议🔄|尚书执行|回奏皇上")

        log(f"  已提交门下省审议，等待准奏/封驳")

    summary = [f"📋 中书省旨意处理报告\n\n发现 **{len(zhongshu)}个** 待处理任务:\n"]
    for t in zhongshu:
        summary.append(f"• `{t['id']}`: {t.get('title','')[:40]}")

    send_feishu("\n".join(summary))
    print(json.dumps({"processed": len(zhongshu), "tasks": [t["id"] for t in zhongshu]}))

if __name__ == "__main__":
    main()
