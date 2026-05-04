#!/usr/bin/env python3
"""
兵部综合看门狗 V5
同时监控：
  1. Cloudflare Tunnel 所有路由（10个域名）
  2. 各本地 Bot API（9090-9097）
  3. OpenClaw Gateway 本地健康
  4. 5020 代理 + OKX Bot
断开自动修复（每子系统最多重试2次），2次失败后停止修复，
转由子代理/私信通知人工干预。
飞书通知。
"""
import json, os, signal, subprocess, sys, time, urllib.request, urllib.error
from datetime import datetime

LOG_FILE = "/tmp/bingbu_watchdog.log"
CLOUDFLARED_PID_FILE = "/tmp/cloudflared.pid"
CLOUDFLARED_CONF = "/Users/luxiangnan/.cloudflared/config-tianlu.yml"
CLOUDFLARED_BIN = "/opt/homebrew/bin/cloudflared"
CHECK_INTERVAL = 30        # 每30秒检查一次
MAX_FAILURES = 3           # 连续3次检测失败才触发重启
MAX_RESTART_RETRIES = 2   # 最多自动重启2次，2次失败后停修复→通知人工
GRACE_PERIOD = 120        # Bot重启后120秒内跳过离线检测（等待初始化完成）
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"
FEISHU_COOLDOWN = 300     # 同一类型告警5分钟内不重复发
ALERT_STATE_FILE = "/tmp/bingbu_watchdog_alert_state.json"

PROXY = "http://127.0.0.1:5020"
OKX_API_TEST = "https://www.okx.com/api/v5/market/tickers?instType=SWAP"

# ── 全部 tunnel 路由 ────────────────────────────────────
TUNNEL_ROUTES = [
    ("openclaw",  "https://openclaw.tianlu2026.org/",         "http://localhost:7891/"),
    ("console",   "https://console.tianlu2026.org/",          "http://localhost:9099/"),
    ("9090",      "https://9090.tianlu2026.org",              "http://localhost:9090/api/v1/ping"),
    ("9091",      "https://9091.tianlu2026.org",              "http://localhost:9091/api/v1/ping"),
    ("9092",      "https://9092.tianlu2026.org",              "http://localhost:9092/api/v1/ping"),
    ("9093",      "https://9093.tianlu2026.org",              "http://localhost:9093/api/v1/ping"),
    ("9094",      "https://9094.tianlu2026.org",              "http://localhost:9094/api/v1/ping"),
    ("9095",      "https://9095.tianlu2026.org",              "http://localhost:9095/api/v1/ping"),
    ("9096",      "https://bhb16638759999.tianlu2026.org",   "http://localhost:9096/api/v1/ping"),
    ("9097",      "https://9097.tianlu2026.org",              "http://localhost:9097/api/v1/ping"),
]

ALL_BOT_PORTS = [9090, 9091, 9092, 9093, 9094, 9095, 9096, 9097]


# ══════════════════════════════════════════════════════════════════
def log(msg, level="INFO"):
    ts = datetime.now().strftime("%m-%d %H:%M:%S")
    icons = {"INFO": "ℹ️", "WARN": "⚠️", "OK": "✅", "ERR": "🚨", "OKX": "🤖"}
    line = f"[{ts}] {icons.get(level,'•')} {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


# ── 飞书通知 ──────────────────────────────────────────────
def load_alert_state() -> dict:
    try:
        with open(ALERT_STATE_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_alert_state(state: dict):
    with open(ALERT_STATE_FILE, "w") as f:
        json.dump(state, f)

def send_feishu_alert(kind: str, title: str, body: str, template: str = "red"):
    """发送飞书卡片通知，带防重复（同类告警 FEISHU_COOLDOWN 秒内不重发）"""
    state = load_alert_state()
    now = time.time()
    last = state.get(kind, 0)
    if now - last < FEISHU_COOLDOWN:
        log(f"[飞书] {kind} 冷却期，跳过", "INFO")
        return
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"【看门狗V5】{title}"},
                "template": template,
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": body}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}},
            ],
        },
    }
    try:
        import requests
        req = requests.Session()
        req.trust_env = False
        req.post(FEISHU_WEBHOOK, json=card, timeout=10)
        state[kind] = now
        save_alert_state(state)
        log(f"[飞书] ✅ 已发送: {title}", "OK")
    except Exception as e:
        log(f"[飞书] ❌ 发送失败: {e}", "ERR")


