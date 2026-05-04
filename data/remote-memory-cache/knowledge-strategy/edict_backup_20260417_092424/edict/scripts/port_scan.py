#!/usr/bin/env python3
"""
服务端口扫描看门狗 - 三层监控 + 分级告警 + 自动恢复
基于工部基础设施监控体系

L1: 进程存活检查 (CRITICAL - 进程死)
L2: 端口响应检查 (WARNING - 端口不通)
L3: 业务指标检查 (INFO - 响应慢)
"""

import subprocess
import json
import os
import time
from datetime import datetime
import sys
import urllib.request
import urllib.error

sys.path.insert(0, '/Users/luxiangnan/edict/scripts')

# ============================================================
# 配置
# ============================================================

# 飞书通知开关
NOTIFY_ENABLED = True

# 告警接收人（分级通知）
NOTIFY_CONFIG = {
    "CRITICAL": {"webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/oc_5016041d5ee6ed2a8cc4e98372569cec", "mention": "太子"},
    "WARNING":  {"webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/oc_5016041d5ee6ed2a8cc4e98372569cec", "mention": "太子"},
    "INFO":     {"webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/oc_5016041d5ee6ed2a8cc4e98372569cec", "mention": None},
}

# 阈值配置
THRESHOLDS = {
    "response_time_warn": 2.0,   # 秒 - 响应超时告警阈值
    "response_time_critical": 5.0,  # 秒 - 响应严重超时
    "restart_cooldown": 60,       # 秒 - 重启冷却时间（防止频繁重启）
}

# 全部需要监控的端口
PORTS = {
    7891: {"name": "三省六部系统", "check": "/", "restart": "cd /Users/luxiangnan/edict && nohup python3 -m uvicorn dashboard.server:app --host 127.0.0.1 --port 7891 > /Users/luxiangnan/edict/data/logs/edict.log 2>&1 &"},
    9090: {"name": "freqtrade-9090", "check": "/api/v1/ping", "restart": None, "process": None},  # 托管给launchd KeepAlive
    9091: {"name": "freqtrade-9091", "check": "/api/v1/ping", "restart": None, "process": None},  # 托管给launchd KeepAlive
    9092: {"name": "freqtrade-9092", "check": "/api/v1/ping", "restart": None, "process": None},  # 托管给launchd KeepAlive
    9093: {"name": "freqtrade-9093", "check": "/api/v1/ping", "restart": None, "process": None},  # 托管给launchd KeepAlive
    9094: {"name": "freqtrade-9094", "check": "/api/v1/ping", "restart": None, "process": None},  # 托管给launchd KeepAlive
    9095: {"name": "freqtrade-9095", "check": "/api/v1/ping", "restart": None, "process": None},  # 托管给launchd KeepAlive
    9096: {"name": "freqtrade-9096", "check": "/api/v1/ping", "restart": None, "process": None},  # 托管给launchd KeepAlive
    9097: {"name": "freqtrade-9097", "check": "/api/v1/ping", "restart": None, "process": None},  # 托管给launchd KeepAlive
    9099: {"name": "console_server", "check": "/", "restart": "cd /Users/luxiangnan/freqtrade_console && nohup python3 console_server.py > /Users/luxiangnan/edict/data/logs/console.log 2>&1 &"},
}

# 需要检查的进程 + 域名验证
PROCESSES = {
    "cloudflared": {
        "cmd": "cloudflared.*config-tianlu",
        "domains": [
            "openclaw.tianlu2026.org",
            "9090.tianlu2026.org", "9091.tianlu2026.org", "9092.tianlu2026.org", "9093.tianlu2026.org",
            "9094.tianlu2026.org", "9095.tianlu2026.org", "9096.tianlu2026.org", "9097.tianlu2026.org",
            "console.tianlu2026.org"
        ],
        "start": "cd ~/.cloudflared && nohup /opt/homebrew/bin/cloudflared --config config-tianlu.yml tunnel run aa05ab31-21df-4431-81bf-4ae6a98792fb >> /Users/luxiangnan/edict/data/logs/cloudflared.log 2>&1 &"
    },
}

# 状态记录（防止重复告警）
last_notify_time = {}
last_restart_time = {}

# ============================================================
# 飞书通知
# ============================================================

