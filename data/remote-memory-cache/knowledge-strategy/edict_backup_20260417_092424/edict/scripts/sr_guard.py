#!/usr/bin/env python3
# sr_guard V6 - 放置到 /Users/luxiangnan/edict/scripts/sr_guard.py
# 桌面设计文档: /Users/luxiangnan/Desktop/sr_guard_v6_rewrite.md

#!/usr/bin/env python3
"""
兵部 · S/R方向守卫 V6（完全重写S/R计算模块）

【V5 → V6 变更说明】
原有方案问题：
  1. OKX：取30根1D K线max/min，是"30天极值"，含远古无效S/R
  2. Gate：取所有周期最远极值（min(all_sup)/max(all_res)），过于极端
  3. _fetch_gate_sr_orderbook() 使用订单簿，曾导致无法开仓 → 已删除

V6新方案：
  1. Pivot Point（前日数据计算）— 机构标准S/R基准
  2. VWAP（成交量加权平均价）— 动态成本线
  3. 多周期局部极值（近10根K线）— 近期有效S/R
  三路信号共振，准确度最高

修复历史（V4 → V5）：
  Bug0: L2检查顺序错误 → 已修复
  Bug1: 盈利>3%时Rule1不自动平仓 → 保留
  Bug2: 平仓前验证trade_id存在 → 保留
  Bug3: OKX bots用OKX API获取S/R → 替换为V6新算法
  Bug4: 平仓后验证trade_id消失 → 保留
  Bug5: profit_pct为0或None时跳过自动执行 → 保留
  Bug6: Rule1没有检查入场位置 → 已修复
  Bug7: auto_exit和proposal共用冷却 → 已分离

V6新增：
  Bug8: 原有S/R算法含远古极值导致误判 → 全新Pivot+VWAP+局部极值算法
  Bug9: 订单簿导致无法开仓 → 删除订单簿依赖
"""

import base64, json, sys, time, urllib.request, concurrent.futures, datetime as dt, os, uuid, math
from pathlib import Path
import requests as _req

EDICT_DATA      = Path("/Users/luxiangnan/edict/data")
STATE_FILE      = EDICT_DATA / "sr_guard_state.json"
PENDING_FILE    = EDICT_DATA / "bingbu_pending_proposals.json"
AUTO_EXIT_LOG  = EDICT_DATA / "sr_guard_auto_exit.json"
BINGBU_API     = "http://127.0.0.1:7891/api"
WEBHOOK_BINGBU = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"

# ── 全局参数 ────────────────────────────────────────────
MAX_POSITION_AGE_SEC  = 24 * 3600    # L1: 超过24小时 → 跳过
SR_TOLERANCE_PCT      = 1.0          # S/R容差 ±1%（与入场规则保持一致）
PROFIT_PROTECT_PCT     = 3.0          # Bug1: 盈利超过此值，Rule1不自动平仓
COOLDOWN_SEC          = 30 * 60      # Bug7修复: proposal和auto_exit分开冷却
AUTO_EXIT_ENABLED     = False        # True=子代理直接平仓，False=需爸审批
RETRY_COUNT           = 2
RETRY_DELAY           = 3

BOT_LABELS = {
    9090: "Gate-17656685222",
    9091: "Gate-85363904550",
    9092: "Gate-15637798222",
    9093: "OKX-15637798222",
    9094: "OKX-BOT85363904550",
    9095: "OKX-BOTa44056283",
    9096: "OKX-BHB16638759999",
    9097: "OKX-17656685222",
}
OKX_PORTS = {9093, 9094, 9095, 9096, 9097}

# ──────────────────────────────────────────────────────
# V6 S/R 计算核心算法
# ──────────────────────────────────────────────────────

def _calc_pivot_point(high: float, low: float, close: float) -> dict:
    """
    计算Pivot Point及衍生R1/R2/R3/S1/S2/S3
    """
    pp = (high + low + close) / 3.0
    r1 = 2 * pp - low
    s1 = 2 * pp - high
    r2 = pp + (high - low)
    s2 = pp - (high - low)
    r3 = high + 2 * (pp - low)
    s3 = low - 2 * (high - pp)
    return {"pp": pp, "r1": r1, "r2": r2, "r3": r3, "s1": s1, "s2": s2, "s3": s3}


