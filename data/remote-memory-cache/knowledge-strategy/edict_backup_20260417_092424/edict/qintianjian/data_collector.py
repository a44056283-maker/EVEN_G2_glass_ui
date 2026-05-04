#!/usr/bin/env python3
"""
钦天监 · 数据采集器
接入 Gate.io / CoinGecko / Freqtrade API
提供实时市场数据给规则引擎
"""
import json
import math
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ── 路径配置 ─────────────────────────────────────────────
DATA_DIR = Path.home() / "edict" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = DATA_DIR / "qintianjian_cache.json"
CACHE_TTL = 20  # 缓存有效期（秒）

# ── Gate.io 配置 ─────────────────────────────────────────
GATE_BASE = "https://api.gateio.ws"
GATE_SPOT = f"{GATE_BASE}/api/v4/spot"
GATE_FUTURES = f"{GATE_BASE}/api/v4/futures/usdt"

# ── 工具函数 ─────────────────────────────────────────────
def _get(url: str, headers: dict = None, timeout: int = 8) -> Optional[dict]:
    try:
        h = {"User-Agent": "TianluQintianjian/1.0", **(headers or {})}
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"[采集器] GET {url} 失败: {e}")
        return None

def _load_cache() -> dict:
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE) as f:
                d = json.load(f)
            if time.time() - d.get("_ts", 0) < CACHE_TTL:
                return d
    except:
        pass
    return {}

def _save_cache(d: dict):
    d["_ts"] = time.time()
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(d, f)
    except:
        pass

# ── Gate.io 现货行情 ─────────────────────────────────────
def fetch_gate_spot(symbol: str = "BTC_USDT") -> Optional[dict]:
    """获取Gate.io现货行情"""
    # symbol需用下划线
    data = _get(f"{GATE_SPOT}/tickers?currency_pair={symbol}")
    if not data or not isinstance(data, list):
        return None
    t = data[0]
    try:
        return {
            "symbol": symbol,
            "price": float(t.get("last", 0)),
            "high_24h": float(t.get("high_24h", 0)),
            "low_24h": float(t.get("low_24h", 0)),
            "change_pct": float(t.get("change_24h", 0)),
            "volume": float(t.get("quote_volume_24h", 0)),
            "bid": float(t.get("highest_bid", 0)),
            "ask": float(t.get("lowest_ask", 0)),
            "spread": 0.0,  # 将在fetch_order_book中更新
        }
    except:
        return None

def fetch_order_book(symbol: str = "BTC_USDT", depth: int = 5) -> Optional[dict]:
    """获取订单簿深度（计算OBI用）"""
    data = _get(f"{GATE_SPOT}/order_book/{symbol}?limit={depth}")
    if not data:
        return None
    try:
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        if not bids or not asks:
            return None
        bid_v = float(bids[0][0])
        ask_v = float(asks[0][0])
        spread = (ask_v - bid_v) / bid_v * 100
        bid_vol = sum(float(b[1]) for b in bids[:3])
        ask_vol = sum(float(a[1]) for a in asks[:3])
        obi = (bid_vol - ask_vol) / (bid_vol + ask_vol + 1e-9)
        return {
            "bid": bid_v, "ask": ask_v,
            "spread_pct": spread,
            "bid_vol": bid_vol, "ask_vol": ask_vol,
            "obi": obi,
        }
    except:
        return None

# ── Gate.io 合约资金费率 ─────────────────────────────────
def fetch_funding_rate(symbol: str = "BTC_USDT") -> Optional[dict]:
    """获取U本位永续合约资金费率"""
    # symbol需转BTC_USDT_SWAP格式
    contract_symbol = symbol.replace("_", "_SWAP_").replace("USDT", "")
    # Gate永续symbol格式: BTC_USDT_SWAP
    swap_sym = f"{symbol.replace('_USDT', '')}_USDT_SWAP"
    data = _get(f"{GATE_FUTURES}/contracts/{swap_sym}")
    if not data:
        return None
    try:
        return {
            "symbol": symbol,
            "funding_rate": float(data.get("funding_rate", 0)),
            "funding_rate_e8": int(data.get("funding_rate_e8", 0)),
            "funding_rate_next": float(data.get("funding_rate_next", 0)),
            "mark_price": float(data.get("mark_price", 0)),
            "index_price": float(data.get("index_price", 0)),
            "total_position": float(data.get("total_position", 0)),
        }
    except:
        return None