def notify(level, title, message, mention=None):
    """发送飞书通知 - 分级
    level: CRITICAL | WARNING | INFO
    """
    if not NOTIFY_ENABLED:
        return
    
    # 检查冷却时间（防止同一问题重复告警）
    now = time.time()
    key = f"{level}:{title}"
    if key in last_notify_time and now - last_notify_time[key] < 300:  # 5分钟内不重复
        print(f"[WATCHDOG] ⏳ 跳过重复通知 ({level}): {title}")
        return
    
    last_notify_time[key] = now
    
    cfg = NOTIFY_CONFIG.get(level, NOTIFY_CONFIG["INFO"])
    webhook = cfg["webhook"]
    
    # 告警级别emoji
    emoji = {"CRITICAL": "🚨", "WARNING": "⚠️", "INFO": "ℹ️"}.get(level, "📌")
    
    # 构建消息
    mention_text = f"@{mention}" if mention else ""
    layer = "看门狗"
    full_message = f"{emoji} 【工部{layer}告警 | {level}】\n\n📌 {title}\n{message}\n\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    if mention_text:
        full_message = f"{mention_text}\n\n{full_message}"
    
    try:
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "text": f"【工部{layer}告警】{title}"},
                    "template": {"CRITICAL": "red", "WARNING": "yellow", "INFO": "blue"}.get(level, "blue")
                },
                "elements": [
                    {"tag": "markdown", "content": full_message}
                ]
            }
        }
        
        req = urllib.request.Request(
            webhook,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=10)
        print(f"[WATCHDOG] ✅ 飞书通知已发送 [{level}]: {title}")
    except urllib.error.HTTPError as e:
        print(f"[WATCHDOG] ⚠️ 飞书HTTP错误: {e.code}")
    except Exception as e:
        print(f"[WATCHDOG] ⚠️ 飞书通知失败: {e}")


def notify_simple(title, message):
    """发送简单文本通知（兼容旧接口）"""
    if not NOTIFY_ENABLED:
        return
    try:
        webhook = NOTIFY_CONFIG["INFO"]["webhook"]
        payload = {
            "msg_type": "text",
            "content": {"text": f"🔔 【工部故障通知】\n\n📌 {title}\n{message}"}
        }
        req = urllib.request.Request(
            webhook,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[WATCHDOG] ⚠️ 飞书通知失败: {e}")


# ============================================================
# L1: 进程存活检查
# ============================================================

def check_process_l1(name, proc_info):
    """
    L1检查: 进程是否存活
    返回: (status, detail)
    status: "OK" | "DEAD" | "RUNNING"
    """
    result = subprocess.run(['pgrep', '-f', proc_info["cmd"]], capture_output=True)
    process_ok = result.returncode == 0
    
    if process_ok:
        return "RUNNING", "进程运行中"
    else:
        return "DEAD", "进程已停止"


# ============================================================
# L2: 端口响应检查
# ============================================================

def check_port_l2(port, check_path):
    """
    L2检查: 端口是否响应
    返回: (status, http_code, response_time)
    status: "OK" | "TIMEOUT" | "ERROR" | "SLOW"
    """
    start = time.time()
    try:
        r = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', f'http://localhost:{port}{check_path}'],
            capture_output=True, timeout=10
        )
        response_time = time.time() - start
        status_code = r.stdout.decode().strip()
        
        if status_code == '200':
            if response_time > THRESHOLDS["response_time_warn"]:
                return "SLOW", status_code, response_time
            return "OK", status_code, response_time
        else:
            return "ERROR", status_code, response_time
    except subprocess.TimeoutExpired:
        return "TIMEOUT", "000", 10.0
    except Exception as e:
        return "ERROR", "000", 0.0


# ============================================================
# L3: 业务指标检查
# ============================================================

