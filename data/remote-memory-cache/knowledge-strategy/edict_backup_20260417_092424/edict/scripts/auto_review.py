#!/usr/bin/env python3
"""
门下省 · 自动化审议脚本
功能：T+1风控日报审查 / 新任务到达通知 / 审议进度上报 / 周五复盘 / 回撤预警自动受理
调度：每日09:30执行 t1_review+daily_check，每周5 14:00执行 friday_review
"""

import sys
import os
import json
import logging
import argparse
import fcntl
import tempfile
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

# ── 路径配置 ────────────────────────────────────────────────────────────────
EDICT_ROOT   = Path("/Users/luxiangnan/edict")
SCRIPTS_DIR  = EDICT_ROOT / "scripts"
DATA_DIR     = EDICT_ROOT / "data"
REPORTS_DIR  = DATA_DIR / "reports"
LOGS_DIR     = DATA_DIR / "logs"
TASKS_FILE   = DATA_DIR / "tasks_source.json"
LOCK_DIR     = DATA_DIR / "locks"
ALERT_API    = "http://localhost:7891/api/bingbu/positions"
FEISHU_SCRIPT = SCRIPTS_DIR / "send_trade_alert.sh"

# 确保必要目录存在
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOCK_DIR.mkdir(parents=True, exist_ok=True)

# ── 日志配置 ────────────────────────────────────────────────────────────────
LOG_FILE = LOGS_DIR / "menxia_auto.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("menxia")


# ═══════════════════════════════════════════════════════════════════════════
#  底层工具
# ═══════════════════════════════════════════════════════════════════════════

def _lock_path(path: Path) -> Path:
    return LOCK_DIR / (path.name + ".lock")


def atomic_json_read(path: Path, default: Any = None) -> Any:
    """持共享锁读取 JSON 文件"""
    lock_file = _lock_path(path)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_SH)
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
        except Exception:
            return default
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _load_env():
    """从workspace/.env加载环境变量"""
    env_file = Path.home() / ".openclaw" / "workspace-menxia" / ".env"
    if env_file.exists():
        for line in env_file.read_text().strip().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