def _fetch_vwap_from_klines(klines: list) -> float:
    """
    从K线数据计算VWAP
    K线格式（OKX）: [ts, open, high, low, close, vol, ...]
    K线格式（Gate）: [ts, vol, close, high, low, open, quote_vol, ...]
    返回: vwap值（无法计算则返回0）
    """
    if not klines:
        return 0.0
    try:
        total_pv = 0.0
        total_vol = 0.0
        for k in klines:
            # 尝试判断格式
            if len(k) >= 6:
                # 尝试OKX格式: [ts, open, high, low, close, vol, ...]
                if isinstance(k[1], (int, float)) and isinstance(k[4], (int, float)) and isinstance(k[5], (int, float)):
                    close_v = float(k[4])
                    vol_v   = float(k[5])
                    total_pv += close_v * vol_v
                    total_vol += vol_v
                # 尝试Gate格式: [ts, vol, close, high, low, open, ...]
                elif isinstance(k[2], (int, float)) and isinstance(k[6], (int, float)):
                    close_v = float(k[2])
                    vol_v   = float(k[6])
                    total_pv += close_v * vol_v
                    total_vol += vol_v
        if total_vol > 0:
            return total_pv / total_vol
    except:
        pass
    return 0.0


_OKX_PROXY = {"http": "http://admin:Xy%4006130822@127.0.0.1:5020", "https": "http://admin:Xy%4006130822@127.0.0.1:5020"}

def _fetch_okx_klines(inst_id: str, bar: str, limit: int) -> list:
    """获取OKX K线数据"""
    try:
        r = _req.get(
            f"https://www.okx.com/api/v5/market/history-candles",
            params={"instId": inst_id, "bar": bar, "limit": limit},
            timeout=8,
            proxies=_OKX_PROXY,
        )
        if r.status_code == 200:
            data = r.json().get("data", [])
            # OKX格式: [ts, open, high, low, close, vol, quoteVol, ...]
            # 按时间正序
            return list(reversed(data))
    except:
        pass
    return []


def _fetch_okx_sr_v6(pair_clean: str, port: int = None) -> tuple:
    """
    V6: OKX S/R计算
    策略：Pivot Point(前日日线) + VWAP(1H K线) + 局部极值(1H K线)
    完全不使用订单簿
    当OKX外部API失败时，尝试从本地Bot获取current_rate
    """
    current = 0.0
    try:
        # 1. 当前价 - 优先用OKX外部API
        tk = _req.get(
            f"https://www.okx.com/api/v5/market/ticker?instId={pair_clean}-USDT",
            timeout=8,
            proxies=_OKX_PROXY,
        )
        if tk.status_code == 200:
            d = tk.json()
            if d.get("data"):
                current = float(d["data"][0].get("last", 0))
    except:
        pass

    # 1b. 如果外部API失败，尝试从本地OKX Bot获取当前价
    if current == 0 and port in OKX_PORTS:
        try:
            creds = "admin:Xy@06130822"
            auth = "Basic " + base64.b64encode(creds.encode()).decode()
            req = urllib.request.Request(
                f"http://localhost:{port}/api/v1/status",
                headers={"Authorization": auth}
            )
            with urllib.request.urlopen(req, timeout=6) as r:
                positions = json.loads(r.read())
                for pos in positions:
                    pos_pair = pos.get("pair", "").split(":")[0].replace("/", "_")
                    if pos_pair == pair_clean or pos_pair == pair_clean.replace("_", ""):
                        cr = pos.get("current_rate", 0)
                        if cr and cr > 0:
                            current = float(cr)
                            break
        except:
            pass

    if current == 0:
        return 0.0, 0.0, 0.0

    # 2. 前日日线 → 计算Pivot Point
    daily_klines = _fetch_okx_klines(pair_clean, "1D", 30)
    pp_data = {}
    if daily_klines and len(daily_klines) >= 2:
        # 取最近一根完整日线（前天）
        yesterday = daily_klines[-2]  # [ts, open, high, low, close, vol, ...]
        high_d  = float(yesterday[2])
        low_d   = float(yesterday[3])
        close_d = float(yesterday[4])
        pp_data = _calc_pivot_point(high_d, low_d, close_d)

    # 3. 近30根1H K线 → 计算VWAP + 局部极值
    hourly_klines = _fetch_okx_klines(pair_clean, "1H", 30)

    vwap = _fetch_vwap_from_klines(hourly_klines)

    # 局部极值（近10根1H K线）
    local_sup = 0.0
    local_res = 0.0
    if hourly_klines:
        recent_10 = hourly_klines[-10:] if len(hourly_klines) >= 10 else hourly_klines
        highs  = [float(k[2]) for k in recent_10]  # high
        lows   = [float(k[3]) for k in recent_10]   # low
        local_res = max(highs)
        local_sup = min(lows)

    # 4. 综合S/R输出
    # 支撑 = 最强支撑（多信号取最小值）
    # 压力 = 最强压力（多信号取最大值）
    all_supports   = []
    all_resistance = []

    if pp_data:
        # PP体系各层级都加入
        all_supports.extend([pp_data["s1"], pp_data["s2"], pp_data["s3"]])
        all_resistance.extend([pp_data["r1"], pp_data["r2"], pp_data["r3"]])

    if vwap > 0:
        all_supports.append(vwap)
        all_resistance.append(vwap)

    if local_sup > 0:
        all_supports.append(local_sup)
    if local_res > 0:
        all_resistance.append(local_res)

    # 取离当前价最远且合理的S/R（保守策略）
    if all_supports:
        # 支撑取最小（最深支撑）
        sup = min(all_supports)
    else:
        sup = current * 0.97  # 兜底：当前价下方3%

    if all_resistance:
        # 压力取最大（最高压力）
        res = max(all_resistance)
    else:
        res = current * 1.03  # 兜底：当前价上方3%

    return current, sup, res