def check_api_l3(port, check_path):
    """
    L3检查: API响应时间和业务指标
    返回: (status, detail)
    """
    start = time.time()
    try:
        r = subprocess.run(
            ['curl', '-s', '-w', '\\n%{time_total}', f'http://localhost:{port}{check_path}'],
            capture_output=True, timeout=15
        )
        response_time = time.time() - start
        lines = r.stdout.decode().strip().split('\n')
        http_code = lines[0] if lines else "000"
        time_total = float(lines[-1]) if len(lines) > 1 else response_time
        
        if http_code == '200':
            if time_total > THRESHOLDS["response_time_critical"]:
                return "CRITICAL_SLOW", f"响应时间 {time_total:.2f}s 严重超标"
            elif time_total > THRESHOLDS["response_time_warn"]:
                return "WARN_SLOW", f"响应时间 {time_total:.2f}s 偏慢"
            return "OK", f"响应时间 {time_total:.2f}s 正常"
        else:
            return "ERROR", f"HTTP {http_code}"
    except subprocess.TimeoutExpired:
        return "TIMEOUT", f"超时 > 15s"
    except Exception as e:
        return "ERROR", str(e)


# ============================================================
# 自动恢复
# ============================================================

def attempt_restart(port, info, reason):
    """
    尝试自动重启服务
    返回: True 重启成功, False 重启失败
    """
    # 检查冷却时间
    now = time.time()
    if port in last_restart_time and now - last_restart_time[port] < THRESHOLDS["restart_cooldown"]:
        print(f"[WATCHDOG] ⏳ 端口 {port} 冷却中，跳过重启")
        return False
    
    restart_cmd = info.get("restart")
    # 注意：freqtrade 由 launchd 托管 KeepAlive，不再通过 port_scan 自动重启
    if not restart_cmd:
        # freqtrade ports 跳过自动重启，launchd 会处理
        if "freqtrade" in info.get("name", "").lower():
            print(f"[WATCHDOG] ℹ️  {info['name']} ({port}) 由 launchd 托管，跳过自动重启")
            return False
    
    if not restart_cmd:
        print(f"[WATCHDOG] ❌ 端口 {port} 没有配置重启命令")
        return False
    
    last_restart_time[port] = now
    print(f"[WATCHDOG] 🔧 尝试重启 {info['name']} ({port}): {reason}")
    
    try:
        # 先杀掉可能残留的进程
        if info.get("process"):
            subprocess.run(['pkill', '-f', info["process"]], capture_output=True)
            time.sleep(1)
        
        # 执行重启
        subprocess.run(restart_cmd, shell=True, capture_output=True)
        time.sleep(5)  # 等待启动
        
        # 验证重启结果
        status, code, rt = check_port_l2(port, info.get("check", "/"))
        if status == "OK":
            print(f"[WATCHDOG] ✅ 端口 {port} 重启成功")
            return True
        else:
            print(f"[WATCHDOG] ❌ 端口 {port} 重启后仍异常: {status} ({code})")
            return False
    except Exception as e:
        print(f"[WATCHDOG] ❌ 端口 {port} 重启异常: {e}")
        return False


# ============================================================
# 主监控循环
# ============================================================

FAILED = []
RESTARTED = []
ALERT_STATS = {"CRITICAL": 0, "WARNING": 0, "INFO": 0}