def send_manual_intervention_alert(subsystem: str, detail: str):
    """
    通知子代理/人工干预（2次重启失败后触发）
    不再尝试自动修复，直接通知人工
    """
    kind = f"manual_intervention_{subsystem}"
    state = load_alert_state()
    now = time.time()
    # 人工干预通知冷却10分钟（避免刷屏）
    if now - state.get(kind, 0) < 600:
        return
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"🚨 看门狗V5 人工干预请求"},
                "template": "red",
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": (
                    f"⚠️ **子系统: {subsystem}**\n\n"
                    f"连续2次自动修复失败，看门狗已停止自动修复。\n\n"
                    f"📋 **详情:**\n{detail}\n\n"
                    f"🔧 **请人工干预修复**\n\n"
                    f"@太子 请检查并手动启动相关服务"
                )}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}},
            ],
        },
    }
    try:
        import requests
        req = requests.Session()
        req.trust_env = False
        req.post(FEISHU_WEBHOOK, json=card, timeout=10)
        state[kind] = now
        save_alert_state(state)
        log(f"[飞书] 🚨 人工干预通知已发送: {subsystem}", "ERR")
    except Exception as e:
        log(f"[飞书] ❌ 人工干预通知失败: {e}", "ERR")


# ══════════════════════════════════════════════════════════════════
# 1. Cloudflare Tunnel 监控
# ══════════════════════════════════════════════════════════════════
def check_cloudflared_process() -> bool:
    """检查 cloudflared 进程是否存活"""
    try:
        with open(CLOUDFLARED_PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return True
    except:
        pass
    result = subprocess.run(
        ["pgrep", "-f", "cloudflared.*config-tianlu"],
        capture_output=True, text=True
    )
    pids = [int(p) for p in result.stdout.strip().split("\n") if p]
    if pids:
        with open(CLOUDFLARED_PID_FILE, "w") as f:
            f.write(str(pids[0]))
        return True
    return False



def check_tunnel(name: str, url: str, local_url: str) -> tuple:
    """检查单个 tunnel 路由是否可达（只检查本地端口，忽略公网URL以避免挂起）"""
    # 仅检查本地端口，大幅降低耗时（85s → 5s）
    # cloudflared 进程状态由 check_cloudflared_process() 独立监控
    try:
        req = urllib.request.Request(local_url, headers={"User-Agent": "TianluWatchdog/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return True, f"{name}=本地OK({r.status})"
    except urllib.error.HTTPError as e:
        return False, f"{name}=HTTP{e.code}"
    except Exception:
        return False, f"{name}=离线"


def check_all_tunnels() -> tuple:
    """检查所有 tunnel 路由，返回 (全部正常, 详情)"""
    results = []
    ok_count = 0
    for name, pub_url, local_url in TUNNEL_ROUTES:
        ok, msg = check_tunnel(name, pub_url, local_url)
        results.append(msg)
        if ok:
            ok_count += 1
    return ok_count == len(TUNNEL_ROUTES), f"{ok_count}/{len(TUNNEL_ROUTES)}正常 | " + " | ".join(results)


def check_local_gateway() -> bool:
    """检查 OpenClaw Gateway 本地健康"""
    try:
        with urllib.request.urlopen("http://localhost:18789/health", timeout=5) as r:
            return r.status == 200
    except:
        return False


def restart_cloudflared():
    """重启 cloudflared 隧道"""
    log("正在重启 Cloudflare Tunnel...", "WARN")
    try:
        result = subprocess.run(
            ["pgrep", "-f", "cloudflared.*config-tianlu"],
            capture_output=True, text=True
        )
        for pid_str in result.stdout.strip().split("\n"):
            if pid_str:
                try:
                    os.kill(int(pid_str), signal.SIGTERM)
                    log(f"已终止旧进程 PID={pid_str}")
                except:
                    pass
        time.sleep(3)
        subprocess.run(
            ["pkill", "-9", "-f", "cloudflared.*config-tianlu"],
            capture_output=True
        )
        time.sleep(2)
        env = os.environ.copy()
        env.pop("HTTP_PROXY", None)
        env.pop("HTTPS_PROXY", None)
        env.pop("http_proxy", None)
        env.pop("https_proxy", None)

        cmd = [
            CLOUDFLARED_BIN,
            "--config", CLOUDFLARED_CONF,
            "tunnel", "run",
            "aa05ab31-21df-4431-81bf-4ae6a98792fb"
        ]
        log_path = "/Users/luxiangnan/edict/data/logs/cloudflared.log"
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w") as lf:
            proc = subprocess.Popen(
                cmd, env=env, stdout=lf, stderr=subprocess.STDOUT,
                cwd="/Users/luxiangnan/.cloudflared"
            )
        with open(CLOUDFLARED_PID_FILE, "w") as f:
            f.write(str(proc.pid))
        log(f"Cloudflare Tunnel 重启成功 PID={proc.pid}", "OK")
        time.sleep(10)
        return True
    except Exception as e:
        log(f"重启 Cloudflare Tunnel 失败: {e}", "ERR")
        return False


# ══════════════════════════════════════════════════════════════════
# 2. 5020 代理 + OKX Bot 监控
# ══════════════════════════════════════════════════════════════════
def test_proxy_okx() -> tuple:
    """测试 5020 代理连通 OKX API"""
    try:
        proxy_handler = urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
        opener = urllib.request.build_opener(proxy_handler)
        req = urllib.request.Request(OKX_API_TEST, headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(req, timeout=10) as r:
            if r.status == 200:
                data = json.loads(r.read())
                if data.get("code") == "0":
                    return True, "OK"
    except:
        pass
    return False, "代理不通"


def check_bot(port: int) -> bool:
    """检查单个 Bot 是否存活"""
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/api/v1/ping", timeout=5) as r:
            return r.status == 200
    except:
        return False


def check_all_bots() -> str:
    """检查所有 Bot，返回状态"""
    results = []
    for port in ALL_BOT_PORTS:
        ok = check_bot(port)
        emoji = "🟢" if ok else "🔴"
        results.append(f"{emoji}{port}:{'在线' if ok else '离线'}")
    return " | ".join(results)


# ── Bot 重启 ──────────────────────────────────────────────
BOT_OVERLAY_MAP = {
    9090: "/Users/luxiangnan/freqtrade/config_9090_overlay.json",
    9091: "/Users/luxiangnan/freqtrade/config_9091_overlay.json",
    9092: "/Users/luxiangnan/freqtrade/config_9092_overlay.json",
    9093: "/Users/luxiangnan/freqtrade/config_9093_overlay.json",
    9094: "/Users/luxiangnan/freqtrade/config_9094_overlay.json",
    9095: "/Users/luxiangnan/freqtrade/config_9095_overlay.json",
    9096: "/Users/luxiangnan/freqtrade/config_9096_overlay.json",
    9097: "/Users/luxiangnan/freqtrade/config_9097_overlay.json",
}

OKX_BOT_OVERLAY_MAP = {
    9093: "/Users/luxiangnan/freqtrade/config_9093_overlay.json",
    9094: "/Users/luxiangnan/freqtrade/config_9094_overlay.json",
    9095: "/Users/luxiangnan/freqtrade/config_9095_overlay.json",
    9096: "/Users/luxiangnan/freqtrade/config_9096_overlay.json",
    9097: "/Users/luxiangnan/freqtrade/config_9097_overlay.json",
}

BOT_ACCOUNTS = {
    9090: "Gate-17656685222",
    9091: "Gate-85363904550",
    9092: "Gate-15637798222",
    9093: "OKX-15637798222",
    9094: "OKX-BOT85363904550",
    9095: "OKX-BOTa44056283",
    9096: "OKX-BHB16638759999",
    9097: "OKX-17656685222",
}


FT_PYTHON = "/Users/luxiangnan/freqtrade/.venv/bin/python3"

# PID文件路径（Gate bots 也用 PID 文件，避免误杀）
BOT_PID_FILES = {
    9090: "/tmp/gate_bot_9090.pid",
    9091: "/tmp/gate_bot_9091.pid",
    9092: "/tmp/gate_bot_9092.pid",
}

def _kill_bot_processes(port: int):
    """
    彻底清理指定端口的所有freqtrade进程（进程组+孤儿双保险）。
    旧逻辑缺陷：PID文件跟踪shell wrapper而非Python进程，导致旧Python变孤儿。
    新逻辑：先杀进程组，再扫孤儿，确保无残留。
    """
    log(f"[CLEANUP] 开始清理 Bot :{port} 相关进程...", "WARN")

    # 第一步：用 pgrep 找到所有相关进程
    result = subprocess.run(
        ["pgrep", "-f", f"freqtrade.*{port}"],
        capture_output=True, text=True
    )
    pids = [int(p) for p in result.stdout.strip().split("\n") if p]

    for pid in pids:
        try:
            # 尝试杀进程组（如果这是session leader）
            os.killpg(pid, signal.SIGTERM)
            log(f"[CLEANUP] SIGTERM进程组 PGID={pid}", "WARN")
        except (ProcessLookupError, OSError):
            pass

    time.sleep(1)

    # 强制杀残留
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass

    time.sleep(1)

    # 第二步：再次扫描，杀孤儿（已脱离进程组的Python进程）
    result2 = subprocess.run(
        ["pgrep", "-f", f"freqtrade.*{port}"],
        capture_output=True, text=True
    )
    orphan_pids = [int(p) for p in result2.stdout.strip().split("\n") if p]
    for pid in orphan_pids:
        try:
            log(f"[CLEANUP] 杀孤儿进程 PID={pid}", "WARN")
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass

    time.sleep(2)

    # 验证
    result3 = subprocess.run(
        ["pgrep", "-f", f"freqtrade.*{port}"],
        capture_output=True, text=True
    )
    remaining = [p for p in result3.stdout.strip().split("\n") if p]
    if remaining:
        log(f"[CLEANUP] ⚠️ 仍有残留进程: {remaining}，将强制再杀", "ERR")
        for pid_str in remaining:
            try:
                os.kill(int(pid_str), signal.SIGKILL)
            except:
                pass
        time.sleep(1)
    else:
        log(f"[CLEANUP] ✅ Bot :{port} 进程清理完毕", "OK")


def restart_bot(port: int) -> bool:
    """重启指定端口的 Freqtrade Bot（9090-9092 Gate bots）"""
    if port in (9093, 9094, 9095, 9096, 9097):
        return restart_okx_bot(port)

    overlay = BOT_OVERLAY_MAP.get(port)
    if not overlay:
        log(f"未知端口 {port}，无对应overlay配置", "ERR")
        return False

    log(f"正在重启 Bot :{port}...", "WARN")

    # 彻底清理旧进程（进程组+孤儿双保险）
    _kill_bot_processes(port)

    # 启动新进程（start_new_session=True 使其成为session leader，可用killpg整组杀）
    cmd = [
        FT_PYTHON,
        "/Users/luxiangnan/freqtrade/.venv/bin/freqtrade",
        "trade",
        "-c", "/Users/luxiangnan/freqtrade/config_shared.json",
        "-c", overlay,
    ]
    log_path = f"/tmp/ft_{port}.log"
    try:
        with open(log_path, "w") as lf:
            # start_new_session=True: 新进程成为session leader，后续可用killpg整组杀
            proc = subprocess.Popen(
                cmd,
                stdout=lf,
                stderr=subprocess.STDOUT,
                cwd="/Users/luxiangnan/freqtrade",
                start_new_session=True,
            )
        log(f"Bot :{port} 重启成功 PID={proc.pid} (session leader)", "OK")

        # 写入 PID 文件（记录 session leader PID，用于后续整组杀）
        pid_file = BOT_PID_FILES.get(port)
        if pid_file:
            with open(pid_file, "w") as f:
                f.write(str(proc.pid))
            log(f"[PID] 已更新 {pid_file} → {proc.pid}", "INFO")

        return True
    except Exception as e:
        log(f"Bot :{port} 重启失败: {e}", "ERR")
        return False


def restart_okx_bot(port: int = 9093) -> bool:
    """重启 OKX Bot（支持 9093-9097）— 使用进程组确保干净重启"""
    log(f"正在重启 OKX Bot :{port}...", "WARN")
    okx_overlay = OKX_BOT_OVERLAY_MAP.get(port, OKX_BOT_OVERLAY_MAP[9093])

    # 彻底清理旧进程（进程组+孤儿双保险）
    _kill_bot_processes(port)

    env = os.environ.copy()
    env["HTTP_PROXY"] = PROXY
    env["HTTPS_PROXY"] = PROXY
    import json as _json
    try:
        with open(okx_overlay) as f:
            cfg = _json.load(f)
        user_dir = cfg.get("user_data_dir", f"/Users/luxiangnan/freqtrade/user_data_okx_{port}")
    except:
        user_dir = f"/Users/luxiangnan/freqtrade/user_data_okx_{port}"

    cmd = [
        FT_PYTHON,
        "/Users/luxiangnan/freqtrade/.venv/bin/freqtrade",
        "trade",
        "-c", "/Users/luxiangnan/freqtrade/config_shared.json",
        "-c", okx_overlay,
        "--userdir", user_dir,
        "-s", "FOttStrategy",
    ]
    log_path = f"/tmp/ft_{port}.log"
    pid_file = f"/tmp/okx_bot_{port}.pid"
    try:
        with open(log_path, "w") as logf:
            proc = subprocess.Popen(
                cmd,
                env=env,
                stdout=logf,
                stderr=subprocess.STDOUT,
                cwd="/Users/luxiangnan/freqtrade",
                start_new_session=True,   # 成为session leader，可用killpg整组杀
            )
        with open(pid_file, "w") as f:
            f.write(str(proc.pid))
        log(f"OKX Bot :{port} 重启成功 PID={proc.pid} (session leader)", "OK")
        return True
    except Exception as e:
        log(f"OKX Bot :{port} 重启失败: {e}", "ERR")
        return False


# ══════════════════════════════════════════════════════════════════
# 3. 主循环
# ══════════════════════════════════════════════════════════════════
def main():
    log("兵部综合看门狗 V5 启动 ✅", "OK")
    log(f"监控: {[n for n,*_ in TUNNEL_ROUTES]} + 8个Bot + 5020代理", "INFO")

    # 启动时发存活通知
    send_feishu_alert(
        "startup",
        "看门狗V5已上线",
        f"🚀 天禄看门狗V5已启动\n"
        f"监控项目：\n"
        f"• Cloudflare Tunnel（10条路由）\n"
        f"• Freqtrade Bot × 8（9090-9097）\n"
        f"• OpenClaw Gateway\n"
        f"• 5020 代理 + OKX Bot\n\n"
        f"异常自动修复（最多2次）\n"
        f"2次失败后停止修复，通知人工干预",
        template="green"
    )

    # 每个子系统独立失败/重试计数
    tunnel_failures = 0
    tunnel_restart_retries = 0   # 隧道重启重试计数
    tunnel_stopped = False       # 隧道是否已停修复

    proxy_failures = 0
    proxy_restart_retries = 0
    proxy_stopped = False

    # bot重启重试计数 {port: retries}
    bot_restart_retries: dict[int, int] = {port: 0 for port in ALL_BOT_PORTS}
    bot_stopped: dict[int, bool] = {port: False for port in ALL_BOT_PORTS}
    bot_restart_time: dict[int, float] = {port: 0.0 for port in ALL_BOT_PORTS}  # grace period

    prev_offline_bots = set()

    while True:
        # ── 隧道检查 ──
        cf_ok = check_cloudflared_process()
        tunnel_all_ok, tunnel_status = check_all_tunnels()
        gateway_ok = check_local_gateway()

        # ── 代理+Bot检查 ──
        proxy_ok, proxy_msg = test_proxy_okx()
        bot_status = check_all_bots()

        # ══ 隧道状态 ══
        if tunnel_all_ok:
            if tunnel_failures > 0:
                log(f"隧道恢复 | Gateway:{'正常' if gateway_ok else '离线'} | Bot:{bot_status}", "OK")
                send_feishu_alert(
                    "tunnel_recover",
                    "隧道恢复",
                    f"✅ Cloudflare Tunnel 已恢复正常\nGateway: {'在线' if gateway_ok else '离线'}\nBot状态: {bot_status}",
                    template="green"
                )
            tunnel_failures = 0
            tunnel_restart_retries = 0
            tunnel_stopped = False
        else:
            tunnel_failures += 1
            log(f"隧道异常 #{tunnel_failures} | {tunnel_status}", "WARN")
            if tunnel_failures >= MAX_FAILURES:
                if tunnel_stopped:
                    # 已达重试上限，停止修复，通知人工
                    if tunnel_restart_retries >= MAX_RESTART_RETRIES:
                        log("隧道重启已达2次上限，停止自动修复，通知人工干预", "ERR")
                        send_manual_intervention_alert(
                            "Cloudflare Tunnel",
                            f"连续 {tunnel_failures} 次检测失败\n"
                            f"已自动重启 {tunnel_restart_retries} 次均未恢复\n"
                            f"详情: {tunnel_status}\n\n"
                            f"请人工检查 cloudflared 进程和隧道状态"
                        )
                else:
                    log("触发隧道自动修复...", "ERR")
                    send_feishu_alert(
                        "tunnel_break",
                        "🚨 隧道中断，强制重启",
                        f"⚠️ Cloudflare Tunnel 连续 {tunnel_failures} 次检查失败\n详情: {tunnel_status}\n\n🔧 正在执行强制重启...",
                        template="red"
                    )
                    ok = restart_cloudflared()
                    if not ok:
                        tunnel_restart_retries += 1
                        log(f"隧道重启失败 #{tunnel_restart_retries}", "ERR")
                        if tunnel_restart_retries >= MAX_RESTART_RETRIES:
                            tunnel_stopped = True
                            log("隧道重启已达2次上限，停止自动修复，通知人工干预", "ERR")
                            send_manual_intervention_alert(
                                "Cloudflare Tunnel",
                                f"重启第{tunnel_restart_retries}次失败\n详情: {tunnel_status}\n\n请人工干预"
                            )
                    tunnel_failures = 0

        # ══ 代理状态 ══
        if proxy_ok:
            if proxy_failures > 0:
                log(f"代理恢复: {proxy_msg} | Bot:{bot_status}", "OK")
                send_feishu_alert(
                    "proxy_recover",
                    "代理恢复",
                    f"✅ 5020代理 已恢复正常\n{proxy_msg}\nBot: {bot_status}",
                    template="green"
                )
            proxy_failures = 0
            proxy_restart_retries = 0
            proxy_stopped = False
        else:
            proxy_failures += 1
            log(f"代理异常 #{proxy_failures}: {proxy_msg} | Bot:{bot_status}", "WARN")
            if proxy_failures >= MAX_FAILURES:
                if proxy_stopped:
                    if proxy_restart_retries >= MAX_RESTART_RETRIES:
                        log("代理重启已达2次上限，停止自动修复，通知人工干预", "ERR")
                        send_manual_intervention_alert(
                            "5020 代理",
                            f"连续 {proxy_failures} 次检测失败\n"
                            f"已自动重启 {proxy_restart_retries} 次均未恢复\n"
                            f"详情: {proxy_msg}\n\n"
                            f"请人工检查 5020 代理服务"
                        )
                else:
                    log("触发OKX Bot自动重启...", "ERR")
                    send_feishu_alert(
                        "proxy_break",
                        "🤖 代理中断，强制重启OKX Bot",
                        f"⚠️ 5020代理连续 {proxy_failures} 次检查失败\n详情: {proxy_msg}\nBot: {bot_status}\n\n🔧 正在重启 OKX Bot...",
                        template="orange"
                    )
                    ok = restart_okx_bot()
                    if ok:
                        # 代理故障重启会影响所有OKX bots，记录grace period
                        for p in (9093, 9094, 9095, 9096, 9097):
                            bot_restart_time[p] = now_ts
                    if not ok:
                        proxy_restart_retries += 1
                        if proxy_restart_retries >= MAX_RESTART_RETRIES:
                            proxy_stopped = True
                            log("代理重启已达2次上限，停止自动修复，通知人工干预", "ERR")
                            send_manual_intervention_alert(
                                "5020 代理 + OKX Bot",
                                f"重启第{proxy_restart_retries}次失败\n详情: {proxy_msg}\n\n请人工干预"
                            )
                    proxy_failures = 0

        # ══ Bot 离线检测 ══
        now_ts = time.time()
        offline_bots = []
        for port in ALL_BOT_PORTS:
            # Grace period：重启后120秒内跳过检测，等待Bot初始化完成
            if now_ts - bot_restart_time.get(port, 0) < GRACE_PERIOD:
                continue
            if not check_bot(port):
                offline_bots.append(port)

        current_offline = set(offline_bots)
        new_offline = current_offline - prev_offline_bots
        recovered = prev_offline_bots - current_offline

        if new_offline:
            for port in new_offline:
                if bot_stopped.get(port, False):
                    # 已停修复，通知人工
                    retries = bot_restart_retries.get(port, 0)
                    log(f"Bot :{port} 已停修复，通知人工干预（重启失败{retries}次）", "ERR")
                    send_manual_intervention_alert(
                        f"Bot {BOT_ACCOUNTS.get(port, port)}",
                        f"Bot :{port} 离线\n"
                        f"已自动重启 {retries} 次均未恢复\n\n"
                        f"请人工检查 Bot 进程和日志"
                    )
                else:
                    bot_str = "/".join(map(str, [port]))
                    log(f"Bot掉线: {port}", "ERR")
                    send_feishu_alert(
                        "bot_offline",
                        f"🤖 Bot掉线: {BOT_ACCOUNTS.get(port, port)}",
                        f"⚠️ Bot :{port} 无响应\n账号: {BOT_ACCOUNTS.get(port, port)}\n\n🔧 正在尝试重启...",
                        template="red"
                    )
                    ok = restart_bot(port)
                    if ok:
                        bot_restart_time[port] = now_ts   # 记录重启时间，grace period生效
                    if not ok:
                        bot_restart_retries[port] = bot_restart_retries.get(port, 0) + 1
                        if bot_restart_retries[port] >= MAX_RESTART_RETRIES:
                            bot_stopped[port] = True
                            log(f"Bot :{port} 重启失败已达2次，停止自动修复，通知人工干预", "ERR")
                            send_manual_intervention_alert(
                                f"Bot {BOT_ACCOUNTS.get(port, port)}",
                                f"Bot :{port} 重启第{bot_restart_retries[port]}次失败\n\n请人工干预"
                            )

        if recovered:
            recovered_str = "/".join(map(str, recovered))
            log(f"Bot恢复: {recovered}", "OK")
            send_feishu_alert(
                "bot_recover",
                f"✅ Bot恢复: {recovered_str}",
                f"✅ 以下Bot已恢复在线:\n" + "\n".join([f"• :{p} → 🟢在线" for p in sorted(recovered)]),
                template="green"
            )
            # 恢复后重置该bot的重试计数
            for port in recovered:
                bot_restart_retries[port] = 0
                bot_stopped[port] = False

        prev_offline_bots = current_offline

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