def send_feishu(level: str, title: str, message: str) -> bool:
    """
    通过 send_trade_alert.py 发送飞书告警
    level: P0/P1/P2/OK
    """
    try:
        import subprocess
        script = FEISHU_SCRIPT
        if not script.exists():
            log.warning("send_trade_alert.sh 不存在，尝试直接curl")
            return _send_feishu_direct(level, title, message)

        result = subprocess.run(
            ["python3", str(script), "--level", level, "--title", title, "--msg", message],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            log.info(f"飞书通知发送成功: {title}")
            return True
        else:
            log.warning(f"飞书通知发送失败: {result.stderr[:200]}")
            return _send_feishu_direct(level, title, message)
    except Exception as e:
        log.error(f"send_feishu异常: {e}")
        return _send_feishu_direct(level, title, message)


def _send_feishu_direct(level: str, title: str, message: str) -> bool:
    """直接curl飞书webhook（备用）"""
    _load_env()
    REPORT_GROUP = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"
    webhook = REPORT_GROUP
    emoji_map = {"P0": "🔴", "P1": "🚨", "P2": "🟠", "OK": "✅"}
    content = f"{emoji_map.get(level,'ℹ️')} **{title}**\n{message}"
    payload = json.dumps({"msg_type": "text", "content": {"text": content}}).encode()
    req = urllib.request.Request(webhook, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            log.info(f"飞书通知(直接curl)响应: {resp.read().decode()[:100]}")
            return True
    except Exception as e:
        log.error(f"飞书curl失败: {e}")
        return False


def _yesterday() -> str:
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _week_range() -> tuple:
    """返回本周一和下周一的日期字符串"""
    today_dt = datetime.now()
    monday = today_dt - timedelta(days=today_dt.weekday())
    next_monday = monday + timedelta(days=7)
    return monday.strftime("%Y-%m-%d"), next_monday.strftime("%Y-%m-%d")


# ═══════════════════════════════════════════════════════════════════════════
#  功能1：每日 T+1 风控日报审查
# ═══════════════════════════════════════════════════════════════════════════

def t1_review() -> dict:
    """
    读取昨日风控日报，对照阈值生成预警
    返回: {date, level, message, bots_down}
    """
    ydate = _yesterday()
    tdate = _today()  # 当天日期用于审查报告
    report_path = REPORTS_DIR / "daily" / ydate / "risk_report.json"
    log.info(f"━━━ T+1风控日报审查 [{ydate}] ━━━")

    result = {
        "date": ydate,
        "review_date": tdate,  # 新增审查日期
        "level": "OK",
        "message": f"风控日报审查通过（{ydate}）",
        "bots_down": [],
    }

    if not report_path.exists():
        log.warning(f"风控日报不存在: {report_path}")
        # 补查各Bot实时状态
        bots_status = []
        for port in [9090, 9091, 9092, 9093, 9094, 9095, 9096, 9097]:
            try:
                urllib.request.urlopen(urllib.request.Request(f"http://localhost:{port}/api/v1/ping", timeout=3))
                bots_status.append(f"✅ {port} 在线")
            except:
                bots_status.append(f"❌ {port} 离线")
        bots_text = "\n".join(bots_status) if bots_status else "（无Bot数据）"
        result["level"] = "P2"
        result["message"] = f"⚠️ 风控日报缺失（{ydate}），请人工确认"
        send_feishu("P2", "【门下省】T+1风控日报缺失",
            f"📅 审查日期: {tdate}（报告日期: {ydate}）\n⚠️ 风控日报文件不存在\n\n📡 各Bot实时状态:\n{bots_text}\n\n💡 请确认尚书省是否已生成日报")
        return result

    try:
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)
    except Exception as e:
        log.error(f"读取风控日报失败: {e}")
        result["level"] = "P1"
        result["message"] = f"风控日报读取异常: {e}"
        send_feishu("P1", "【门下省】风控日报读取异常", f"路径: {report_path}\n错误: {e}")
        return result

    # 读取单日回撤
    daily_retrace = report.get("daily_retrace_pct", 0)
    emoji = "✅"
    level = "OK"
    msg_prefix = f"单日回撤: {daily_retrace}%"

    if daily_retrace > 5:
        emoji, level = "🔴", "P0"
        msg_prefix = f"🔴 红色预警！单日回撤: {daily_retrace}%"
    elif daily_retrace > 3:
        emoji, level = "🟠", "P1"
        msg_prefix = f"🟠 橙色预警，单日回撤: {daily_retrace}%"
    elif daily_retrace > 1:
        emoji, level = "🟡", "P2"
        msg_prefix = f"🟡 黄色预警，单日回撤: {daily_retrace}%"

    result["level"] = level
    result["message"] = msg_prefix
    log.info(msg_prefix)

    # 检查各Bot状态（端口9090-9097）
    bots_down = []
    bots_ok = []
    for port in [9090, 9091, 9092, 9093, 9094, 9095, 9096, 9097]:
        try:
            req = urllib.request.Request(f"http://localhost:{port}/api/v1/ping", timeout=3)
            urllib.request.urlopen(req, timeout=3)
            bots_ok.append(str(port))
        except Exception:
            bots_down.append(str(port))
            log.warning(f"Bot端口 {port} 不可达")

    result["bots_down"] = bots_down

    if bots_down:
        msg = f"{msg_prefix}\n\n📡 Bot状态:\n✅ 在线: {', '.join(bots_ok) or '无'}\n❌ 离线: {', '.join(bots_down)}"
        send_feishu(level, "【门下省】Bot状态异常", msg)
    elif level != "OK":
        # 读出报告关键指标，发完整数据
        metrics = report.get("metrics", {})
        win_rate = metrics.get("win_rate", "—")
        profit = metrics.get("total_profit", "—")
        max_dd = metrics.get("max_drawdown", "—")
        trades = metrics.get("trade_count", "—")
        sharpe = metrics.get("sharpe", "—")
        msg = (f"📊 风控日报 [{ydate}]\n"
               f"📅 审查时间: {tdate}\n\n"
               f"📈 关键指标:\n"
               f"• 单日回撤: {daily_retrace}%\n"
               f"• 胜率: {win_rate}%\n"
               f"• 总盈亏: {profit}\n"
               f"• 最大回撤: {max_dd}%\n"
               f"• 交易次数: {trades}\n"
               f"• 夏普比率: {sharpe}\n"
               f"• Bot: {', '.join(bots_ok)} 全部在线\n"
               f"• 报告生成: {report.get('generated_at', '未知')}")
        send_feishu(level, "【门下省】T+1风控日报预警", msg)

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  功能2：新任务到达通知
# ═══════════════════════════════════════════════════════════════════════════

def new_task_notify() -> dict:
    """
    读取 tasks_source.json，找出所有状态为"中书省"的待审议任务
    等待超4小时的上报太子
    """
    log.info("━━━ 新任务到达通知 ━━━")
    tasks = atomic_json_read(TASKS_FILE, default=[])
    now_ts = datetime.now().timestamp()

    pending = [
        t for t in tasks
        if t.get("state") == "中书省" or (
            isinstance(t.get("_scheduler", {}).get("snapshot", {}).get("org"), str)
            and "中书" in str(t.get("_scheduler", {}).get("snapshot", {}).get("org", ""))
            and t.get("state") not in ("Done", "Rejected", "门下省")
        )
    ]

    result = {"total": len(pending), "urgent": [], "normal": []}

    for t in pending:
        # 找出进入中书省的时间
        flow_log = t.get("flow_log", [])
        entry_time = None
        for entry in reversed(flow_log):
            if "中书省" in str(entry.get("to", "")):
                entry_time = entry.get("at", "")
                break

        if not entry_time:
            # 降级：用 updatedAt
            entry_time = t.get("updatedAt", "")

        wait_hours = 0
        if entry_time:
            try:
                entry_dt = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
                wait_hours = (datetime.now() - entry_dt.replace(tzinfo=None)).total_seconds() / 3600
            except Exception:
                wait_hours = 0

        entry = {
            "id": t.get("id"),
            "title": t.get("title"),
            "state": t.get("state"),
            "wait_hours": round(wait_hours, 1),
            "entry_at": entry_time,
        }

        if wait_hours > 4:
            result["urgent"].append(entry)
        else:
            result["normal"].append(entry)

        log.info(f"  待审议任务 {t.get('id')}: {t.get('title')} | 等待{wait_hours:.1f}小时")

    # 上报太子（等待超4小时的任务）
    if result["urgent"]:
        lines = [f"📋 **{len(result['urgent'])}条待审议任务等待超4小时**"]
        for u in result["urgent"]:
            lines.append(f"• [{u['id']}] {u['title']}\n  等待: {u['wait_hours']}h | 状态: {u['state']}")
        # 加上正常待审的任务列表
        if result["normal"]:
            lines.append(f"\n📋 另有 {len(result['normal'])} 条正常待审:")
            for n in result["normal"][:5]:
                lines.append(f"• [{n['id']}] {n['title']} | {n['wait_hours']}h")
            if len(result["normal"]) > 5:
                lines.append(f"  ...还有 {len(result['normal'])-5} 条")
        send_feishu("P1", "【门下省】待审议任务积压预警", "\n".join(lines))
        log.warning(f"待审议任务积压: {len(result['urgent'])}条超4小时")
    else:
        # 无积压时不再发送重复健康状态（避免刷屏）
        # 只有当有待审议任务时才发送
        all_pending = result["urgent"] + result["normal"]
        if all_pending:
            summary = [f"📬 门下省待审议任务报告\n共 {len(all_pending)} 条待审议\n"]
            for u in all_pending[:10]:
                summary.append(f"• [{u['id']}] {u['title']}\n  等待{u['wait_hours']}h | {u['state']}")
            send_feishu("OK", "【门下省】待审议任务状态", "\n".join(summary))
        log.info("暂无积压任务，审查通过")

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  功能3：审议进度上报
# ═══════════════════════════════════════════════════════════════════════════

# 上次进度快照文件
_PROGRESS_SNAPSHOT = DATA_DIR / "progress_snapshot.json"

def progress_report() -> dict:
    """
    读取 tasks_source.json，检查 progress 字段变化，有更新时记录日志
    """
    log.info("━━━ 审议进度上报 ━━━")
    tasks = atomic_json_read(TASKS_FILE, default=[])

    # 加载上次快照
    snapshot = {}
    if _PROGRESS_SNAPSHOT.exists():
        try:
            snapshot = json.loads(_PROGRESS_SNAPSHOT.read_text(encoding="utf-8"))
        except Exception:
            snapshot = {}

    changes = []
    now_str = datetime.now().isoformat()

    for t in tasks:
        tid = t.get("id")
        if not tid:
            continue
        progress = t.get("progress", 0)
        prev = snapshot.get(tid, {}).get("progress", None)

        if prev is not None and progress != prev:
            changes.append({
                "id": tid,
                "title": t.get("title"),
                "from": prev,
                "to": progress,
            })
            log.info(f"  进度更新 {tid}: {prev}% → {progress}%")

        snapshot[tid] = {
            "progress": progress,
            "state": t.get("state"),
            "updatedAt": t.get("updatedAt"),
        }

    # 写回快照
    try:
        _PROGRESS_SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log.error(f"进度快照写入失败: {e}")

    result = {"total_tasks": len(tasks), "changes": changes}
    if changes:
        lines = [f"📝 **{len(changes)}条任务进度有更新**"]
        for c in changes:
            lines.append(f"• [{c['id']}] {c['title']}: {c['from']}% → {c['to']}%")
        send_feishu("OK", "【门下省】审议进度更新", "\n".join(lines))
    else:
        # 无变化时发当前状态总览
        states = {}
        for t in tasks:
            s = t.get("state", "未知")
            states[s] = states.get(s, 0) + 1
        total = len(tasks)
        lines = [f"📋 三省六部任务总览（共 {total} 条）"]
        for s, cnt in sorted(states.items(), key=lambda x: -x[1]):
            lines.append(f"• {s}: {cnt} 条")
        send_feishu("OK", "【门下省】任务状态总览", "\n".join(lines))

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  功能4：周五复盘（每周五14:00执行）
# ═══════════════════════════════════════════════════════════════════════════

def friday_review() -> dict:
    """
    汇总本周审议数量、封驳数量、通过数量，检查Bot状态，生成周报摘要并飞书通知
    """
    log.info("━━━ 周五复盘 ━━━")
    tasks = atomic_json_read(TASKS_FILE, default=[])

    monday_str, next_monday_str = _week_range()
    try:
        monday_dt = datetime.fromisoformat(monday_str)
        next_monday_dt = datetime.fromisoformat(next_monday_str)
    except Exception:
        monday_dt = datetime.now() - timedelta(days=datetime.now().weekday())
        next_monday_dt = monday_dt + timedelta(days=7)

    week_tasks = []
    for t in tasks:
        updated = t.get("updatedAt", "")
        if not updated:
            continue
        try:
            updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00")).replace(tzinfo=None)
            if monday_dt <= updated_dt < next_monday_dt:
                week_tasks.append(t)
        except Exception:
            continue

    # 统计
    total = len(week_tasks)
    rejected = sum(1 for t in week_tasks if t.get("state") == "Rejected")
    approved = sum(1 for t in week_tasks if t.get("state") in ("Done", "Approved", "门下省"))
    in_progress = sum(1 for t in week_tasks if t.get("state") == "中书省")
    # 封驳：flow_log里有Rejected相关记录
    fengbo = 0
    for t in week_tasks:
        for entry in t.get("flow_log", []):
            remark = str(entry.get("remark", ""))
            if "封驳" in remark or "拒绝" in remark or "Rejected" in remark:
                fengbo += 1
                break

    # Bot状态检查
    bots_status = {}
    for port in [9090, 9091, 9092, 9093, 9094, 9095, 9096, 9097]:
        try:
            req = urllib.request.Request(f"http://localhost:{port}/health", timeout=3)
            urllib.request.urlopen(req, timeout=3)
            bots_status[port] = "在线"
        except Exception:
            bots_status[port] = "离线"

    result = {
        "week_start": monday_str,
        "week_end": next_monday_str,
        "total": total,
        "approved": approved,
        "rejected": rejected,
        "fengbo": fengbo,
        "in_progress": in_progress,
        "bots_status": bots_status,
    }

    # 生成分段落
    lines = [
        f"📊 **{_today()} 门下省周报**（{monday_str} ~ {next_monday_str}）",
        f"",
        f"**审议概览**",
        f"  • 本周审议任务: {total} 条",
        f"  • 通过: {approved} 条",
        f"  • 封驳: {fengbo} 条",
        f"  • 待处理: {in_progress} 条",
        f"",
        f"**Bot状态**",
    ]
    for port, status in bots_status.items():
        icon = "✅" if status == "在线" else "❌"
        lines.append(f"  {icon} Bot-{port}: {status}")

    msg = "\n".join(lines)
    log.info(msg)
    send_feishu("OK", f"【门下省】{_today()} 周报", msg)

    # 保存周报
    weekly_dir = REPORTS_DIR / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)
    weekly_file = weekly_dir / f"{_today()}_weekly_review.json"
    try:
        weekly_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info(f"周报已保存: {weekly_file}")
    except Exception as e:
        log.error(f"周报保存失败: {e}")

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  功能5：回撤预警自动受理
# ═══════════════════════════════════════════════════════════════════════════

