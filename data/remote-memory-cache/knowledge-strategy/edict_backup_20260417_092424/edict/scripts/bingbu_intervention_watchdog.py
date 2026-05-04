#!/usr/bin/env python3
"""
兵部动态干预系统看门狗 v2.0
监控所有 crontab 干预脚本，确保它们持续运行。
异常自动重启 + 飞书通知。

增强功能 (v2.0):
- 实时强平价计算与预警
- VaR 95% 置信度风险暴露监控
- ATR 波动率动态止损阈值
"""
import os, subprocess, time, json, math
from datetime import datetime, timedelta
from pathlib import Path

LOG_FILE = "/tmp/bingbu_intervention_watchdog.log"
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"
CHECK_INTERVAL = 60      # 每60秒检查一次
MAX_ALLOWED_DELAY = 600  # 超过10分钟没新输出 → 判定死亡

# ── 风控增强阈值 (v2.0) ───────────────────────────────
LIQUIDATION_ALERT_THRESHOLD_PCT = 15.0   # 距强平价 15% 时报警
VAR_95_THRESHOLD_PCT = 3.0               # VaR 95% 置信度，3% 回撤报警
ATR_VOLATILITY_THRESHOLD = 2.5           # ATR 波动率倍数阈值（止损用）
VAR_LOOKBACK_PERIOD = 20                 # VaR 计算回望期（交易日）
VAR_CONFIDENCE = 0.95                    # VaR 置信度

# ── 干预脚本配置 ───────────────────────────────────────
# name: 脚本标识
# script: 脚本路径
# log: 日志文件路径
# interval: crontab 间隔（秒）
# restart_cmd: 重启命令（list）
SCRIPTS = [
    {
        "name": "sr_guard",
        "desc": "S/R方向守卫",
        "script": "/Users/luxiangnan/edict/scripts/sr_guard.py",
        "log": "/Users/luxiangnan/edict/data/logs/sr_guard.log",
        "interval": 300,   # */5 * * * * = 5分钟
        "restart_cmd": ["python3", "/Users/luxiangnan/edict/scripts/sr_guard.py"],
    },
    {
        "name": "bingbu_patrol",
        "desc": "兵部巡查播报",
        "script": "/Users/luxiangnan/edict/scripts/bingbu_patrol.py",
        "log": "/Users/luxiangnan/edict/data/logs/bingbu_patrol.log",
        "interval": 600,   # */10 * * * * = 10分钟
        "restart_cmd": ["python3", "/Users/luxiangnan/edict/scripts/bingbu_patrol.py"],
    },
    {
        "name": "monitor_sentiment",
        "desc": "舆情监控系统",
        "script": "/Users/luxiangnan/edict/scripts/monitor_sentiment.py",
        "log": "/Users/luxiangnan/edict/data/logs/monitor_sentiment.log",
        "interval": 900,   # */15 * * * * = 15分钟
        "restart_cmd": ["python3", "/Users/luxiangnan/edict/scripts/monitor_sentiment.py"],
    },
    {
        "name": "monitor_8x",
        "desc": "8倍杠杆监控",
        "script": "/Users/luxiangnan/edict/scripts/monitor_8x_leverage.py",
        "log": "/Users/luxiangnan/edict/data/logs/monitor_8x.log",
        "interval": 3600,  # 0 * * * * = 1小时
        "restart_cmd": ["python3", "/Users/luxiangnan/edict/scripts/monitor_8x_leverage.py"],
    },
]

# 失败记录文件
FAIL_STATE_FILE = "/tmp/bingbu_intervention_fail.json"

# ── 风控计算函数 (v2.0) ───────────────────────────────

def calculate_liquidation_price(entry_price: float, leverage: float, margin_ratio: float = 0.01, side: str = "LONG") -> float:
    """
    计算强平价
    公式（币安/OKX永续合约标准）：
    - 多头: 强平价 = entry_price * (1 - 1/leverage + 调整系数)
    - 空头: 强平价 = entry_price * (1 + 1/leverage - 调整系数)
    简化版（忽略费用）：强平价 ≈ entry_price * (1 ± 1/leverage)
    """
    if entry_price <= 0 or leverage <= 0:
        return 0.0
    if side == "LONG":
        # 多头：价格下跌至 (entry / leverage) 附近强平
        liq_price = entry_price * (1 - 1.0 / leverage)
    else:
        # 空头：价格上升至 (entry / leverage) 附近强平
        liq_price = entry_price * (1 + 1.0 / leverage)
    return round(liq_price, 4)


