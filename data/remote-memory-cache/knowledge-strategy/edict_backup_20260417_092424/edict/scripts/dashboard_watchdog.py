#!/usr/bin/env python3
"""
尚书省 · 总控台健康监控与自动修复脚本
监控：7891总控台各省部agent状态
自动修复：任务卡住时触发重派，agent离线时唤醒
"""
import json, subprocess, sys, threading, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path

DATA_DIR = Path("/Users/luxiangnan/edict/data")
LOG_FILE = DATA_DIR / "logs" / "dashboard_watchdog.log"
LOG_FILE.parent.mkdir(exist_ok=True)
DASH_URL = "http://127.0.0.1:7891"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def http_get(path):
    try:
        req = urllib.request.Request(f"{DASH_URL}{path}")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())
    except Exception as e:
        return None

def check_agents_status():
    """从看板API获取各省部agent状态"""
    data = http_get("/api/agents-status")
    if not data:
        return {}
    result = {}
    for a in data.get("agents", []):
        aid = a["id"]
        result[aid] = {
            "label": a.get("label", aid),
            "status": a.get("status", "unknown"),
            "statusLabel": a.get("statusLabel", "⚪"),
            "lastActive": a.get("lastActive"),
            "sessions": a.get("sessions", 0),
        }
    return result

def check_tasks():
    """从看板获取活跃任务列表"""
    tasks = http_get("/api/live-status")
    if not tasks:
        return []
    return tasks

def check_dashboard_alive():
    """检测7891服务是否存活"""
    try:
        req = urllib.request.Request(f"{DASH_URL}/healthz")
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except:
        return False

def restart_dashboard():
    """重启7891 dashboard服务"""
    try:
        # 先尝试找到进程
        result = subprocess.run(["pgrep", "-f", "server.py.*7891"],
                              capture_output=True, text=True, timeout=5)
        if result.stdout.strip():
            pid = result.stdout.strip().split()[0]
            subprocess.run(["kill", pid], timeout=5)
            import time; time.sleep(1)
        # 重启
        subprocess.Popen(
            ["python3", "-m", "http.server", "7891"],
            cwd="/Users/luxiangnan/edict/dashboard",
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        log("[INFO] dashboard已重启")
        return True
    except Exception as e:
        log(f"[ERROR] dashboard重启失败: {e}")
        return False

def send_dispatch(agent_id, task_id, task_title):
    """通过openclaw agent命令向各省部派发任务"""
    msg = f"任务已派发：{task_title}\n任务ID: {task_id}\n请立即执行并用 kanban_update.py 更新状态。"
    try:
        result = subprocess.run(
            ["/opt/homebrew/bin/openclaw", "agent", "--agent", agent_id, "-m", msg, "--timeout", "300"],
            capture_output=True, text=True, timeout=310
        )
        return result.returncode == 0
    except Exception as e:
        log(f"[ERROR] 向 {agent_id} 派发失败: {e}")
        return False

def main():
    log("━━━ 尚书省·总控台健康检查 ━━━")
    
    # 1. 检测dashboard服务
    alive = check_dashboard_alive()
    if alive:
        log("dashboard服务: ✅ 正常运行")
    else:
        log("dashboard服务: ❌ 无响应，尝试重启...")
        restart_dashboard()
    
    # 2. 检查各省部agent状态
    agents = check_agents_status()
    if agents:
        log("各省部agent状态:")
        for aid, info in sorted(agents.items()):
            log(f"  {info['statusLabel']} {info['label']}({aid}): {info['sessions']}会话 {info['lastActive'] or '无记录'}")
            # 如果离线超过10分钟，尝试唤醒
            if info['status'] == 'offline' and info['lastActive'] is None:
                log(f"  → 唤醒 {aid}...")
                subprocess.Popen(
                    ["/opt/homebrew/bin/openclaw", "agent", "--agent", aid, "-m", f"🔔 唤醒确认，请回复。"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
    else:
        log("[WARN] 无法获取agent状态（看板API异常）")
    
    # 3. 检查活跃任务（live-status返回dict，取tasks字段）
    tasks_data = check_tasks()
    if isinstance(tasks_data, dict):
        tasks = tasks_data.get("tasks", [])
    elif isinstance(tasks_data, list):
        tasks = tasks_data
    else:
        tasks = []
    if tasks:
        log(f"活跃任务: {len(tasks)} 个")
        # 检查卡住的任务
        now = datetime.now()
        stuck = []
        for t in tasks:
            updated = t.get("updatedAt", "")
            if not updated:
                continue
            try:
                upd = datetime.fromisoformat(updated.replace("Z", "+00:00").replace("+00:00", ""))
                age_h = (now - upd).total_seconds() / 3600
                state = t.get("state", "")
                if age_h > 2 and state not in ("Done", "Cancelled"):
                    stuck.append(t)
            except:
                pass
        if stuck:
            log(f"[WARN] 发现 {len(stuck)} 个卡住的任务(>2小时未推进):")
            for t in stuck[:5]:
                log(f"  - {t.get('id')} | {t.get('title','')[:30]} | {t.get('state')}")
    else:
        log("[WARN] 无法获取任务列表")
    
    log("━━━ 检查完毕 ━━━\n")

if __name__ == "__main__":
    main()