def fetch_futures_tickers() -> list:
    """获取所有合约持仓量变化"""
    data = _get(f"{GATE_FUTURES}/tickers")
    if not data:
        return []
    result = []
    for t in data[:20]:  # 只取前20个主流币
        try:
            result.append({
                "symbol": t.get("contract", ""),
                "volume_24h": float(t.get("volume_24h", 0)),
                "change_pct": float(t.get("change_24h", 0)),
            })
        except:
            pass
    return result

# ── K线数据（用于ATR计算）────────────────────────────────
def fetch_klines(symbol: str = "BTC_USDT", interval: str = "1h", limit: int = 100) -> list:
    """获取K线数据（用于计算ATR）"""
    interval_map = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}
    intv = interval_map.get(interval, "1h")
    data = _get(f"{GATE_SPOT}/candlesticks?currency_pair={symbol}&interval={intv}&limit={limit}")
    if not data:
        return []
    result = []
    for c in data:
        try:
            result.append({
                "t": int(c[0]),
                "v": float(c[5]),      # volume
                "h": float(c[2]),      # high
                "l": float(c[3]),      # low
                "c": float(c[4]),      # close
            })
        except:
            pass
    return result

def calc_atr(klines: list, period: int = 14) -> float:
    """计算ATR（Average True Range）"""
    if len(klines) < period + 1:
        return 0.0
    trs = []
    for i in range(1, min(len(klines), period + 50)):
        h = klines[i]["h"]
        l = klines[i]["l"]
        prev_c = klines[i-1]["c"]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        trs.append(tr)
    if len(trs) < period:
        return 0.0
    trs = trs[-period:]
    return sum(trs) / len(trs)

def calc_atr_pct(atrs: float, price: float) -> float:
    """ATR占价格百分比"""
    if not price:
        return 0.0
    return atrs / price * 100

def calc_adx(klines: list, period: int = 14) -> float:
    """计算ADX（趋势强度）"""
    if len(klines) < period * 2:
        return 0.0
    plus_dm, minus_dm, tr_sum = [], [], []
    for i in range(1, min(len(klines), period * 3)):
        h, l, prev_h, prev_l = klines[i]["h"], klines[i]["l"], klines[i-1]["h"], klines[i-1]["l"]
        tr = max(h - l, abs(h - klines[i-1]["c"]), abs(l - klines[i-1]["c"]))
        plus_dm_val = max(h - prev_h, 0) if (h - prev_h) > (prev_l - l) else 0
        minus_dm_val = max(prev_l - l, 0) if (prev_l - l) > (h - prev_h) else 0
        tr_sum.append(tr)
        plus_dm.append(plus_dm_val)
        minus_dm.append(minus_dm_val)
    if len(tr_sum) < period:
        return 0.0
    tr_avg = sum(tr_sum[-period:]) / period
    plus_avg = sum(plus_dm[-period:]) / period
    minus_avg = sum(minus_dm[-period:]) / period
    if not tr_avg:
        return 0.0
    plus_di = (plus_avg / tr_avg) * 100
    minus_di = (minus_avg / tr_avg) * 100
    dx = abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9) * 100
    # 简化：返回ADX估计值
    return min(dx, 100)

# ── EMA 计算 ─────────────────────────────────────────────
def calc_ema(prices: list, period: int) -> float:
    if len(prices) < period:
        return 0.0
    k = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for p in prices[period:]:
        ema = p * k + ema * (1 - k)
    return ema

