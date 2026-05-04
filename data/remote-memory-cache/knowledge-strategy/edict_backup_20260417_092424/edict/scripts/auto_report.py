#!/usr/bin/env python3
"""
尚书省·自动化汇报脚本
功能：每日汇报任务执行状态、六部派发进度
"""

import os, json, argparse
from datetime import datetime
from pathlib import Path

DATA_DIR = "/Users/luxiangnan/edict/data"
WORKSPACE = "/Users/luxiangnan/.openclaw/workspace-shangshu"
KANBAN = "/Users/luxiangnan/edict/scripts/kanban_update.py"
LOG_FILE = f"{DATA_DIR}/logs/shangshu.log"
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
    wh = os.environ.get("SHANGSHU_WEBHOOK", "")
    if not wh or "${" in wh:
        log("[WARN] SHANGSHU_WEBHOOK未配置")
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

def load_tasks():
    try:
        with open(f"{DATA_DIR}/tasks_source.json", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def daily_report():
    """每日执行状态汇报"""
    log("━━━ 尚书省每日汇报 ━━━")
    tasks = load_tasks()

    states = {}
    for t in tasks:
        s = t.get("state", "未知")
        states[s] = states.get(s, 0) + 1

    doing = [t for t in tasks if t.get("state") == "Doing"]
    assigned = [t for t in tasks if t.get("state") == "Assigned"]

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"🏛️ **尚书省·每日汇报** `{now}`",
        f"",
        f"总任务: {len(tasks)} | 📥执行中: {len(doing)} | 📤待派发: {len(assigned)}",
        f"",
        f"**各状态分布:**"
    ]
    for s, cnt in sorted(states.items(), key=lambda x: -x[1]):
        lines.append(f"• {s}: {cnt}条")

    if doing:
        lines.append(f"")
        lines.append(f"**📥 执行中任务:**")
        for t in doing[:10]:
            lines.append(f"• `{t.get('id','?')}` {t.get('title','')[:35]}")
        if len(doing) > 10:
            lines.append(f"  ...还有 {len(doing)-10} 条")

    msg = "\n".join(lines)
    send_feishu(msg)
    log(f"汇报已发送: 执行中{len(doing)}条, 待派发{len(assigned)}条")
    return {"doing": len(doing), "assigned": len(assigned), "states": states}

def check_stuck():
    """检查卡住的任务（Assigned超过2小时未派发）"""
    log("━━━ 尚书省任务卡住检查 ━━━")
    tasks = load_tasks()
    assigned = [t for t in tasks if t.get("state") == "Assigned"]
    stuck = []
    for t in assigned:
        entry = t.get("entry_at", "")
        if entry:
            try:
                from datetime import datetime
                entry_dt = datetime.fromisoformat(entry.replace("Z", "+00:00"))
                hours = (datetime.now() - entry_dt.replace(tzinfo=None)).total_seconds() / 3600
                if hours > 2:
                    stuck.append((t, hours))
            except:
                pass

    if stuck:
        lines = [f"🚨 **尚书省任务卡住预警**\n共 {len(stuck)} 个任务 Assignned超过2小时未派发:\n"]
        for t, hours in stuck:
            lines.append(f"• `{t.get('id','?')}` {t.get('title','')[:30]} ({hours:.1f}h)")
        send_feishu("\n".join(lines))
        log(f"卡住告警: {len(stuck)}条")
    else:
        log("无卡住任务")

    return {"stuck": len(stuck)}