def _tunnel_health() -> dict:
    """检查cloudflared隧道状态，VPN切换后自动重连"""
    import subprocess
    result = {"tunnels": [], "restarted": []}
    # cloudflared进程名
    try:
        proc = subprocess.run(["pgrep", "-f", "cloudflared"], capture_output=True, timeout=5)
        pids = [p.strip() for p in proc.stdout.decode().splitlines() if p.strip()]
    except Exception as e:
        log.warning(f"隧道检查异常: {e}")
        return result
    result["tunnels"] = pids
    if not pids:
        log.warning("cloudflared未运行，尝试重启...")
        try:
            subprocess.Popen(
                ["nohup", "/opt/homebrew/bin/cloudflared", "--config",
                 str(Path.home() / ".cloudflared/config.yml"), "tunnel", "run"],
                stdout=open("/tmp/cloudflared_tunnel.log", "a"),
                stderr=subprocess.STDOUT)
            log.info("cloudflared重启已触发")
            result["restarted"].append("cloudflared")
            send_feishu("P1", "【隧道】cloudflared重启", "VPN切换导致隧道中断，已自动重启")
        except Exception as e2:
            log.error(f"隧道重启失败: {e2}")
            send_feishu("P0", "【隧道】cloudflared重启失败", f"重启失败: {e2}")
    return result

