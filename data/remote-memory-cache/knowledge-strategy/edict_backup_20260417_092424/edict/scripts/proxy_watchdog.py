#!/usr/bin/env python3
"""
5020 代理看门狗
监控 OKX API 连通性 + 5020 代理状态
断开时自动重启代理进程 + 重启 OKX bot
"""
import json, os, signal, subprocess, sys, time, urllib.request
from datetime import datetime

LOG_FILE = "/tmp/proxy_watchdog.log"
OKX_API_TEST = "https://www.okx.com/api/v5/market/tickers?instType=SWAP"
PROXY = "http://127.0.0.1:5020"
OKX_BOT_PORTS = [9093, 9094, 9095, 9096, 9097]
OKX_BOT_PID_FILE = "/tmp/okx_bot.pid"
CHECK_INTERVAL = 60  # 每60秒检查一次
MAX_RETRIES = 3
RETRY_DELAY = 15

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def test_proxy_okx():
    """测试 5020 代理是否能连通 OKX API"""
    try:
        req = urllib.request.Request(OKX_API_TEST)
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status == 200:
                data = json.loads(r.read())
                if data.get("code") == "0":
                    return True, "OK"
    except Exception as e:
        pass
    # 不走代理测试（直连）
    try:
        import urllib.request
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
        req = urllib.request.Request(OKX_API_TEST)
        with opener.open(req, timeout=10) as r:
            if r.status == 200:
                return True, "直连OK"
    except:
        pass
    return False, "代理不通"

def get_okx_bot_pid(port: int):
    """获取指定端口 OKX bot PID"""
    pid_file = f"/tmp/okx_bot_{port}.pid"
    try:
        with open(pid_file) as f:
            return int(f.read().strip())
    except:
        pass
    # 尝试从ps查找
    result = subprocess.run(
        ["pgrep", "-f", f"freqtrade.*{port}"],
        capture_output=True, text=True
    )
    pids = [int(p) for p in result.stdout.strip().split("\n") if p]
    return pids[0] if pids else None

def get_all_okx_pids():
    """获取所有 OKX bot PID"""
    return {port: get_okx_bot_pid(port) for port in OKX_BOT_PORTS}

def is_process_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

OKX_BOT_OVERLAY_MAP = {
    9093: "/Users/luxiangnan/freqtrade/config_9093_overlay.json",
    9094: "/Users/luxiangnan/freqtrade/config_9094_overlay.json",
    9095: "/Users/luxiangnan/freqtrade/config_9095_overlay.json",
    9096: "/Users/luxiangnan/freqtrade/config_9096_overlay.json",
    9097: "/Users/luxiangnan/freqtrade/config_9097_overlay.json",
}

def restart_okx_bot(port: int):
    """重启指定端口的 OKX bot"""
    overlay = OKX_BOT_OVERLAY_MAP.get(port, OKX_BOT_OVERLAY_MAP[9093])
    log(f"重启 OKX bot :{port}...")
    try:
        pid = get_okx_bot_pid(port)
        if pid and is_process_alive(pid):
            os.kill(pid, signal.SIGTERM)
            time.sleep(3)
            try:
                os.kill(pid, signal.SIGKILL)
            except:
                pass
    except Exception as e:
        log(f"停止旧进程失败: {e}")

    # 获取 user_data_dir
    import json as _json
    try:
        with open(overlay) as f:
            cfg = _json.load(f)
        user_dir = cfg.get("user_data_dir", f"/Users/luxiangnan/freqtrade/user_data_okx_{port}")
    except:
        user_dir = f"/Users/luxiangnan/freqtrade/user_data_okx_{port}"

    env = os.environ.copy()
    env["HTTP_PROXY"] = PROXY
    env["HTTPS_PROXY"] = PROXY

    cmd = [
        sys.executable,
        "/Users/luxiangnan/freqtrade/.venv/bin/freqtrade",
        "trade",
        "-c", "/Users/luxiangnan/freqtrade/config_shared.json",
        "-c", overlay,
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
                cwd="/Users/luxiangnan/freqtrade"
            )
        with open(pid_file, "w") as f:
            f.write(str(proc.pid))
        log(f"OKX bot :{port} 重启成功 PID={proc.pid}")
        return True
    except Exception as e:
        log(f"启动 OKX bot :{port} 失败: {e}")
        return False

def restart_all_okx_bots():
    """重启所有 OKX bots"""
    for port in OKX_BOT_PORTS:
        restart_okx_bot(port)

def restart_proxy():
    """重启 5020 系统代理（networkserviceproxy）"""
    log("尝试重启 5020 代理...")
    # networkserviceproxy 是系统进程，不能直接杀
    # 尝试通过 networksetup 重启
    try:
        # 刷新网络配置
        subprocess.run(["networksetup", "-setautoproxyurl", "Wi-Fi", "http://127.0.0.1:5020"],
                     capture_output=True, timeout=10)
    except:
        pass
    log("代理重启完成（请手动检查 networkserviceproxy 状态）")

def check_okx_bot_status():
    """检查所有 OKX bot 是否正常运行"""
    results = {}
    for port in OKX_BOT_PORTS:
        try:
            req = urllib.request.Request(f"http://localhost:{port}/api/v1/ping")
            with urllib.request.urlopen(req, timeout=5) as r:
                results[port] = r.status == 200
        except:
            results[port] = False
    return results

def all_bots_alive(status_map):
    return all(status_map.values())

def main():
    log("5020 代理看门狗启动")
    consecutive_failures = 0

    while True:
        proxy_ok, proxy_msg = test_proxy_okx()
        bot_status = check_okx_bot_status()
        bot_alive = all_bots_alive(bot_status)

        if proxy_ok and bot_alive:
            if consecutive_failures > 0:
                log(f"✅ 恢复: 代理={proxy_msg}, 全部Bot正常")
            consecutive_failures = 0
        else:
            offline = [p for p, ok in bot_status.items() if not ok]
            consecutive_failures += 1
            log(f"⚠️ 检查失败 (连续{consecutive_failures}次): 代理={proxy_msg}, Bot离线={offline}")

            if consecutive_failures >= MAX_RETRIES:
                log("🚀 触发自动修复...")
                restart_proxy()
                time.sleep(RETRY_DELAY)
                if not bot_alive:
                    restart_all_okx_bots()
                    time.sleep(5)
                    new_status = check_okx_bot_status()
                    if all_bots_alive(new_status):
                        log("✅ 全部 OKX bot 重启成功")
                        consecutive_failures = 0
                    else:
                        still_down = [p for p, ok in new_status.items() if not ok]
                        log(f"⚠️ 部分Bot重启失败: {still_down}")
                        consecutive_failures = 0
                else:
                    log("⚠️ 代理已重启，Bot存活，等待恢复...")
                    consecutive_failures = 0

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