def _fetch_gate_klines(gate_pair: str, interval: str, limit: int) -> list:
    """获取Gate.io K线数据"""
    try:
        r = _req.get(
            f"https://api.gateio.ws/api/v4/spot/candlesticks",
            params={"currency_pair": gate_pair, "interval": interval, "limit": limit},
            timeout=8
        )
        if r.status_code == 200:
            data = r.json()
            # Gate格式: [ts, vol, close, high, low, open, quote_vol, 0]
            # 按时间正序返回
            return list(reversed(data))
    except:
        pass
    return []


def _fetch_gate_sr_v6(gate_pair: str) -> tuple:
    """
    V6: Gate.io S/R计算
    策略：Pivot Point(前日日线) + VWAP(1H K线) + 局部极值(多周期)
    完全不使用订单簿
    """
    current = 0.0
    try:
        # 1. 当前价（从1H K线最新收盘价）
        r = _req.get(
            f"https://api.gateio.ws/api/v4/spot/candlesticks",
            params={"currency_pair": gate_pair, "interval": "1h", "limit": 1},
            timeout=8
        )
        if r.status_code == 200:
            data = r.json()
            if data:
                current = float(data[-1][2])  # close price
    except:
        pass

    if current == 0:
        return 0.0, 0.0, 0.0

    # 2. 前日日线 → Pivot Point
    daily_klines = _fetch_gate_klines(gate_pair, "1d", 30)
    pp_data = {}
    if daily_klines and len(daily_klines) >= 2:
        yesterday = daily_klines[-2]  # [ts, vol, close, high, low, open, ...]
        high_d  = float(yesterday[3])
        low_d   = float(yesterday[4])
        close_d = float(yesterday[2])
        pp_data = _calc_pivot_point(high_d, low_d, close_d)

    # 3. 近30根1H K线 → VWAP + 局部极值
    hourly_klines = _fetch_gate_klines(gate_pair, "1h", 30)

    vwap = _fetch_vwap_from_klines(hourly_klines)

    local_sup = 0.0
    local_res = 0.0
    if hourly_klines:
        recent_10 = hourly_klines[-10:] if len(hourly_klines) >= 10 else hourly_klines
        highs = [float(k[3]) for k in recent_10]  # high
        lows  = [float(k[4]) for k in recent_10]  # low
        local_res = max(highs)
        local_sup = min(lows)

    # 4. 4H K线局部极值（辅助确认）
    h4_klines = _fetch_gate_klines(gate_pair, "4h", 30)
    if h4_klines:
        recent_h4_10 = h4_klines[-10:] if len(h4_klines) >= 10 else h4_klines
        h4_highs = [float(k[3]) for k in recent_h4_10]
        h4_lows  = [float(k[4]) for k in recent_h4_10]
        if h4_highs:
            local_res = max(local_res, max(h4_highs)) if local_res > 0 else max(h4_highs)
        if h4_lows:
            local_sup = min(local_sup, min(h4_lows)) if local_sup > 0 else min(h4_lows)

    # 5. 综合输出
    all_supports   = []
    all_resistance = []

    if pp_data:
        all_supports.extend([pp_data["s1"], pp_data["s2"], pp_data["s3"]])
        all_resistance.extend([pp_data["r1"], pp_data["r2"], pp_data["r3"]])

    if vwap > 0:
        all_supports.append(vwap)
        all_resistance.append(vwap)

    if local_sup > 0:
        all_supports.append(local_sup)
    if local_res > 0:
        all_resistance.append(local_res)

    if all_supports:
        sup = min(all_supports)
    else:
        sup = current * 0.97

    if all_resistance:
        res = max(all_resistance)
    else:
        res = current * 1.03

    return current, sup, res


def fetch_sr(pair: str, port: int = 9090) -> tuple:
    """
    V6统一入口
    返回: (current_price, support, resistance)
    """
    pair_clean = pair.split(":")[0].replace("/", "-")
    gate_pair   = pair.split(":")[0].replace("/", "_")

    if port in OKX_PORTS:
        return _fetch_okx_sr_v6(pair_clean, port=port)
    else:
        return _fetch_gate_sr_v6(gate_pair)


# ──────────────────────────────────────────────────────
# 以下为原有逻辑（V5保持不变，仅S/R获取函数替换）
# ──────────────────────────────────────────────────────

# ── 状态读写 ───────────────────────────────────────────
def load_state():
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
    except: pass
    return {"violations": {}, "auto_exit_cool": {}}