def check_audit_mechanism():
    """
    兵部动态干预审核机制健康检查
    1. 检查Cooldown状态和剩余时间
    2. 检查待审批队列（超时未处理则催办）
    3. 检查sentiment_pool数据时效
    4. 异常时飞书通知门下省
    """
    from datetime import timedelta
    log("━━━ 兵部审核机制健康检查 ━━━")

    # ── 1. Cooldown状态 ─────────────────────────
    cooldown_status = "未知"
    cooldown_remaining = 0
    try:
        with open(f"{DATA_DIR}/bingbu_freeze.json") as f:
            freeze = json.load(f)
        last_ts = freeze.get("last_freeze_at", "")
        if last_ts:
            last_dt = datetime.strptime(last_ts, "%Y-%m-%d %H:%M:%S")
            elapsed = datetime.now() - last_dt
            cooldown_min = freeze.get("cooldown_minutes", 30)
            remaining = max(0, cooldown_min * 60 - elapsed.total_seconds())
            cooldown_remaining = int(remaining // 60)
            if remaining > 0:
                cooldown_status = f"⏳ 冷却中（剩余 {cooldown_remaining} 分钟）"
            else:
                cooldown_status = "✅ 冷却已结束，可接受新审批"
    except:
        cooldown_status = "✅ 未在冷却（无冻结记录）"

    log(f"  Cooldown: {cooldown_status}")

    # ── 2. 待审批队列检查 ────────────────────────
    pending_issues = []
    try:
        with open(f"{DATA_DIR}/pending_approvals.json") as f:
            pending = json.load(f)
        pending_items = [p for p in pending if p.get("status") == "pending"]
        for p in pending_items:
            created = p.get("created_at", "")
            if created:
                try:
                    created_dt = datetime.strptime(created, "%Y-%m-%d %H:%M:%S")
                    wait_min = (datetime.now() - created_dt).total_seconds() / 60
                    if wait_min > 30:
                        pending_issues.append(
                            f"⚠️ `{p.get('id')}` 类型={p.get('type')} "
                            f"已等待 {int(wait_min)} 分钟（超时未审批）"
                        )
                except:
                    pass
    except:
        pending_items = []
        log("  pending_approvals.json 不存在或为空（正常）")

    # ── 3. 聚合数据时效检查 ──────────────────────
    pool_stale = False
    try:
        with open(f"{DATA_DIR}/sentiment_pool.json") as f:
            pool = json.load(f)
        # Check market.updated_at (main sentiment data) instead of news.updated_at
        updated = pool.get("market", {}).get("updated_at", pool.get("news", {}).get("updated_at", ""))
        if updated:
            updated_dt = datetime.strptime(updated, "%Y-%m-%d %H:%M:%S")
            age_min = (datetime.now() - updated_dt).total_seconds() / 60
            if age_min > 30:
                pool_stale = True
                log(f"  ⚠️ sentiment_pool 数据陈旧（{int(age_min)}分钟未更新）")
    except:
        log("  ⚠️ sentiment_pool.json 读取失败")

    # ── 4. 生成报告 ──────────────────────────────
    alerts = []
    if pending_issues:
        alerts.extend(pending_issues)
    if pool_stale:
        alerts.append("⚠️ sentiment_pool 数据超时未更新，可能影响舆情判断")

    report_lines = [
        f"📋 **兵部审核机制状态报告** `{datetime.now().strftime('%H:%M')}`",
        f"",
        f"❄️ 冻结/Cooldown：{cooldown_status}",
        f"📂 待审批队列：{len(pending_items)} 个待处理",
        f"📊 数据状态：{'⚠️ 陈旧' if pool_stale else '✅ 正常'}",
    ]
    if alerts:
        report_lines.append("")
        report_lines.extend(alerts)

    report = "\n".join(report_lines)
    log(f"\n{report}")
    send_feishu(report)

    return {
        "cooldown": cooldown_status,
        "cooldown_minutes_left": cooldown_remaining,
        "pending_count": len(pending_items),
        "pool_stale": pool_stale,
        "issues": alerts,
    }


def tripartite_report():
    """三省会商状态报告（每日14:00）"""
    log("━━━ 三省会商状态报告 ━━━")
    tasks = load_tasks()

    # State summary
    states = {}
    for t in tasks:
        s = t.get("state", "?")
        states[s] = states.get(s, 0) + 1

    # Categorize by province
    zhongshu = [t for t in tasks if t.get("state") == "Zhongshu"]
    doing = [t for t in tasks if t.get("state") == "Doing"]
    done_recent = [t for t in tasks if t.get("state") == "Done"][-5:]
    stuck = [t for t in tasks if t.get("state") == "Assigned"]

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"🏛️ **三省会商状态** `{now}`",
        f"",
        f"**📊 总体概况**",
        f"总任务: {len(tasks)} | 中书省待审议: {len(zhongshu)} | 尚书省执行中: {len(doing)} | 已完成: {states.get('Done',0)}",
        f""
    ]

    # 中书省
    if zhongshu:
        lines.append(f"**📝 中书省（{len(zhongshu)}项待审议）**")
        for t in zhongshu[:5]:
            lines.append(f"• {t.get('title','')[:40]}")
        if len(zhongshu) > 5:
            lines.append(f"  ...还有 {len(zhongshu)-5} 项")
        lines.append(f"")

    # 尚书省
    if doing:
        lines.append(f"**⚙️ 尚书省（{len(doing)}项执行中）**")
        for t in doing[:5]:
            lines.append(f"• {t.get('title','')[:40]}")
        lines.append(f"")

    # 卡住任务
    if stuck:
        lines.append(f"**⏸️ 待派发（积压 {len(stuck)}项）**")
        for t in stuck[:3]:
            lines.append(f"• {t.get('title','')[:35]}")
        lines.append(f"")

    # 最近完成
    if done_recent:
        lines.append(f"**✅ 最近完成**")
        for t in done_recent:
            lines.append(f"• {t.get('title','')[:40]}")

    msg = "\n".join(lines)
    send_feishu(msg)
    log(f"三省会商汇报已发送")
    return {
        "total": len(tasks),
        "zhongshu": len(zhongshu),
        "doing": len(doing),
        "done": states.get("Done", 0),
        "stuck": len(stuck)
    }

def main():
    parser = argparse.ArgumentParser(description="尚书省自动化汇报")
    parser.add_argument("mode", nargs="?", default="report",
        choices=["report", "stuck", "tripartite", "audit"])
    args = parser.parse_args()

    if args.mode == "report":
        r = daily_report()
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif args.mode == "stuck":
        r1 = check_stuck()
        r2 = check_audit_mechanism()
        print(json.dumps({"stuck": r1, "audit": r2}, ensure_ascii=False, indent=2))
    elif args.mode == "audit":
        r = check_audit_mechanism()
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif args.mode == "tripartite":
        r = tripartite_report()
        print(json.dumps(r, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