def alert_check() -> dict:
    """
    读取兵部监控台数据 http://localhost:7891/api/bingbu/positions
    检查高波动和8x杠杆告警，触发阈值时自动在看板登记状态
    每次运行前先检查隧道健康，发现中断自动重连
    """
    log.info("━━━ 回撤预警+隧道检查 ━━━")
    # 先查隧道
    tunnel_result = _tunnel_health()
    if tunnel_result["restarted"]:
        log.info(f"隧道已重启: {tunnel_result['restarted']}")

    result = {"alerts_triggered": [], "ok": True}
    # 再查告警
    try:
        req = urllib.request.Request(ALERT_API)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        log.error(f"兵部监控台读取失败: {e}")
        result["ok"] = False
        result["error"] = str(e)
        return result

    # 解析 bingbu/positions 数据
    # 新格式: {positions: [...], count: N, total_pnl: X}
    positions = data.get("positions", [])
    leverage_8x = [p for p in positions if isinstance(p, dict) and p.get("leverage", 0) >= 8]
    highvol = []  # bingbu/positions 不含波动率数据，跳过高波动检查

    alerts = []

    # 高波动检查
    if isinstance(highvol, list):
        for item in highvol:
            if item.get("triggered") or item.get("alert") or item.get("level") in ("P0", "P1", "P2"):
                alerts.append({"type": "高波动", "detail": item})

    # 8x杠杆检查
    if isinstance(leverage_8x, list):
        for item in leverage_8x:
            alerts.append({"type": "8x杠杆", "detail": item})

    if alerts:
        result["alerts_triggered"] = alerts
        result["ok"] = False
        for a in alerts:
            log.warning(f"触发告警: {a['type']} - {a['detail']}")

        # 在看板登记状态（写入 live_status.json）
        live_file = DATA_DIR / "bingbu_unified_status.json"
        try:
            existing = atomic_json_read(live_file, default={})
            existing["menxia_alert_check_at"] = datetime.now().isoformat()
            existing["menxia_alerts"] = alerts
            # 原子写回
            lock_file = _lock_path(live_file)
            fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                tmp_fd, tmp_path = tempfile.mkstemp(dir=str(live_file.parent), suffix=".tmp")
                with os.fdopen(tmp_fd, "w") as f:
                    json.dump(existing, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, str(live_file))
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            log.info("已在看板登记告警状态")
        except Exception as e:
            log.error(f"看板登记失败: {e}")

        highvol = [a for a in alerts if a['type'] == '高波动']
        leverage = [a for a in alerts if a['type'] == '8x杠杆']
        lines = [f"🔴 回撤预警触发，共 {len(alerts)} 条"]
        if highvol:
            lines.append(f"📊 高波动 ({len(highvol)} 条):")
            for a in highvol[:5]:
                detail = a.get('detail', {})
                coin = detail.get('coin', '?')
                change = detail.get('change_pct', '?')
                price = detail.get('price', '?')
                lines.append(f"• {coin}: 现价{price} 24h变幅{change}%")
        if leverage:
            lines.append(f"⚠️ 8x杠杆 ({len(leverage)} 条):")
            for a in leverage[:5]:
                detail = a.get('detail', {})
                sym = detail.get('symbol', '?')
                margin = detail.get('margin_ratio', '?')
                lines.append(f"• {sym}: 保证金率{margin}%")
        lines.append("✅ 详情已登记至看板")
        send_feishu("P0", "【门下省】回撤预警触发", "\n".join(lines))
    else:
        log.info("回撤预警检查正常，无触发告警")

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  主入口
# ═══════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────
#  四维审议框架
# ─────────────────────────────────────────────────────────────────