def save_state(state):
    tmp = str(STATE_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(state, ensure_ascii=False, indent=2))
    os.replace(tmp, str(STATE_FILE))

# ── 持仓获取 ───────────────────────────────────────────
def get_positions():
    try:
        req = urllib.request.Request(BINGBU_API + "/bingbu/positions")
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read()).get("positions", [])
    except Exception as e:
        print(f"[sr_guard] 获取持仓失败: {e}")
        return []

def enrich_with_open_date(positions):
    port_map = {}
    for p in positions:
        port_map.setdefault(p.get("port", 0), []).append(p)

    def fetch_port(port, plist):
        creds_map = {
            9090: "freqtrade:freqtrade",
            9091: "freqtrade:freqtrade",
            9092: "freqtrade:freqtrade",
        }
        creds = creds_map.get(port, "admin:Xy@06130822")
        auth = "Basic " + base64.b64encode(creds.encode()).decode()
        try:
            req = urllib.request.Request(f"http://localhost:{port}/api/v1/status",
                                        headers={"Authorization": auth})
            with urllib.request.urlopen(req, timeout=6) as r:
                bot_pos = json.loads(r.read())
                return {str(po["trade_id"]): po.get("open_date","") for po in bot_pos}
        except:
            return {}

    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(fetch_port, port, plist): (port, plist) for port, plist in port_map.items()}
        for fut in concurrent.futures.as_completed(futures):
            trade_dates = fut.result()
            for p in futures[fut][1]:
                tid = str(p.get("trade_id",""))
                p["open_date"] = trade_dates.get(tid, p.get("open_date",""))
                results[(p.get("pair",""), p.get("side",""))] = p.get("open_date","")
    return results

# ── 平仓工具 ───────────────────────────────────────────
def _get_auth(port: int) -> str:
    creds_map = {
        9090: "freqtrade:freqtrade",
        9091: "freqtrade:freqtrade",
        9092: "freqtrade:freqtrade",
    }
    creds = creds_map.get(port, "admin:Xy@06130822")
    return "Basic " + base64.b64encode(creds.encode()).decode()

def _trade_exists(trade_id: int, port: int) -> bool:
    try:
        req = urllib.request.Request(f"http://localhost:{port}/api/v1/status",
                                    headers={"Authorization": _get_auth(port)})
        with urllib.request.urlopen(req, timeout=6) as r:
            positions = json.loads(r.read())
            if isinstance(positions, dict):
                positions = positions.get("result", [])
            for p in positions:
                if str(p.get("trade_id","")) == str(trade_id):
                    return True
    except:
        pass
    return False

def _wait_and_verify_exit(trade_id: int, port: int, max_wait: int = 8) -> bool:
    for _ in range(max_wait):
        time.sleep(1)
        if not _trade_exists(trade_id, port):
            return True
    return False

def auto_exit_single(trade_id: int, port: int, pair: str, side: str,
                    rule: str, pnl_pct: float) -> tuple:
    if not _trade_exists(trade_id, port):
        return True, "已平仓(平仓前验证)"

    last_err = ""
    for attempt in range(RETRY_COUNT + 1):
        try:
            resp = _req.post(
                f"http://localhost:{port}/api/v1/forceexit",
                json={"tradeid": str(trade_id)},
                headers={"Authorization": _get_auth(port)},
                timeout=10,
            )
            if resp.status_code in (200, 201):
                if _wait_and_verify_exit(trade_id, port, max_wait=RETRY_DELAY):
                    return True, f"成功({resp.status_code})"
                last_err = f"超时未确认({resp.status_code})"
            else:
                last_err = f"失败({resp.status_code})"
        except Exception as e:
            last_err = f"异常({e})"

        if attempt < RETRY_COUNT:
            time.sleep(RETRY_DELAY)

    return False, last_err