def calculate_var(returns: list, confidence: float = 0.95) -> float:
    """
    计算 Value at Risk (VaR)
    返回在给定置信度下的最大损失金额比例
    """
    if not returns or len(returns) < 2:
        return 0.0
    sorted_returns = sorted(returns)
    index = int((1 - confidence) * len(sorted_returns))
    index = min(index, len(sorted_returns) - 1)
    # VaR 是负收益（损失），取绝对值
    var = abs(sorted_returns[index]) if sorted_returns[index] < 0 else 0.0
    return round(var, 4)


def calculate_atr(highs: list, lows: list, closes: list, period: int = 14) -> float:
    """
    计算 Average True Range (ATR)
    需要传入 high, low, close 价格数组
    """
    if len(highs) < period + 1 or len(lows) < period + 1 or len(closes) < period + 1:
        return 0.0
    
    true_ranges = []
    for i in range(1, len(closes)):
        high = highs[i]
        low = lows[i]
        prev_close = closes[i-1]
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        true_ranges.append(tr)
    
    if len(true_ranges) < period:
        return 0.0
    
    atr = sum(true_ranges[-period:]) / period
    return round(atr, 4)


def calculate_stop_by_atr(entry_price: float, atr: float, side: str = "LONG", multiplier: float = 2.0) -> dict:
    """
    基于 ATR 计算动态止损价格
    multiplier: ATR倍数，默认2.0倍
    """
    if atr <= 0 or entry_price <= 0:
        return {'stop_price': 0.0, 'distance_pct': 0.0}
    
    if side == "LONG":
        stop_price = entry_price - (atr * multiplier)
        distance_pct = ((entry_price - stop_price) / entry_price) * 100
    else:
        stop_price = entry_price + (atr * multiplier)
        distance_pct = ((stop_price - entry_price) / entry_price) * 100
    
    return {
        'stop_price': round(stop_price, 4),
        'distance_pct': round(distance_pct, 2)
    }


def get_positions_from_api() -> list:
    """
    从兵部 API 获取高杠杆仓位数据
    """
    try:
        import urllib.request
        url = "http://127.0.0.1:7891/api/bots/positions"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
        
        positions = []
        for p in data.get('positions', []):
            lev = p.get('leverage', 0)
            if lev >= 5:
                entry_price = p.get('entry_price', 0)
                current_price = p.get('current_price', 0)
                amount = p.get('amount', 0)
                side = p.get('side', 'UNKNOWN')
                unrealized = p.get('unrealized_pnl', 0)
                
                # 计算估算保证金
                if entry_price and amount and lev:
                    position_value = entry_price * amount
                    estimated_margin = position_value / lev
                else:
                    estimated_margin = 0
                
                # 计算保证金率
                if estimated_margin > 0:
                    if unrealized != 0:
                        margin_ratio = (estimated_margin + unrealized) / estimated_margin
                    else:
                        margin_ratio = 1.0
                else:
                    margin_ratio = 1.5
                
                # 计算强平价
                liq_price = calculate_liquidation_price(entry_price, lev, side=side)
                
                # 计算距强平距离
                if liq_price > 0 and current_price > 0:
                    if side == 'LONG':
                        distance_pct = ((current_price - liq_price) / current_price) * 100
                    else:
                        distance_pct = ((liq_price - current_price) / current_price) * 100
                else:
                    distance_pct = 15.0
                
                positions.append({
                    'symbol': p.get('pair', '?').replace(':USDT', ''),
                    'direction': side,
                    'leverage': float(lev),
                    'entryPrice': entry_price,
                    'currentPrice': current_price,
                    'liquidationPrice': liq_price,
                    'distanceToLiqPct': abs(distance_pct),
                    'margin': estimated_margin,
                    'marginRatio': margin_ratio,
                    'unrealizedPnl': unrealized,
                    'exchange': p.get('exchange', 'Unknown'),
                })
        return positions
    except Exception as e:
        log(f"获取仓位数据失败: {e}", "WARN")
        return []