# ── RSI 计算 ─────────────────────────────────────────────
def calc_rsi(prices: list, period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    if len(gains) < period:
        return 50.0
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ── 布林带 ──────────────────────────────────────────────
def calc_bollinger(prices: list, period: int = 20, std_mult: float = 2.0) -> dict:
    if len(prices) < period:
        return {"upper": 0, "lower": 0, "mid": 0, "width": 100}
    subset = prices[-period:]
    mid = sum(subset) / len(subset)
    variance = sum((p - mid) ** 2 for p in subset) / len(subset)
    std = math.sqrt(variance)
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    width = (upper - lower) / mid * 100 if mid else 0
    return {"upper": upper, "lower": lower, "mid": mid, "width": width}

# ── VWAP ─────────────────────────────────────────────────
def calc_vwap(klines: list) -> float:
    """成交量加权平均价"""
    if not klines:
        return 0.0
    total_pv = sum(k["c"] * k["v"] for k in klines)
    total_v = sum(k["v"] for k in klines)
    return total_pv / total_v if total_v else 0.0

# ── Fear & Greed ─────────────────────────────────────────
def fetch_fear_greed() -> dict:
    """获取Fear & Greed指数"""
    data = _get("https://api.alternative.me/fng/?limit=1", timeout=5)
    if not data or "data" not in data:
        return {"value": 50, "label": "Neutral", "timestamp": ""}
    try:
        d = data["data"][0]
        return {
            "value": int(d.get("value", 50)),
            "label": d.get("value_classification", "Neutral"),
            "timestamp": d.get("timestamp", ""),
        }
    except:
        return {"value": 50, "label": "Neutral", "timestamp": ""}

# ── BTC Dominance ────────────────────────────────────────
def fetch_btc_dominance() -> float:
    """获取BTC市值占比"""
    data = _get("https://api.coingecko.com/api/v3/global", timeout=8)
    if not data or "data" not in data:
        return 50.0
    try:
        return float(data["data"]["market_cap_percentage"]["btc"])
    except:
        return 50.0

# ── Freqtrade Bot 认证配置 ────────────────────────────────
import base64

def _ft_auth(port: int) -> str:
    """根据端口返回正确的Basic Auth"""
    if port in (9090, 9091, 9092):
        creds = "freqtrade:freqtrade"
    else:  # 9093-9097 are OKX bots
        creds = "admin:Xy@06130822"
    return "Basic " + base64.b64encode(creds.encode()).decode()

# ── Freqtrade 持仓 & P&L ────────────────────────────────
def fetch_ft_positions(port: int = 9090) -> list:
    """获取Freqtrade当前持仓"""
    data = _get(
        f"http://127.0.0.1:{port}/api/v1/status",
        headers={"Authorization": _ft_auth(port)},
        timeout=5
    )
    if not data:
        return []
    if isinstance(data, dict):
        data = data.get("result", [])
    positions = []
    for p in data:
        try:
            positions.append({
                "symbol": p.get("pair", ""),
                "amount": float(p.get("amount", 0)),
                "entry_price": float(p.get("open_rate", 0)),
                "current_price": float(p.get("current_rate", 0)),
                "pnl_pct": float(p.get("profit_abs", 0)),
                "pnl_abs": float(p.get("profit_abs", 0)),
                "is_short": p.get("is_short", False),
                "opened_at": p.get("open_date", ""),
            })
        except:
            pass
    return positions

def fetch_ft_balance(port: int = 9090) -> dict:
    """获取Freqtrade账户余额"""
    data = _get(
        f"http://127.0.0.1:{port}/api/v1/balance",
        headers={"Authorization": _ft_auth(port)},
        timeout=5
    )
    if not data:
        return {}
    try:
        b = data.get("result", data)
        return {
            "total": float(b.get("total", 0)),
            "free": float(b.get("free", 0)),
            "used": float(b.get("used", 0)),
            " equity": float(b.get(" equity", b.get("total", 0))),
        }
    except:
        return {}

def fetch_daily_pnl(port: int = 9090) -> float:
    """获取今日盈亏百分比"""
    data = _get(
        f"http://127.0.0.1:{port}/api/v1/balance",
        headers={"Authorization": _ft_auth(port)},
        timeout=5
    )
    if not data:
        return 0.0
    try:
        b = data.get("result", data)
        return float(b.get("profit_all_percent", 0))
    except:
        return 0.0

# ── 采集主函数 ─────────────────────────────────────────────
def collect_all() -> dict:
    """
    采集所有市场数据，返回完整情报包（并发优化版）
    优先使用缓存，20秒内不重复请求
    所有外部API调用全部并发执行
    """
    import concurrent.futures

    cache = _load_cache()
    now = time.time()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _need(key: str, ttl: int = CACHE_TTL) -> bool:
        return cache.get(f"_ts_{key}", 0) < now - ttl

    result = {"collected_at": ts, "symbols": {}, "sentiment": {}, "positions": [], "balances": []}

    # ── 并发采集所有外部数据（所有组同时请求）──
    def _fetch_group_btc():
        klines = fetch_klines("BTC_USDT", "1h", 200)
        price_data = fetch_gate_spot("BTC_USDT")
        ob_data = fetch_order_book("BTC_USDT")
        fr_data = fetch_funding_rate("BTC_USDT")
        return klines, price_data, ob_data, fr_data

    def _fetch_group_sentiment():
        fg = fetch_fear_greed()
        btc_d = fetch_btc_dominance()
        return fg, btc_d

    def _fetch_positions(port):
        try:
            pos = fetch_ft_positions(port)
            for p in pos:
                p["bot_port"] = port
            return pos
        except:
            return []

    def _fetch_balance(port):
        try:
            bal = fetch_ft_balance(port)
            return (str(port), bal) if bal else None
        except:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        futures = {}

        # BTC 行情（4个API并发）
        if _need("btc"):
            f1 = pool.submit(fetch_klines, "BTC_USDT", "1h", 200)
            f2 = pool.submit(fetch_gate_spot, "BTC_USDT")
            f3 = pool.submit(fetch_order_book, "BTC_USDT")
            f4 = pool.submit(fetch_funding_rate, "BTC_USDT")
            futures["btc"] = (f1, f2, f3, f4)
        else:
            klines = cache.get("btc_klines", [])
            price_data = cache.get("btc_price", {})
            ob_data = cache.get("btc_ob", {})
            fr_data = cache.get("btc_fr", {})
            futures["btc"] = None

        # ETH 行情
        if _need("eth"):
            futures["eth"] = pool.submit(fetch_gate_spot, "ETH_USDT")
        else:
            futures["eth"] = None

        # 情绪
        if _need("fg"):
            f_fg = pool.submit(fetch_fear_greed)
            f_btc_d = pool.submit(fetch_btc_dominance)
            futures["fg"] = (f_fg, f_btc_d)
        else:
            futures["fg"] = None

        # 持仓（8个bot并发）
        if _need("positions"):
            port_futures = {pool.submit(_fetch_positions, p): p for p in [9090, 9091, 9092, 9093, 9094, 9095, 9096, 9097]}
            futures["positions"] = port_futures
        else:
            futures["positions"] = None

        # 余额（8个bot并发）
        if _need("balances"):
            bal_futures = {pool.submit(_fetch_balance, p): p for p in [9090, 9091, 9092, 9093, 9094, 9095, 9096, 9097]}
            futures["balances"] = bal_futures
        else:
            futures["balances"] = None

        # ── 收集结果 ──────────────────────────────────
        # BTC
        if futures["btc"] is not None:
            f1, f2, f3, f4 = futures["btc"]
            klines, price_data, ob_data, fr_data = f1.result(), f2.result(), f3.result(), f4.result()
            cache["btc_klines"] = klines
            cache["btc_price"] = price_data
            cache["btc_ob"] = ob_data
            cache["btc_fr"] = fr_data
            cache["_ts_btc"] = now
        else:
            klines = cache.get("btc_klines", [])
            price_data = cache.get("btc_price", {})
            ob_data = cache.get("btc_ob", {})
            fr_data = cache.get("btc_fr", {})

        # ETH
        if futures["eth"] is not None:
            eth_price_data = futures["eth"].result()
            cache["eth_price"] = eth_price_data
            cache["_ts_eth"] = now
        else:
            eth_price_data = cache.get("eth_price", {})

        # 情绪
        if futures["fg"] is not None:
            f_fg, f_btc_d = futures["fg"]
            cache["fg"] = f_fg.result()
            cache["btc_d"] = f_btc_d.result()
            cache["_ts_fg"] = now

        # 持仓
        if futures["positions"] is not None:
            all_positions = []
            for pf in concurrent.futures.as_completed(futures["positions"]):
                all_positions.extend(pf.result())
            cache["all_positions"] = all_positions
            cache["_ts_positions"] = now
        else:
            all_positions = cache.get("all_positions", [])

        # 余额
        if futures["balances"] is not None:
            all_balances = {}
            for bf in concurrent.futures.as_completed(futures["balances"]):
                r = bf.result()
                if r:
                    port_str, bal = r
                    all_balances[port_str] = bal
            cache["all_balances"] = all_balances
            cache["_ts_balances"] = now
        else:
            all_balances = cache.get("all_balances", {})

    # ── 计算技术指标 ───────────────────────────────
    price = price_data.get("price", 0) if price_data else 0
    closes = [k["c"] for k in klines] if klines else []
    atr = calc_atr(klines, 14) if klines else 0
    atr_pct = calc_atr_pct(atr, price)
    adx = calc_adx(klines, 14) if klines else 0
    ema50 = calc_ema(closes, 50) if len(closes) >= 50 else 0
    ema200 = calc_ema(closes, 200) if len(closes) >= 200 else 0
    rsi = calc_rsi(closes, 14) if len(closes) >= 15 else 50
    bb = calc_bollinger(closes, 20) if len(closes) >= 20 else {"width": 100}
    vwap = calc_vwap(klines[-24:]) if klines else 0
    vol_ratio = 1.0
    if klines and len(klines) >= 24:
        avg_vol = sum(k["v"] for k in klines[-24:]) / 24
        cur_vol = klines[-1]["v"] if klines else 1
        vol_ratio = cur_vol / avg_vol if avg_vol else 1.0

    result["symbols"]["BTC"] = {
        "price": price,
        "high_24h": price_data.get("high_24h", 0) if price_data else 0,
        "low_24h": price_data.get("low_24h", 0) if price_data else 0,
        "change_pct": price_data.get("change_pct", 0) if price_data else 0,
        "volume_24h": price_data.get("volume", 0) if price_data else 0,
        "bid": price_data.get("bid", 0) if price_data else 0,
        "ask": price_data.get("ask", 0) if price_data else 0,
        "atr": atr,
        "atr_pct": atr_pct,
        "adx": adx,
        "ema50": ema50,
        "ema200": ema200,
        "rsi": rsi,
        "bb_width": bb.get("width", 100),
        "vwap": vwap,
        "vol_ratio": vol_ratio,
        "obi": ob_data.get("obi", 0) if ob_data else 0,
        "spread_pct": ob_data.get("spread_pct", 0) if ob_data else 0,
        "funding_rate": fr_data.get("funding_rate", 0) if fr_data else 0,
        "funding_rate_e8": fr_data.get("funding_rate_e8", 0) if fr_data else 0,
    }
    result["symbols"]["ETH"] = {
        "price": eth_price_data.get("price", 0) if eth_price_data else 0,
        "change_pct": eth_price_data.get("change_pct", 0) if eth_price_data else 0,
    }
    result["sentiment"] = {
        "fear_greed": cache.get("fg", {}).get("value", 50),
        "fg_label": cache.get("fg", {}).get("label", "Neutral"),
        "btc_dominance": cache.get("btc_d", 50.0),
    }
    result["positions"] = all_positions
    result["balances"] = all_balances

    # ── 汇总统计 ──
    total_pnl_pct = 0.0
    max_holding_hours = 0.0
    now_ts = datetime.now()
    for p in result["positions"]:
        opened = p.get("opened_at", "")
        if opened:
            try:
                opened_dt = datetime.strptime(opened[:19], "%Y-%m-%dT%H:%M:%S")
                hours = (now_ts - opened_dt).total_seconds() / 3600
                max_holding_hours = max(max_holding_hours, hours)
            except:
                pass

    result["stats"] = {
        "open_count": len(result["positions"]),
        "total_pnl_pct": total_pnl_pct,
        "max_holding_hours": max_holding_hours,
    }

    _save_cache(cache)
    return result

if __name__ == "__main__":
    data = collect_all()
    print(json.dumps(data, indent=2, ensure_ascii=False))