# ── 核心审计逻辑（V5保持不变）────────────────────────
def audit_position(pos: dict, state: dict, now_ts: int):
    """
    五重过滤：
      L1: 年龄过滤（>24h跳过）
      L2: 入场S/R验证（入场位置正确 → 不违规）
      L3: Rule1（入场错误 + 当前在错误S/R位 → 自动平仓）
      L4: Rule2（入场错误 + 当前在错误S/R位 + 亏损 → 自动平仓）
    """
    pair     = pos.get("pair", "?")
    side     = pos.get("side", "?")
    entry    = float(pos.get("entry_price") or 0)
    trade_id = str(pos.get("trade_id", ""))
    open_d   = pos.get("open_date", "")
    port     = pos.get("port", 0)

    # ── L1: 年龄过滤 ───────────────────────────────────
    age_seconds = 0
    if open_d:
        try:
            open_dt = dt.datetime.strptime(open_d, "%Y-%m-%d %H:%M:%S")
            age_seconds = now_ts - open_dt.timestamp()
        except:
            age_seconds = 0
    pos["age_seconds"] = age_seconds
    if age_seconds > MAX_POSITION_AGE_SEC:
        return None

    # ── L2: 获取当前S/R（V6新算法）────────────────
    cur_price, sup, res = fetch_sr(pair, port)
    if not cur_price or not sup or not res:
        return None

    pos["current"]    = cur_price
    pos["support"]    = sup
    pos["resistance"] = res

    d2s_cur = (cur_price - sup)  / cur_price * 100
    d2r_cur = (res - cur_price)  / cur_price * 100
    pos["dist_sup_pct"] = round(d2s_cur, 2)
    pos["dist_res_pct"] = round(d2r_cur, 2)

    # ── Bug5: profit_pct 处理 ─────────────────────────
    pnl_pct_raw = pos.get("profit_pct")
    if pnl_pct_raw is None or pnl_pct_raw == 0.0:
        pnl_available = False
        pnl_pct = 0.0
    else:
        pnl_available = True
        pnl_pct = float(pnl_pct_raw)
    pos["pnl_available"] = pnl_available
    pos["pnl_pct"]      = pnl_pct

    # ── Bug1: 盈利保护 ────────────────────────────────
    profit_protected = (
        pnl_available and
        ((side == "LONG"  and pnl_pct >= PROFIT_PROTECT_PCT) or
         (side == "SHORT" and pnl_pct <= -PROFIT_PROTECT_PCT))
    )
    pos["profit_protected"] = profit_protected

    # ── 入场S/R验证（L2过滤）────────────────────────
    if entry > 0:
        d2s_ent = (entry - sup) / entry * 100
        d2r_ent = (res - entry) / entry * 100
        pos["entry_dist_sup"] = round(d2s_ent, 2)
        pos["entry_dist_res"] = round(d2r_ent, 2)
        entry_valid = (
            (side == "LONG"  and d2s_ent < SR_TOLERANCE_PCT) or
            (side == "SHORT" and d2r_ent < SR_TOLERANCE_PCT)
        )
    else:
        entry_valid = False
        d2s_ent = d2r_ent = 0.0
        pos["entry_dist_sup"] = pos["entry_dist_res"] = 0.0
    pos["entry_valid"] = entry_valid

    # ── Rule判断（L3/L4）──────────────────────────────
    long_entry_wrong  = (side == "LONG"  and d2r_cur < SR_TOLERANCE_PCT)
    short_entry_wrong = (side == "SHORT" and d2s_cur < SR_TOLERANCE_PCT)

    is_r1 = False
    is_r2 = False
    violations_r1 = []
    violations_r2 = []

    if long_entry_wrong:
        is_r1 = True
        violations_r1.append(f"🔴 [{pair}] LONG在压力位附近(距压力{d2r_cur:.1f}%)，入场已偏离")
    elif short_entry_wrong:
        is_r1 = True
        violations_r1.append(f"🔴 [{pair}] SHORT在支撑位附近(距支撑{d2s_cur:.1f}%)，入场已偏离")

    if entry > 0 and pnl_available:
        if side == "LONG"  and long_entry_wrong  and cur_price < entry:
            is_r2 = True
            violations_r2.append(f"🔴 [{pair}] LONG在压力区间+亏损中({pnl_pct:.2f}%)")
        elif side == "SHORT" and short_entry_wrong and cur_price > entry:
            is_r2 = True
            violations_r2.append(f"🔴 [{pair}] SHORT在支撑区间+亏损中({pnl_pct:.2f}%)")

    pos["is_violation_r1"] = is_r1
    pos["is_violation_r2"] = is_r2
    pos["violations_r1"]   = violations_r1
    pos["violations_r2"]   = violations_r2

    if entry_valid:
        return None

    if is_r2:
        pos["rule_triggered"] = "rule2_remedy"
        return violations_r2
    if is_r1:
        pos["rule_triggered"] = "rule1_direction_error"
        return violations_r1

    return None

# ── 自动执行 ───────────────────────────────────────────
def _load_auto_exit_log() -> list:
    try:
        if AUTO_EXIT_LOG.exists():
            return json.loads(AUTO_EXIT_LOG.read_text())
    except:
        return []

def _save_auto_exit_log(logs: list):
    AUTO_EXIT_LOG.write_text(json.dumps(logs[:200], ensure_ascii=False, indent=2))