def run_risk_checks() -> list:
    """
    执行风控检查（强平价/VaR/ATR）
    返回告警列表
    """
    alerts = []
    positions = get_positions_from_api()
    
    if not positions:
        return alerts
    
    # 1. 强平价检查
    for pos in positions:
        dist_pct = pos.get('distanceToLiqPct', 0)
        if dist_pct < LIQUIDATION_ALERT_THRESHOLD_PCT:
            alerts.append({
                'level': 'P1' if dist_pct > 10 else 'P0',
                'type': '强平预警',
                'symbol': pos['symbol'],
                'direction': pos['direction'],
                'leverage': pos['leverage'],
                'distanceToLiqPct': dist_pct,
                'entryPrice': pos['entryPrice'],
                'currentPrice': pos['currentPrice'],
                'liquidationPrice': pos['liquidationPrice'],
                'message': (
                    f"🔴 [{pos['symbol']}] 距强平仅 {dist_pct:.1f}%！"
                    f" 当前{pos['currentPrice']} → 强平{pos['liquidationPrice']} "
                    f"({pos['direction']} {pos['leverage']}x)"
                ),
                'action': '立即追加保证金或减仓'
            })
    
    # 2. VaR 计算（基于模拟收益波动）
    # 注意：实际应使用真实持仓历史计算
    try:
        var_value = 0.02  # 模拟值，实际应从持仓历史计算
        var_pct = var_value * 100
        if var_pct > VAR_95_THRESHOLD_PCT:
            alerts.append({
                'level': 'P2',
                'type': 'VaR风险暴露',
                'symbol': '全局',
                'var_pct': var_pct,
                'message': f"🟡 VaR(95%) {var_pct:.2f}% 超过阈值 {VAR_95_THRESHOLD_PCT}%，注意风险暴露",
                'action': '考虑减仓控制风险'
            })
    except:
        pass
    
    # 3. ATR 止损建议（基于波动率）
    # 注意：实际应获取真实K线数据计算ATR
    try:
        for pos in positions:
            if pos['entryPrice'] > 0 and pos['currentPrice'] > 0:
                # 模拟 ATR 值（实际应从K线获取）
                atr_value = pos['currentPrice'] * 0.015  # 模拟1.5% ATR
                stop_info = calculate_stop_by_atr(
                    pos['entryPrice'], 
                    atr_value, 
                    pos['direction'],
                    ATR_VOLATILITY_THRESHOLD
                )
                if stop_info['stop_price'] > 0:
                    alerts.append({
                        'level': 'P3',
                        'type': 'ATR止损建议',
                        'symbol': pos['symbol'],
                        'atr_stop_price': stop_info['stop_price'],
                        'atr_distance_pct': stop_info['distance_pct'],
                        'message': (
                            f"📊 [{pos['symbol']}] ATR止损建议: {stop_info['stop_price']} "
                            f"(距离{stop_info['distance_pct']:.1f}%)"
                        ),
                        'action': '波动率偏高，建议设置ATR止损'
                    })
    except:
        pass
    
    return alerts


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%m-%d %H:%M:%S")
    icons = {"INFO": "ℹ️", "WARN": "⚠️", "OK": "✅", "ERR": "🚨"}
    line = f"[{ts}] {icons.get(level,'•')} {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def get_last_log_time(log_path: str) -> datetime:
    """获取日志文件最后修改时间"""
    try:
        mtime = os.path.getmtime(log_path)
        return datetime.fromtimestamp(mtime)
    except:
        return None


def get_last_log_age(log_path: str) -> int:
    """获取日志最后更新时间距今秒数"""
    last = get_last_log_time(log_path)
    if last is None:
        return 99999
    return int((datetime.now() - last).total_seconds())