print(f"[WATCHDOG] 🏛️ 工部看门狗启动 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"[WATCHDOG] 📊 监控层级: L1(进程) + L2(端口) + L3(API响应)")

# L1: 进程检查
print("\n=== L1: 进程存活检查 ===")
for name, proc_info in PROCESSES.items():
    status, detail = check_process_l1(name, proc_info)
    print(f"[L1] {name}: {status} - {detail}")
    
    if status == "DEAD":
        ALERT_STATS["CRITICAL"] += 1
        notify("CRITICAL", f"进程死亡: {name}", f"{detail}\n正在尝试重启...", "太子")
        
        # 尝试重启
        subprocess.run(['pkill', '-f', proc_info["cmd"]], capture_output=True)
        time.sleep(2)
        result = subprocess.run(proc_info["start"], shell=True, capture_output=True)
        time.sleep(10)
        
        # 验证
        new_status, _ = check_process_l1(name, proc_info)
        if new_status == "RUNNING":
            notify("INFO", f"进程已恢复: {name}", "自动重启成功")
            RESTARTED.append(name)
        else:
            notify("CRITICAL", f"进程恢复失败: {name}", "请人工干预！", "太子")

# L2 + L3: 端口和API检查
print("\n=== L2/L3: 端口响应检查 ===")
for port, info in PORTS.items():
    # L2: 端口检查
    status_l2, code, rt = check_port_l2(port, info.get("check", "/"))
    
    # 构建日志前缀
    rt_str = f"{rt*1000:.0f}ms"
    log_prefix = f"[L2] {info['name']} ({port}): {status_l2} ({code}) [{rt_str}]"
    
    if status_l2 == "OK":
        print(log_prefix)
        
        # L3: API响应时间检查
        if "api" in info.get("check", "/").lower() or port in [9090, 9091, 9092, 9093, 9094, 9095, 9096, 9097]:
            status_l3, detail = check_api_l3(port, info.get("check", "/"))
            if status_l3 in ["WARN_SLOW", "CRITICAL_SLOW"]:
                print(f"    └── [L3] {status_l3}: {detail}")
                ALERT_STATS["WARNING" if status_l3 == "WARN_SLOW" else "CRITICAL"] += 1
                if status_l3 == "CRITICAL_SLOW":
                    notify("WARNING", f"API响应慢: {info['name']}", detail)
    
    elif status_l2 == "SLOW":
        print(f"{log_prefix} ⚠️ 响应偏慢")
        ALERT_STATS["WARNING"] += 1
        # L2的SLOW暂不触发飞书通知（2-5s属于正常波动，7891等内部服务常见）
        # 等L3检查结果：只有L3确认CRITICAL_SLOW才发飞书
        # notify("WARNING", f"端口响应慢: {info['name']}", f"HTTP {code}, 响应时间 {rt_str}")
    
    elif status_l2 == "TIMEOUT":
        print(f"{log_prefix} ⏰ 超时")
        FAILED.append(port)
        ALERT_STATS["CRITICAL"] += 1
        
        # 尝试自动重启
        if attempt_restart(port, info, "端口超时无响应"):
            notify("INFO", f"端口已恢复: {info['name']}", f"自动重启成功，响应时间 {rt_str}")
            RESTARTED.append(port)
        else:
            notify("CRITICAL", f"端口故障: {info['name']}", f"HTTP {code}, 重启失败，请人工检查！", "太子")
    
    else:  # ERROR
        print(f"{log_prefix} ❌ 异常")
        FAILED.append(port)
        ALERT_STATS["WARNING"] += 1
        
        # 尝试自动重启
        if attempt_restart(port, info, f"端口返回 {code}"):
            notify("INFO", f"端口已恢复: {info['name']}", f"自动重启成功")
            RESTARTED.append(port)
        else:
            notify("WARNING", f"端口异常: {info['name']}", f"HTTP {code}, 重启未成功，需关注", "太子")

# 检查cloudflared隧道
print("\n=== 隧道健康检查 ===")
for name, proc_info in PROCESSES.items():
    status, detail = check_process_l1(name, proc_info)
    
    # 检查域名解析
    domain_ok = False
    for domain in proc_info.get("domains", []):
        try:
            r = subprocess.run(
                ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', f'https://{domain}'],
                capture_output=True, timeout=10
            )
            if r.stdout.decode().strip() == '200':
                domain_ok = True
                break
        except:
            pass
    
    if status == "RUNNING" and domain_ok:
        print(f"[TUNNEL] ✅ {name}: 进程+隧道正常")
    else:
        print(f"[TUNNEL] ⚠️ {name}: 进程{status}, 隧道{domain_ok}")
        ALERT_STATS["WARNING"] += 1
        notify("WARNING", f"隧道异常: {name}", f"进程:{status}, 隧道:{'正常' if domain_ok else '断开'}")

# 汇总
print(f"\n{'='*50}")
print(f"[WATCHDOG] 📊 监控汇总")
print(f"    告警统计: 🚨CRITICAL={ALERT_STATS['CRITICAL']} ⚠️WARNING={ALERT_STATS['WARNING']} ℹ️INFO={ALERT_STATS['INFO']}")
print(f"    异常端口: {FAILED if FAILED else '无'}")
print(f"    已恢复:   {RESTARTED if RESTARTED else '无'}")

if FAILED and not RESTARTED:
    print(f"[WATCHDOG] ⚠️ 端口宕机 {FAILED}，重启未成功，请人工检查")
    notify_simple("系统告警", f"端口宕机 {FAILED}，重启未成功")
elif not FAILED:
    print(f"[WATCHDOG] ✅ 全部正常")
print(f"{'='*50}\n")