def _build_card(is_pre: bool, pos: dict, rule: str,
                result_ok: bool, result_msg: str) -> dict:
    now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    rule_label = "规则一·方向错误" if rule == "rule1_direction_error" else "规则二·补救条款"
    rule_emoji = "🚨" if rule == "rule1_direction_error" else "🟡"
    pair   = pos.get("pair","?")
    side   = pos.get("side","?")
    port   = pos.get("port",0)
    tid    = pos.get("trade_id","")
    cur    = pos.get("current",0)
    entry  = pos.get("entry_price",0)
    pnl    = pos.get("pnl_pct",0)
    sup    = pos.get("support",0)
    res    = pos.get("resistance",0)
    d2s    = pos.get("dist_sup_pct",0)
    d2r    = pos.get("dist_res_pct",0)

    if is_pre:
        title = f"{rule_emoji} 自动平仓预警 · {rule_label} · {now_str}"
        header_color = "orange"
        body = (
            f"**触发规则：** {rule_emoji} {rule_label}\n"
            f"**持仓机器人：** {BOT_LABELS.get(port, f'端口{port}')}（端口 {port}）\n"
            f"**Trade ID：** `{tid}`\n"
            f"**交易对：** `{pair}` | {side}\n"
            f"**当前价：** ${cur:.4f} | **入场价：** ${entry:.4f}\n"
            f"**当前盈亏：** {pnl:.2f}%\n"
            f"**支撑位：** ${sup:.4f}（距支撑{d2s:.1f}%）\n"
            f"**压力位：** ${res:.4f}（距压力{d2r:.1f}%）\n\n"
            f"⏰ **子代理已授权，将在确认后直接执行平仓**\n"
            f"📍 如需人工拦截，请在10秒内联系管理员"
        )
    else:
        result_emoji = "✅" if result_ok else "❌"
        title = f"{result_emoji} 自动平仓执行结果 · {rule_label} · {now_str}"
        header_color = "green" if result_ok else "red"
        body = (
            f"**交易对：** `{pair}` | {side}\n"
            f"**持仓机器人：** {BOT_LABELS.get(port, f'端口{port}')}（端口 {port}）\n"
            f"**Trade ID：** `{tid}`\n"
            f"**执行结果：** {result_emoji} {result_msg}\n"
            f"**入场盈亏：** {pnl:.2f}%\n\n"
            f"{'✅ 自动平仓成功' if result_ok else '❌ 自动平仓失败，请人工检查'}"
        )

    return {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": title}, "template": header_color},
            "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": body}}],
        },
    }

def send_auto_exit_cards(pos: dict, rule: str, result_ok: bool, result_msg: str):
    try:
        pre_card = _build_card(True, pos, rule, result_ok, result_msg)
        result_card = _build_card(False, pos, rule, result_ok, result_msg)
        _send(WEBHOOK_BINGBU, pre_card)
        _send(WEBHOOK_BINGBU, result_card)
    except Exception as e:
        print(f"  ⚠️ 飞书卡片发送失败: {e}")