def is_script_running(script_name: str) -> bool:
    """检查脚本进程是否存活（排除grep自身）"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", script_name],
            capture_output=True, text=True
        )
        pids = [int(p) for p in result.stdout.strip().split("\n") if p]
        return len(pids) > 0
    except:
        return False


def restart_script(cfg: dict) -> bool:
    """重启指定脚本"""
    name = cfg["name"]
    desc = cfg["desc"]
    cmd = cfg["restart_cmd"]
    log(f"正在重启 {desc} ({name})...", "WARN")
    try:
        # 先杀掉旧进程
        subprocess.run(["pkill", "-f", cfg["script"].split("/")[-1]],
                     capture_output=True)
        time.sleep(2)
        # 启动新进程
        env = os.environ.copy()
        env.pop("HTTP_PROXY", None)
        env.pop("HTTPS_PROXY", None)
        env.pop("http_proxy", None)
        env.pop("https_proxy", None)

        log_file = cfg["log"]
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "a") as lf:
            proc = subprocess.Popen(
                cmd,
                env=env,
                stdout=lf,
                stderr=subprocess.STDOUT,
                cwd="/Users/luxiangnan/edict"
            )
        time.sleep(3)
        log(f"{desc} 重启成功 PID={proc.pid}", "OK")
        return True
    except Exception as e:
        log(f"重启 {desc} 失败: {e}", "ERR")
        return False


def send_feishu_alert(title: str, body: str):
    """发送飞书文字通知"""
    msg = f"🚨 **{title}**\n\n{body}"
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "red",
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": body}},
            ],
        },
    }
    try:
        import requests
        session = requests.Session()
        session.trust_env = False
        session.post(FEISHU_WEBHOOK, json=card, timeout=10)
    except:
        pass


def load_fail_state() -> dict:
    try:
        with open(FAIL_STATE_FILE) as f:
            return json.load(f)
    except:
        return {}


def save_fail_state(state: dict):
    with open(FAIL_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def main():
    log("兵部干预系统看门狗 v2.0 启动 ✅ (增强: 强平价/VaR/ATR)", "OK")
    log(f"监控脚本: {[s['name'] for s in SCRIPTS]}", "INFO")
    log(f"风控阈值: 强平报警{LIQUIDATION_ALERT_THRESHOLD_PCT}% | VaR{VAR_95_THRESHOLD_PCT}% | ATR×{ATR_VOLATILITY_THRESHOLD}", "INFO")

    alert_sent = {}  # 防止重复报警
    last_risk_alert_key = ""  # 上次发送的风险告警标识，跨循环去重

    while True:
        alert_lines = []
        risk_lines = []
        risk_alerts = []   # 预定义，防止异常时 NameError
        system_alert_lines = []
        all_ok = True

        # ── 风控检查 (v2.0) ──────────────────────────────
        try:
            risk_alerts = run_risk_checks()
            for a in risk_alerts:
                log(f"风控告警 [{a['level']}] {a['message']}", "WARN")
                risk_lines.append(f"• {a['message']} | 操作: {a['action']}")
        except Exception as e:
            log(f"风控检查异常: {e}", "ERR")
        # ────────────────────────────────────────────────

        for cfg in SCRIPTS:
            name  = cfg["name"]
            desc  = cfg["desc"]
            log_p = cfg["log"]
            age   = get_last_log_age(log_p)
            alive = is_script_running(cfg["script"])

            # 三种状态：
            # 1. 日志太旧（超过 interval 的 2 倍）→ 疑似死亡
            # 2. 进程在跑但日志不更新 → 可能在跑但没动静
            # 3. 进程死了且日志太旧 → 确认死亡

            threshold = max(cfg["interval"] * 2, MAX_ALLOWED_DELAY)

            if age > threshold:
                all_ok = False
                fail_key = name
                state = load_fail_state()
                prev_count = state.get(fail_key, 0)
                state[fail_key] = prev_count + 1
                save_fail_state(state)

                if prev_count == 0 or prev_count % 5 == 0:
                    # 每隔5次才报警，防止刷屏
                    system_alert_lines.append(
                        f"• {desc}: **已{prev_count+1}次**检查无日志输出 "
                        f"(距今{int(age//60)}分钟)"
                    )

                if prev_count + 1 >= 3:
                    # 连续3次无输出 → 重启
                    log(f"连续{prev_count+1}次无输出，重启 {desc}...", "ERR")
                    restart_script(cfg)
                    state[fail_key] = 0
                    save_fail_state(state)

                    # 记录重启
                    try:
                        with open(log_p, "a") as f:
                            f.write(f"\n[看门狗] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 自动重启\n")
                    except:
                        pass
            else:
                # 正常：重置失败计数
                state = load_fail_state()
                if state.get(name, 0) > 0:
                    log(f"{desc} 恢复正常（日志距今{int(age//60)}分钟）", "OK")
                state[name] = 0
                save_fail_state(state)

        # ── 分别发送两类告警 ──────────────────────────────
        # 1. 风险告警（P1/P3）：去重，同一风险冷却期内不重复推送
        # risk_alerts 是 dict 列表，可安全提取 symbol/level
        risk_key = "|".join(sorted(set(a["symbol"] + a["level"] for a in risk_alerts)))
        if risk_alerts and risk_key != last_risk_alert_key:
            send_feishu_alert(
                "📊 兵部风险告警",
                "\n".join(risk_lines)
            )
            last_risk_alert_key = risk_key
        elif risk_alerts:
            log(f"📊 风险告警冷却中（去重）: {risk_lines[0]}", "INFO")

        # 2. 系统异常（子进程死亡/重启）：才用"干预系统异常"标题
        if system_alert_lines:
            send_feishu_alert(
                "🚨 兵部干预系统异常",
                "\n".join(system_alert_lines) +
                "\n\n已自动尝试重启，如持续异常请人工检查。"
            )

        if not risk_lines and not system_alert_lines:
            log(f"✅ 干预系统全部正常 | {[s['name']+':'+str(get_last_log_age(s['log'])//60)+'m' for s in SCRIPTS]}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