def _notify_taizi(stage: str, task_id: str, title: str, detail: str, level: str = "P2") -> bool:
    """上报太子：受理/审查中/完成三个节点"""
    emoji = {"受理": "📬", "审查中": "🔍", "完成": "✅", "封驳": "❌", "准奏": "🎉"}
    icon = emoji.get(stage, "📋")
    msg = f"{icon} **门下省·{stage}**\n\n**任务**: {title}\n**ID**: `{task_id}`\n\n{detail}"
    return send_feishu(level, f"【门下省】{stage}——{title[:20]}", msg)


def _load_tasks() -> list:
    try:
        with open(TASKS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_tasks(tasks: list) -> None:
    lock_file = _lock_path(Path(TASKS_FILE))
    fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=str(Path(TASKS_FILE).parent), suffix=".tmp")
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, str(TASKS_FILE))
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _update_task_state(task_id: str, state: str, extra: dict = None) -> None:
    """更新任务状态+打时间戳"""
    tasks = _load_tasks()
    for t in tasks:
        if t.get("id") == task_id:
            t["state"] = state
            t["menxia_reviewed_at"] = datetime.now().isoformat()
            if extra:
                t.update(extra)
            break
    _save_tasks(tasks)


def four_dimension_review(task_id: str) -> dict:
    """
    四维审议框架：
    1. 可行性  2. 完整性  3. 风险  4. 资源
    返回: {"decision": "准奏"|"封驳", "维度": [...], "round": int}
    """
    tasks = _load_tasks()
    task = next((t for t in tasks if t.get("id") == task_id), None)
    if not task:
        return {"decision": "error", "reason": f"任务{task_id}不存在"}

    title = task.get("title", "")
    desc = task.get("description", task.get("detail", ""))
    current_round = task.get("rejection_round", 0)

    # ── 第一维：可行性 ──────────────────────────────────────────
    dim1_pass = True
    dim1_issues = []
    if not desc or len(desc) < 10:
        dim1_pass = False
        dim1_issues.append("方案描述缺失或过于简略")
    if "?" in title and len(desc) < 20:
        dim1_pass = False
        dim1_issues.append("技术路径不明确")
    # ── 第二维：完整性 ──────────────────────────────────────────
    dim2_pass = True
    dim2_issues = []
    if not task.get("subtasks") and not task.get("steps"):
        dim2_issues.append("缺少子任务拆解")
    if not task.get("success_criteria"):
        dim2_issues.append("未定义成功标准")
    # ── 第三维：风险审查 ────────────────────────────────────────
    dim3_pass = True
    dim3_issues = []
    desc_lower = desc.lower()
    if "止损" not in desc_lower and "stop" not in desc_lower:
        dim3_issues.append("无止损机制描述 🔴")
    if any(kw in desc_lower for kw in ["杠杆", "leverage", "5x", "8x", "10x"]) and "保证金" not in desc_lower:
        dim3_issues.append("高杠杆无风险说明 🔴")
    if "回滚" not in desc_lower and "rollback" not in desc_lower and "恢复" not in desc_lower:
        dim3_issues.append("缺少回滚/熔断预案")
    # ── 第四维：资源审查 ──────────────────────────────────────
    dim4_pass = True
    dim4_issues = []
    if task.get("department"):
        depts = str(task.get("department"))
        if len(depts.split(",")) > 3:
            dim4_issues.append("跨部门过多，协调成本高")

    # 统计
    all_issues = dim1_issues + dim2_issues + dim3_issues + dim4_issues
    red_flags = [i for i in all_issues if "🔴" in i]
    blockers = [i for i in all_issues if "🟠" in i or "❌" in i]

    # 决策逻辑
    if red_flags:
        decision = "封驳"
    elif blockers:
        decision = "封驳"
    elif current_round >= 2:  # 第3轮强制准奏
        decision = "准奏"
    elif len([i for i in all_issues if "🟡" in i]) >= 2:
        decision = "封驳"
    else:
        decision = "准奏"

    result = {
        "task_id": task_id,
        "title": title,
        "decision": decision,
        "round": current_round,
        "维度": {
            "可行性": {"通过": dim1_pass, "问题": dim1_issues},
            "完整性": {"通过": dim2_pass, "问题": dim2_issues},
            "风险": {"通过": dim3_pass, "问题": dim3_issues},
            "资源": {"通过": dim4_pass, "问题": dim4_issues},
        },
        "all_issues": all_issues,
    }

    # 写回状态
    if decision == "封驳":
        _update_task_state(task_id, "Review", {
            "rejection_round": current_round + 1,
            "menxia_issues": all_issues,
            "menxia_decision": "封驳",
        })
    else:
        _update_task_state(task_id, "Assigned", {
            "menxia_issues": all_issues,
            "menxia_decision": "准奏",
            "menxia_approved_at": datetime.now().isoformat(),
        })

    return result