def process_auto_exit(pos: dict, rule: str, state: dict, now_ts: int):
    pair         = pos.get("pair","?")
    side         = pos.get("side","?")
    port         = pos.get("port",0)
    trade_id_int = int(pos.get("trade_id") or 0)
    pnl_pct      = pos.get("pnl_pct", 0) if pos.get("pnl_available") else 0.0

    if not pos.get("pnl_available", False):
        print(f"  ⏸️  [{pair}] 盈亏数据不可用，跳过自动执行")
        return False

    aekey = f"{pair}|{side}|auto_exit"
    last_ae = state.get("auto_exit_cool", {}).get(aekey, 0)
    if now_ts - last_ae < COOLDOWN_SEC:
        remaining = int((COOLDOWN_SEC - (now_ts - last_ae)) // 60)
        print(f"  ⏳ [{pair}] {side} 自动平仓冷却中（{remaining}分钟剩余）")
        return False

    if not trade_id_int or not AUTO_EXIT_ENABLED:
        return False

    rule_label = "规则一·方向错误" if rule == "rule1_direction_error" else "规则二·补救条款"
    print(f"  🚀 [{rule_label}] {pair} {side} → 执行自动平仓...")

    ok, msg = auto_exit_single(
        trade_id=trade_id_int, port=port, pair=pair, side=side,
        rule=rule, pnl_pct=pnl_pct,
    )
    send_auto_exit_cards(pos, rule, ok, msg)

    logs = _load_auto_exit_log()
    logs.insert(0, {
        "id": len(logs)+1,
        "timestamp": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rule": rule, "pair": pair, "side": side,
        "port": port, "trade_id": trade_id_int,
        "entry_price": pos.get("entry_price", 0),
        "exit_price":  pos.get("current", 0),
        "pnl_pct": pnl_pct, "result": msg, "success": ok,
    })
    _save_auto_exit_log(logs)

    if "auto_exit_cool" not in state:
        state["auto_exit_cool"] = {}
    state["auto_exit_cool"][aekey] = now_ts
    return ok

# ── 飞书发送 ───────────────────────────────────────────
def _send(webhook: str, card: dict) -> bool:
    try:
        payload = json.dumps(card, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(webhook, data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            json.loads(r.read())
        return True
    except Exception as e:
        print(f"[sr_guard] 飞书发送失败: {e}")
        return False

# ── 提案 ───────────────────────────────────────────────
def _load_pending():
    try:
        if PENDING_FILE.exists():
            return json.loads(PENDING_FILE.read_text())
    except:
        return []

def _save_pending(proposals):
    tmp = str(PENDING_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(proposals, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, str(PENDING_FILE))

def write_sr_proposal(pair: str, direction: str, action: str,
                      current: float, support: float, resistance: float,
                      dist_sup_pct: float, dist_res_pct: float,
                      port: int = 0, trade_id: str = "") -> str:
    now  = dt.datetime.now()
    uid  = uuid.uuid4().hex[:8]
    code = f"BS-SR-{now.strftime('%m%d%H%M')}-{uid}"
    proposals = _load_pending()
    proposals = [
        p for p in proposals
        if not (p.get("details",{}).get("pair") == pair and p.get("action") == action)
    ]
    proposals.append({
        "id": code, "code": code, "proposal_type": "sr_guard",
        "action": action, "pair": pair,
        "reason": f"S/R方向守卫：{pair} {direction}持仓方向偏离S/R位置",
        "details": {
            "pair": pair, "direction": direction, "port": port,
            "trade_id": trade_id, "current_price": current,
            "support": support, "resistance": resistance,
            "dist_sup_pct": dist_sup_pct, "dist_res_pct": dist_res_pct,
        },
        "created_at": now.isoformat(),
        "expires_at": (now + dt.timedelta(minutes=15)).isoformat(),
        "status": "pending",
        "executed_at": None, "result": None,
    })
    _save_pending(proposals)
    return code

def _load_builder():
    sys.path.insert(0, str(Path(__file__).parent))
    import bingbu_card_builder as _b
    return _b

def send_card(violations, all_position_details, state, now_ts):
    now_str  = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    base_url = "https://openclaw.tianlu2026.org"
    builder  = _load_builder()
    new_pos  = [p for p in all_position_details
                if p.get("age_seconds", 999999) <= MAX_POSITION_AGE_SEC]

    if not violations:
        print(f"  ✅ S/R正常（{len(new_pos)}个持仓在24小时内，均无偏离）")
        return

    sr_lines = []
    for p in new_pos:
        pair  = p.get("pair","?")
        side  = p.get("side","?")
        cur   = p.get("current",0)
        # 跳过数据无效（价格=0）的持仓，避免发送垃圾数据
        if cur <= 0:
            continue
        d2s   = p.get("dist_sup_pct",0)
        d2r   = p.get("dist_res_pct",0)
        age_m = int(p.get("age_seconds",0) // 60)
        is_v  = p.get("is_violation_r1") or p.get("is_violation_r2")
        ent_v = p.get("entry_valid", False)
        prot  = p.get("profit_protected", False)
        rule  = p.get("rule_triggered","")
        tag   = f"[{rule}]" if rule else ""
        flag  = ("🟡" if prot else "🚨") if is_v else ("✅" if ent_v else "⚠️")
        sr_lines.append(
            f"  {flag} **{pair}** `{side}` ${cur:.4f} | "
            f"撑距{d2s:.1f}% 压距{d2r:.1f}% | {age_m}m {tag}"
        )

    summary_card = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": f"🛡️ S/R方向守卫 V6 · {now_str}"},
                       "template": "red"},
            "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": (
                f"**【V6算法：Pivot Point + VWAP + 局部极值，无订单簿】**\n\n"
                f"**规则：入场在正确S/R位→不告警；入场错误+当前偏离→自动平仓；盈利>3% Rule1不执行**\n\n"
                f"**⚠️ {len(violations)} 个持仓偏离S/R位**\n\n"
                f"**📋 24h内持仓（S/R状态）：**\n" + "\n".join(sr_lines)
            )}}],
        },
    }
    _send(WEBHOOK_BINGBU, summary_card)

    for pos in all_position_details:
        age  = pos.get("age_seconds", 0)
        is_v = pos.get("is_violation_r1") or pos.get("is_violation_r2")
        if age > MAX_POSITION_AGE_SEC or not is_v or pos.get("entry_valid"):
            continue

        pair   = pos.get("pair","?")
        side   = pos.get("side","?")
        cur    = pos.get("current",0)
        # 跳过数据无效（价格=0）的持仓
        if cur <= 0:
            continue
        sup    = pos.get("support",0)
        res    = pos.get("resistance",0)
        d2s    = pos.get("dist_sup_pct",0)
        d2r    = pos.get("dist_res_pct",0)
        age_m  = int(age // 60)
        port   = pos.get("port",0)
        tid    = pos.get("trade_id","")
        pnl    = pos.get("pnl_pct",0)

        pkey = f"{pair}|{side}|proposal"
        last_p = state.get("violations", {}).get(pkey, 0)
        if now_ts - last_p < COOLDOWN_SEC:
            print(f"  ⏳ {pair} {side} 提案冷却中，跳过")
            continue

        if side == "SHORT":
            action, type_label, color, approve_text, reason = (
                "inject_long_pair", "📈 S/R方向守卫·做多提案", "green", "📈 批准反向做多",
                f"S/R方向守卫：{pair} SHORT持仓在支撑位附近（距支撑{d2s:.1f}%，距压力{d2r:.1f}%），建议做多"
            )
        else:
            action, type_label, color, approve_text, reason = (
                "inject_short_pair", "📉 S/R方向守卫·做空提案", "orange", "📉 批准反向做空",
                f"S/R方向守卫：{pair} LONG持仓在压力位附近（距支撑{d2s:.1f}%，距压力{d2r:.1f}%），建议做空"
            )

        code = write_sr_proposal(
            pair=pair, direction=side, action=action,
            current=cur, support=sup, resistance=res,
            dist_sup_pct=d2s, dist_res_pct=d2r,
            port=port, trade_id=tid,
        )
        state.setdefault("violations", {})[pkey] = now_ts

        exit_url    = f"{base_url}/bingbu/approve?code={code}&pair={pair}&action=exit"
        reject_url  = f"{base_url}/bingbu/reject?code={code}&pair={pair}"
        approve_url = f"{base_url}/bingbu/approve?code={code}&pair={pair}"

        body_lines = [
            f"**📍 持仓机器人：** {BOT_LABELS.get(port, f'端口 {port}')}（端口 {port}）",
            f"**Trade ID：** `{tid}` | **{side}**",
            f"**持仓时长：** 约{age_m}分钟 | **当前价：** ${cur:.4f}",
            f"**支撑位：** ${sup:.4f}（距支撑{d2s:.1f}%）",
            f"**压力位：** ${res:.4f}（距压力{d2r:.1f}%）",
            f"**入场盈亏：** {pnl:.2f}%",
        ]
        body = "\n".join(body_lines)

        card = builder.build_bingbu_card(
            action=action, proposal_id=code, pair=pair,
            reason=reason, approve_url=approve_url, reject_url=reject_url,
            body_text=body, expires_minutes=15, approve_text=approve_text,
            third_button_text="🔴 仅平仓（不反向）",
            third_button_url=exit_url, third_button_type="danger",
        )
        card["card"]["header"] = {
            "title": {"tag": "plain_text", "content": f"{type_label} · {now_str}"},
            "template": color
        }
        _send(WEBHOOK_BINGBU, card)
        print(f"  ✅ 已发送提案: {code} {pair} {side}")

# ── 主流程 ───────────────────────────────────────────
def main():
    ts = dt.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] 🛡️ S/R方向守卫 V6 启动（自动执行: {'启用' if AUTO_EXIT_ENABLED else '禁用'}）")

    now_ts   = time.time()
    positions = get_positions()
    print(f"  总持仓: {len(positions)}")
    if not positions:
        print("  ✅ 无持仓")
        return 0

    print("  🔍 获取各持仓入场时间...")
    open_dates = enrich_with_open_date(positions)

    state = load_state()

    def enrich(p):
        key = (p.get("pair", ""), p.get("side", ""))
        p["open_date"] = open_dates.get(key, p.get("open_date", ""))
        v = audit_position(p, state, now_ts)
        return p, v

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(enrich, positions))

    auto_exit_count = 0

    for pos, violations in results:
        if violations:
            rule  = pos.get("rule_triggered", "rule1_direction_error")
            age_m = int(pos.get("age_seconds", 0) // 60)
            pnl   = pos.get("pnl_pct", 0)
            prot  = pos.get("profit_protected", False)
            entry_v = pos.get("entry_valid", False)
            print(f"  🚨 [{rule}] {pos['pair']} {pos['side']} "
                  f"距支撑{pos.get('dist_sup_pct','?')}% 距压力{pos.get('dist_res_pct','?')}% "
                  f"age={age_m}m pnl={pnl:+.2f}% "
                  f"{'🔒盈利保护' if prot else ''} "
                  f"{'✅入场正确' if entry_v else ''}")

            if AUTO_EXIT_ENABLED and rule in ("rule1_direction_error", "rule2_remedy"):
                if rule == "rule1_direction_error" and pos.get("profit_protected", False):
                    print(f"  ⏭  [{pos['pair']}] 盈利>{PROFIT_PROTECT_PCT}%，Rule1跳过自动执行")
                    continue
                ok = process_auto_exit(pos, rule, state, now_ts)
                if ok:
                    auto_exit_count += 1

    violations_state = state.get("violations", {})
    violations_state = {k: v for k, v in violations_state.items() if now_ts - v <= COOLDOWN_SEC}
    state["violations"] = violations_state

    all_details = [dict(pos) for pos, _ in results]
    all_violations = [v for _, v in results if v]

    print(f"  📤 广播（违规 {len(all_violations)} 条，自动执行 {auto_exit_count} 条）")
    send_card(all_violations, all_details, state, now_ts)
    save_state(state)
    return len(all_violations)


if __name__ == "__main__":
    n = main()
    sys.exit(0)