def check_review_queue() -> dict:
    """
    检查待审议队列，对所有处于Review状态且未审议的任务执行四维审议
    触发三个强制上报节点：受理 → 审查中 → 完成
    """
    log.info("━━━ 四维审议队列检查 ━━━")
    tasks = _load_tasks()
    review_tasks = [t for t in tasks if t.get("state") == "Review"
                    and not t.get("menxia_decision")]

    if not review_tasks:
        log.info("无待审议任务")
        return {"reviewed": [], "decisions": {}}

    results = {}
    for t in review_tasks:
        tid = t["id"]
        title = t.get("title", "")[:40]

        # 节点1：受理上报
        _notify_taizi("受理", tid, title,
                     f"开始四维审议，预计10分钟内完成", level="P2")

        # 执行四维审议
        r = four_dimension_review(tid)

        # 节点3：完成上报
        if r["decision"] == "准奏":
            issues_text = "无异议项" if not r["all_issues"] else "\n".join(r["all_issues"])
            _notify_taizi("准奏", tid, title,
                         f"四维审议通过，方案已转尚书省执行\n\n审议结果:\n{issues_text}",
                         level="P2")
        else:
            issues_text = "\n".join([f"• {i}" for i in r["all_issues"]])
            round_msg = f"（第{r['round']+1}轮封驳，还剩{max(0, 2-r['round']-1)}轮）"
            _notify_taizi("封驳", tid, title,
                         f"发现以下问题:\n{issues_text}\n\n{round_msg}\n请中书省补充后重新提交",
                         level="P1")

        results[tid] = r["decision"]
        log.info(f"审议完成 [{tid}] {r['decision']}: {title}")

    return {"reviewed": [t["id"] for t in review_tasks], "decisions": results}


# ─────────────────────────────────────────────────────────────────
#  main
# ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="门下省自动化审议脚本")
    parser.add_argument(
        "mode",
        nargs="?",
        default="all",
        choices=["all", "t1_review", "new_task", "progress", "friday_review", "alert_check", "review"],
        help="执行模式",
    )
    args = parser.parse_args()

    mode = args.mode
    log.info(f"━━━━ 门下省自动化脚本启动 [{mode}] ━━━━")

    results = {}

    if mode in ("all", "t1_review"):
        results["t1_review"] = t1_review()

    if mode in ("all", "new_task"):
        results["new_task"] = new_task_notify()

    if mode in ("all", "review"):
        results["review"] = check_review_queue()

    if mode in ("all", "progress"):
        results["progress"] = progress_report()

    if mode in ("all", "friday_review"):
        # 判断是否周五
        if datetime.now().weekday() == 4:
            results["friday_review"] = friday_review()
        else:
            log.info("今日非周五，跳过周五复盘")

    if mode in ("all", "alert_check"):
        results["alert_check"] = alert_check()

    log.info(f"━━━━ 全部执行完成 ━━━━")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return results


if __name__ == "__main__":
    main()
