#!/usr/bin/env python3

"""

兵部下单审计脚本 + 自动S/R信号扫描

检查持仓方向是否与S/R位置逻辑一致（原有功能）
逻辑一：无持仓时入场信号扫描（±2%规则）
逻辑二：对手信号全平+反向开仓扫描

发现问题 → 生成提案 → 发尚书省审批（半自动B方案）

自动扫描模式：
  python3 bingbu_order_audit.py --auto-scan

"""

import json, sys, time, urllib.request, concurrent.futures, datetime as dt, subprocess, os
import requests as _req

from pathlib import Path
from typing import Optional


def _atomic_write_json(filepath: Path, data, indent: int = 2) -> None:
    """将data以JSON格式原子写入filepath（先写.tmp再rename）"""
    tmp = str(filepath) + ".tmp"
    Path(tmp).write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")
    os.replace(tmp, str(filepath))



EDICT_DATA = Path("/Users/luxiangnan/edict/data")

FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"

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



FREQTRADE = {
    9090: {"url": "http://127.0.0.1:9090", "auth": "Basic ZnJlcXRyYWRlOmZyZXF0cmFkZQ==", "label": "Gate-17656685222"},
    9091: {"url": "http://127.0.0.1:9091", "auth": "Basic ZnJlcXRyYWRlOmZyZXF0cmFkZQ==", "label": "Gate-85363904550"},
    9092: {"url": "http://127.0.0.1:9092", "auth": "Basic ZnJlcXRyYWRlOmZyZXF0cmFkZQ==", "label": "Gate-15637798222"},
    9093: {"url": "http://127.0.0.1:9093", "auth": "Basic YWRtaW46WHlAdmE2MTMwODIy", "label": "OKX-15637798222"},
    9094: {"url": "http://127.0.0.1:9094", "auth": "Basic YWRtaW46WHlAdmE2MTMwODIy", "label": "OKX-BOT85363904550"},
    9095: {"url": "http://127.0.0.1:9095", "auth": "Basic YWRtaW46WHlAdmE2MTMwODIy", "label": "OKX-BOTa44056283"},
    9096: {"url": "http://127.0.0.1:9096", "auth": "Basic YWRtaW46WHlAdmE2MTMwODIy", "label": "OKX-BHB16638759999"},
    9097: {"url": "http://127.0.0.1:9097", "auth": "Basic YWRtaW46WHlAdmE2MTMwODIy", "label": "OKX-17656685222"},
}




def get_positions():

    result = []

    for port, cfg in FREQTRADE.items():

        try:

            req = urllib.request.Request(f"{cfg['url']}/api/v1/status", headers={"Authorization": cfg["auth"]})

            with urllib.request.urlopen(req, timeout=5) as r:

                for pos in json.loads(r.read()):

                    if pos.get("is_open"):

                        result.append({

                            "pair": pos.get("pair", "?"),

                            "side": "SHORT" if pos.get("is_short") else "LONG",

                            "entry": float(pos.get("open_rate", 0)),

                            "amount": float(pos.get("amount", 0)),

                            "bot": cfg["label"],

                            "port": port,

                            "trade_id": str(pos.get("trade_id", "")),

                        })

        except Exception:

            pass

    return result




def fetch_sr(pair):

    """通过Gate.io公开API获取当前价格和S/R位"""

    pair_clean = pair.split(":")[0]  # BTC/USDT:USDT -> BTC/USDT

    gate_pair = pair_clean.replace("/", "_")  # BTC/USDT -> BTC_USDT

    current, support, resistance = 0.0, None, None

    try:

        tk = _req.get(f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={gate_pair}", timeout=8)

        if tk.status_code == 200:

            data = tk.json()

            if data and isinstance(data, list):

                current = float(data[0].get("last", 0))

        kx = _req.get(f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={gate_pair}&interval=15m&limit=100", timeout=8)

        if kx.status_code == 200:

            klines = kx.json()

            if klines and isinstance(klines, list) and len(klines) > 0:

                highs = [float(k[3]) for k in klines]

                lows  = [float(k[4]) for k in klines]

                n = min(20, len(highs))

                resistance = sum(sorted(highs[-n:])[-5:]) / 5

                support    = sum(sorted(lows[-n:])[:5]) / 5

    except Exception:

        pass

    return current, support, resistance


# ─────────────────────────────────────────────────────────────
# V6.5 S/R 信号扫描（Gate.io 公开API）— 多时线确认版本
# ─────────────────────────────────────────────────────────────

# 多时线列表（interval 参数）
TF_INTERVALS = ["1m", "5m", "15m", "1h"]
# 每个时线取最近 N 根 K 线
TF_LOOKBACK = 40


def _fetch_sr_single_tf(gate_pair: str, interval: str) -> dict | None:
    """单一时线获取 S/R 数据。返回 dict 或 None（失败）。"""
    try:
        kx = _req.get(
            f"https://api.gateio.ws/api/v4/spot/candlesticks"
            f"?currency_pair={gate_pair}&interval={interval}&limit={TF_LOOKBACK}",
            timeout=10,
        )
        if kx.status_code != 200:
            return None
        klines = kx.json()
        if not klines or len(klines) < 10:
            return None

        highs  = [float(k[3]) for k in klines]
        lows   = [float(k[4]) for k in klines]
        closes = [float(k[2]) for k in klines]

        n = min(20, len(lows))
        support_price    = sum(sorted(lows[-n:])[:5]) / 5
        resistance_price = sum(sorted(highs[-n:])[-5:]) / 5

        support_touches    = sum(1 for c in closes[-20:] if c <= support_price * 1.02)
        resistance_touches = sum(1 for c in closes[-20:] if c >= resistance_price * 0.98)

        return {
            "support_price":    support_price,
            "resistance_price": resistance_price,
            "support_touches":    support_touches,
            "resistance_touches": resistance_touches,
        }
    except Exception:
        return None


def fetch_sr_v65(pair: str) -> dict:
    """
    通过 Gate.io 公开 API 获取 S/R 数据，使用多时线确认机制。
    并发请求 1m / 5m / 15m / 1h 四个时线，
    只有 ≥2 个时线同时确认某 S/R 位才视为有效。

    返回: {
        "has_support": bool, "support_price": float, "support_touches": int,
        "has_resistance": bool, "resistance_price": float, "resistance_touches": int,
        "current_price": float,
        "dist_to_support_pct": float, "dist_to_resistance_pct": float,
        "tf_confirmed": int,   # 确认时线数量（1~4）
        "tf_support": float,   # 多时线加权支撑位
        "tf_resistance": float, # 多时线加权压力位
    }
    """
    pair_clean = pair.split(":")[0]
    gate_pair  = pair_clean.replace("/", "_")

    try:
        tk = _req.get(
            f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={gate_pair}",
            timeout=8,
        )
        if tk.status_code != 200 or not tk.json():
            return {}
        current = float(tk.json()[0].get("last", 0))
        if not current or current <= 0:
            return {}
    except Exception:
        return {}

    # 并发请求四个时线
    def fetch_one(interval: str) -> tuple[str, dict | None]:
        return interval, _fetch_sr_single_tf(gate_pair, interval)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        results = dict(ex.map(fetch_one, TF_INTERVALS))

    valid_results = {k: v for k, v in results.items() if v is not None}
    if not valid_results:
        return {}

    # ── 多时线 S/R 汇总 ────────────────────────────────────
    all_sup  = [v["support_price"]    for v in valid_results.values()]
    all_res  = [v["resistance_price"] for v in valid_results.values()]

    # 支撑位：多时线等权均值
    tf_support    = sum(all_sup) / len(all_sup)
    # 压力位：多时线等权均值
    tf_resistance = sum(all_res) / len(all_res)

    # 触底/触顶：取各时线最大值（更具代表性）
    tf_support_touches    = max((v["support_touches"]    for v in valid_results.values()), default=0)
    tf_resistance_touches = max((v["resistance_touches"] for v in valid_results.values()), default=0)

    # 多时线确认数
    tf_confirmed = len(valid_results)

    # 到期 S/R 距离百分比
    dist_to_support_pct    = round((current - tf_support)    / current * 100, 2)
    dist_to_resistance_pct = round((tf_resistance - current) / current * 100, 2)

    return {
        "has_support":          True,
        "support_price":       round(tf_support,    4),
        "support_touches":      tf_support_touches,
        "has_resistance":       True,
        "resistance_price":     round(tf_resistance, 4),
        "resistance_touches":   tf_resistance_touches,
        "current_price":        round(current, 4),
        "dist_to_support_pct":    dist_to_support_pct,
        "dist_to_resistance_pct": dist_to_resistance_pct,
        "tf_confirmed":         tf_confirmed,
        "tf_support":           round(tf_support,    4),
        "tf_resistance":        round(tf_resistance, 4),
    }


def get_whitelist_pairs() -> list[str]:
    """从任意一个运行中的bot获取白名单交易对"""
    for port in [9090, 9091, 9092, 9093, 9094, 9095, 9096, 9097]:
        cfg = FREQTRADE.get(port)
        if not cfg:
            continue
        try:
            req = urllib.request.Request(
                f"{cfg['url']}/api/v1/whitelist",
                headers={"Authorization": cfg["auth"]},
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
                wl = data.get("whitelist", [])
                if wl:
                    return [p.split(":")[0] for p in wl]
        except Exception:
            continue
    return []


# ─────────────────────────────────────────────────────────────
# 逻辑一：无持仓时入场信号扫描
# ─────────────────────────────────────────────────────────────

def scan_entry_signals(flat_pairs: list[str]) -> list[dict]:
    """
    扫描空仓交易对，检测是否存在强烈入场信号。
    V6.5 入场规则：
      - 做多：价格在支撑位±2%内（d2sup ≤ 2%）且触底≥1次
      - 做空：价格在压力位±2%内（d2res ≤ 2%）且触顶≥1次
    """
    if not flat_pairs:
        return []

    # 并发获取所有空仓对的S/R数据
    def enrich_pair(pair: str) -> tuple[str, dict]:
        sr = fetch_sr_v65(pair)
        return pair, sr

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        results = dict(ex.map(enrich_pair, flat_pairs))

    proposals = []
    for pair, sr in results.items():
        if not sr.get("has_support") or not sr.get("has_resistance"):
            continue

        cur        = sr["current_price"]
        sup        = sr["support_price"]
        res        = sr["resistance_price"]
        t_sup      = sr["support_touches"]
        t_res      = sr["resistance_touches"]
        d2sup      = sr["dist_to_support_pct"]
        d2res      = sr["dist_to_resistance_pct"]

        # ── 逻辑一A：做多信号 ─────────────────────────────
        if d2sup <= 2.0 and t_sup >= 1:
            proposals.append({
                "type": "entry_signal",
                "direction": "LONG",
                "pair": pair,
                "action": "inject_long_pair",
                "reason": (
                    f"🚀 兵部入场扫描[LONG]：{pair} 空仓中检测到强入场信号\n"
                    f"当前价${cur:.4f} | 支撑${sup:.4f}（距{d2sup:.1f}%）| 触底{t_sup}次\n"
                    f"触发规则：支撑位±2%内 + 触底≥1次 → 建议做多"
                ),
                "details": {
                    "pair": pair,
                    "direction": "LONG",
                    "confidence": min(95, 60 + t_sup * 10),
                    "current_price": round(cur, 4),
                    "support": round(sup, 4),
                    "resistance": round(res, 4),
                    "dist_to_support_pct": d2sup,
                    "dist_to_resistance_pct": d2res,
                    "support_touches": t_sup,
                    "resistance_touches": t_res,
                    "signal_type": "scan_entry_long",
                },
            })

        # ── 逻辑一B：做空信号 ─────────────────────────────
        if d2res <= 2.0 and t_res >= 1:
            proposals.append({
                "type": "entry_signal",
                "direction": "SHORT",
                "pair": pair,
                "action": "inject_short_pair",
                "reason": (
                    f"📉 兵部入场扫描[SHORT]：{pair} 空仓中检测到强入场信号\n"
                    f"当前价${cur:.4f} | 压力${res:.4f}（距{d2res:.1f}%）| 触顶{t_res}次\n"
                    f"触发规则：压力位±2%内 + 触顶≥1次 → 建议做空"
                ),
                "details": {
                    "pair": pair,
                    "direction": "SHORT",
                    "confidence": min(95, 60 + t_res * 10),
                    "current_price": round(cur, 4),
                    "support": round(sup, 4),
                    "resistance": round(res, 4),
                    "dist_to_support_pct": d2sup,
                    "dist_to_resistance_pct": d2res,
                    "support_touches": t_sup,
                    "resistance_touches": t_res,
                    "signal_type": "scan_entry_short",
                },
            })

    return proposals


# ─────────────────────────────────────────────────────────────
# 逻辑二：对手信号全平 + 反向开仓扫描
# ─────────────────────────────────────────────────────────────

def scan_counter_signals(positions: list[dict]) -> list[dict]:
    """
    扫描现有持仓，检测是否存在对手信号冲突。
    规则：
      - LONG持仓 + 价格在阻力位±2%内 + 触顶≥1次 → 全平LONG + 注入SHORT信号
      - SHORT持仓 + 价格在支撑位±2%内 + 触底≥1次 → 全平SHORT + 注入LONG信号
    """
    if not positions:
        return []

    def enrich_pos(pos: dict) -> tuple[dict, dict]:
        sr = fetch_sr_v65(pos["pair"])
        return pos, sr

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        enriched = list(ex.map(enrich_pos, positions))

    proposals = []
    for pos, sr in enriched:
        if not sr.get("has_support") or not sr.get("has_resistance"):
            continue

        cur    = sr["current_price"]
        sup    = sr["support_price"]
        res    = sr["resistance_price"]
        t_sup  = sr["support_touches"]
        t_res  = sr["resistance_touches"]
        d2sup  = sr["dist_to_support_pct"]
        d2res  = sr["dist_to_resistance_pct"]
        side   = pos["side"]

        # ── 逻辑二A：LONG持仓 + 阻力位强势 → 全平 + 做空 ─
        if side == "LONG" and d2res <= 2.0 and t_res >= 1:
            proposals.append({
                "type": "counter_signal",
                "direction": "SHORT",
                "pair": pos["pair"],
                "action": "inject_short_pair",
                "reason": (
                    f"⚠️ 兵部对手信号扫描：{pos['pair']} LONG持仓面临SHORT信号\n"
                    f"当前价${cur:.4f} | 压力${res:.4f}（距{d2res:.1f}%）| 触顶{t_res}次\n"
                    f"触发规则：LONG持仓 + 压力位±2%内 + 触顶≥1次 → 全平LONG，反向做空"
                ),
                "details": {
                    "pair": pos["pair"],
                    "direction": "SHORT",
                    "port": pos.get("port", 0),
                    "trade_id": pos.get("trade_id", ""),
                    "confidence": min(95, 70 + t_res * 8),
                    "current_price": round(cur, 4),
                    "support": round(sup, 4),
                    "resistance": round(res, 4),
                    "dist_to_support_pct": d2sup,
                    "dist_to_resistance_pct": d2res,
                    "support_touches": t_sup,
                    "resistance_touches": t_res,
                    "existing_side": side,
                    "entry_price": round(pos["entry"], 4),
                    "signal_type": "scan_counter_short",
                },
            })

        # ── 逻辑二B：SHORT持仓 + 支撑位强势 → 全平 + 做多 ─
        elif side == "SHORT" and d2sup <= 2.0 and t_sup >= 1:
            proposals.append({
                "type": "counter_signal",
                "direction": "LONG",
                "pair": pos["pair"],
                "action": "inject_long_pair",
                "reason": (
                    f"⚠️ 兵部对手信号扫描：{pos['pair']} SHORT持仓面临LONG信号\n"
                    f"当前价${cur:.4f} | 支撑${sup:.4f}（距{d2sup:.1f}%）| 触底{t_sup}次\n"
                    f"触发规则：SHORT持仓 + 支撑位±2%内 + 触底≥1次 → 全平SHORT，反向做多"
                ),
                "details": {
                    "pair": pos["pair"],
                    "direction": "LONG",
                    "port": pos.get("port", 0),
                    "trade_id": pos.get("trade_id", ""),
                    "confidence": min(95, 70 + t_sup * 8),
                    "current_price": round(cur, 4),
                    "support": round(sup, 4),
                    "resistance": round(res, 4),
                    "dist_to_support_pct": d2sup,
                    "dist_to_resistance_pct": d2res,
                    "support_touches": t_sup,
                    "resistance_touches": t_res,
                    "existing_side": side,
                    "entry_price": round(pos["entry"], 4),
                    "signal_type": "scan_counter_long",
                },
            })

    return proposals




def audit(positions):

    """审计所有持仓，找出方向错误的持仓（多时线确认版）"""

    issues = []

    def enrich(pos: dict) -> dict:
        sr = fetch_sr_v65(pos["pair"])
        pos["_sr"] = sr
        return pos

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        positions = list(ex.map(enrich, positions))

    for p in positions:
        sr  = p.get("_sr", {})
        if not sr.get("has_support") or not sr.get("has_resistance"):
            continue

        side    = p["side"]
        cur     = sr.get("current_price", 0) or p["entry"]
        sup     = sr.get("support_price")
        res     = sr.get("resistance_price")
        d2s     = sr.get("dist_to_support_pct")
        d2r     = sr.get("dist_to_resistance_pct")
        t_sup   = sr.get("support_touches", 0)
        t_res   = sr.get("resistance_touches", 0)
        tf_conf = sr.get("tf_confirmed", 0)

        # 至少2个时线确认才处理
        if tf_conf < 2:
            continue

        # ── 置信度分层 ───────────────────────────────────
        # 高置信：≥3条时线确认 且 偏离>8%（明显错误）
        # 低置信：2条时线确认 或 偏离5%~8%（边缘情况 → 半自动审批）
        high_conf = (tf_conf >= 3 and ((side == "SHORT" and d2r > 8.0) or
                                       (side == "LONG"  and d2s > 8.0)))

        approval_mode = "auto" if high_conf else "manual"

        if side == "SHORT":
            # 做空：应在压力位附近（d2r 越小越近），距离>5%视为异常
            if res and d2r is not None and d2r > 5.0:
                issues.append({
                    "type": "wrong_direction",
                    "severity": "high" if high_conf else "medium",
                    "pair": p["pair"],
                    "side": side,
                    "action": "inject_long_pair",
                    "reason": (
                        "🔴 [高置信] 做空距压力位太远(%.1f%%)！方向明显错误！\n"
                        "当前价%.2f | 多时线确认%d条 | 支撑%.2f | 压力%.2f\n"
                        "建议：平仓"
                        % (d2r, cur, tf_conf, sup or 0, res)
                        if high_conf else
                        "📋 [半自动审批] 做空距压力位太远(%.1f%%)，方向存疑。\n"
                        "当前价%.2f | 多时线确认%d条 | 支撑%.2f | 压力%.2f\n"
                        "当前确认度不足以自动执行，请爸审批。"
                        % (d2r, cur, tf_conf, sup or 0, res)
                    ),
                    "details": {
                        "pair":                   p["pair"],
                        "wrong_side":             side,
                        "correct_side":           "LONG",
                        "support":                round(sup, 4) if sup     else None,
                        "resistance":             round(res, 4) if res     else None,
                        "current_price":          round(cur, 4),
                        "dist_to_support_pct":    d2s,
                        "dist_to_resistance_pct": d2r,
                        "support_touches":        t_sup,
                        "resistance_touches":     t_res,
                        "tf_confirmed":           tf_conf,
                        "confidence":             "high" if high_conf else "low",
                        "approval_mode":          approval_mode,
                        "entry_price":            round(p["entry"], 4),
                        "bot":                   p.get("bot", ""),
                    }
                })

        elif side == "LONG":
            # 做多：应在支撑位附近（d2s 越小越近），距离>5%视为异常
            if sup and d2s is not None and d2s > 5.0:
                issues.append({
                    "type": "wrong_direction",
                    "severity": "high" if high_conf else "medium",
                    "pair": p["pair"],
                    "side": side,
                    "action": "inject_short_pair",
                    "reason": (
                        "🔴 [高置信] 做多距支撑位太远(%.1f%%)！方向明显错误！\n"
                        "当前价%.2f | 多时线确认%d条 | 支撑%.2f | 压力%.2f\n"
                        "建议：平仓"
                        % (d2s, cur, tf_conf, sup, res or 0)
                        if high_conf else
                        "📋 [半自动审批] 做多距支撑位太远(%.1f%%)，方向存疑。\n"
                        "当前价%.2f | 多时线确认%d条 | 支撑%.2f | 压力%.2f\n"
                        "当前确认度不足以自动执行，请爸审批。"
                        % (d2s, cur, tf_conf, sup, res or 0)
                    ),
                    "details": {
                        "pair":                   p["pair"],
                        "wrong_side":             side,
                        "correct_side":           "SHORT",
                        "support":                round(sup, 4) if sup     else None,
                        "resistance":             round(res, 4) if res     else None,
                        "current_price":          round(cur, 4),
                        "dist_to_support_pct":    d2s,
                        "dist_to_resistance_pct": d2r,
                        "support_touches":        t_sup,
                        "resistance_touches":     t_res,
                        "tf_confirmed":           tf_conf,
                        "confidence":             "high" if high_conf else "low",
                        "approval_mode":          approval_mode,
                        "entry_price":            round(p["entry"], 4),
                        "bot":                   p.get("bot", ""),
                    }
                })

    return positions, issues





def load_proposals():

    f = EDICT_DATA / "bingbu_pending_proposals.json"

    if f.exists():

        try:

            return json.loads(f.read_text())

        except Exception:

            pass

    return []




def save_proposals(proposals):
    _atomic_write_json(EDICT_DATA / "bingbu_pending_proposals.json", proposals)




def make_proposals(issues: list, new_signals: list = None) -> list[dict]:
    """生成干预提案（支持下单审计+新信号扫描）"""
    new_signals = new_signals or []
    now = dt.datetime.now()
    proposals = load_proposals()

    recent = [p for p in proposals
              if p.get("status") == "pending"
              and p.get("proposal_type") == "order_audit"
              and (now - dt.datetime.fromisoformat(p.get("created_at", now.isoformat()))).seconds < 600]

    recent_pairs = {p.get("pair") for p in recent}
    new = []
    seq = len([p for p in proposals if p.get("proposal_type") == "order_audit"]) + 1

    def _make_code() -> str:
        nonlocal seq
        code = "BS-OA-%s-%02d" % (now.strftime("%m%d%H%M%S"), seq)
        seq += 1
        return code

    for iss in issues:
        pair = iss["details"]["pair"]
        if pair in recent_pairs:
            continue
        code = _make_code()
        proposals.append({
            "id": code, "code": code, "proposal_type": "order_audit",
            "action": iss["action"], "pair": pair, "reason": iss["reason"],
            "details": iss["details"],
            "created_at": now.isoformat(),
            "expires_at": (now + dt.timedelta(minutes=15)).isoformat(),
            "status": "pending",
            "executed_at": None, "result": None,
        })
        new.append(proposals[-1])
        recent_pairs.add(pair)

    for sig in new_signals:
        pair = sig["pair"]
        if pair in recent_pairs:
            continue
        code = _make_code()
        proposals.append({
            "id": code, "code": code, "proposal_type": "order_audit",
            "action": sig["action"], "pair": pair, "reason": sig["reason"],
            "details": sig["details"],
            "created_at": now.isoformat(),
            "expires_at": (now + dt.timedelta(minutes=15)).isoformat(),
            "status": "pending",
            "executed_at": None, "result": None,
        })
        new.append(proposals[-1])
        recent_pairs.add(pair)

    if new:
        save_proposals(proposals)
    return new




def send_card(issues: list, new_proposals: list, positions: list) -> dict:
    """发送飞书卡片：每个提案一张独立卡片，按钮在标题正下方（统一格式）"""
    from bingbu_card_builder import build_bingbu_card

    now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    long_n  = sum(1 for p in positions if p["side"] == "LONG")
    short_n = sum(1 for p in positions if p["side"] == "SHORT")
    base_url = "https://openclaw.tianlu2026.org"

    results = []

    # ── 1. 先发一张总览卡（方向异常持仓）─────────────────────────
    issue_txt = ""
    for iss in issues:
        d = iss["details"]
        issue_txt += (
            "  🔴 **%s** [%s]\n"
            "    当前:%.2f | 支撑:%s | 压力:%s\n"
            "    距支撑:%.1f%% | 距压力:%.1f%%\n    %s\n\n"
        ) % (
            d["pair"], d["wrong_side"],
            d["current"],
            "%.2f" % d["support"] if d["support"] else "N/A",
            "%.2f" % d["resistance"] if d["resistance"] else "N/A",
            d["dist_to_support_pct"] or 0, d["dist_to_resistance_pct"] or 0,
            iss["reason"],
        )

    summary_card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"📊 兵部持仓总览 · {now_str}"},
                "template": "orange"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": (
                    f"**总持仓：{len(positions)} 个 | 多:{long_n} 空:{short_n}**"
                )}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": (
                    f"**🚨 方向异常持仓：**\n{issue_txt or '  无异常 ✅'}"
                )}},
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": (
                    f"**📋 S/R信号提案：{len(new_proposals)} 条**（详见下方各提案卡片）"
                )}},
            ],
        },
    }
    _send_feishu(summary_card)

    # ── 2. 每个提案发一张独立卡片（统一格式）──────────────────────
    for p in new_proposals:
        code    = p["id"]
        pair    = p.get("pair", "")
        action  = p.get("action", "")
        reason  = p.get("reason", "")
        details = p.get("details", {})
        sig_type = details.get("signal_type", "")

        # 动作emoji
        if "long" in action:
            emoji, color = "📈", "green"
        elif "short" in action:
            emoji, color = "📉", "orange"
        else:
            emoji, color = "⚡", "red"

        # 类型标签
        if "entry_long" in sig_type:
            type_label = f"{emoji} 入场做多信号"
        elif "entry_short" in sig_type:
            type_label = f"{emoji} 入场做空信号"
        elif "counter" in sig_type:
            type_label = f"⚠️ 对手信号提案"
        else:
            type_label = f"{emoji} S/R信号提案"

        # 按钮URL
        if action in ("inject_long_pair", "inject_short_pair"):
            approve_url = f"{base_url}/bingbu/approve?code={code}"
        elif action in ("force_exit_pair", "exit"):
            approve_url = f"{base_url}/bingbu/exit/{code}"
        else:
            approve_url = f"{base_url}/bingbu/approve?code={code}"
        reject_url = f"{base_url}/bingbu/reject?code={code}"

        # 提案信息
        cur     = details.get("current_price", 0)
        sup     = details.get("support", 0)
        res     = details.get("resistance", 0)
        d2sup   = details.get("dist_to_support_pct", 0)
        d2res   = details.get("dist_to_resistance_pct", 0)
        t_sup   = details.get("support_touches", 0)
        t_res   = details.get("resistance_touches", 0)
        conf    = details.get("confidence", 80)
        existing = details.get("existing_side", "")
        port     = details.get("port", 0)
        trade_id = details.get("trade_id", "")

        # body内容：S/R数据 + 置信度信息
        body_lines = []
        if existing:
            body_lines += [
                f"**📍 持仓机器人：** {BOT_LABELS.get(port, f'端口 {port}')}（端口 {port}）",
                f"**Trade ID：** `{trade_id}`",
                f"**持仓方向：** {existing}",
                f"**入场价：** ${details.get('entry_price', cur):.4f}",
            ]
        else:
            body_lines += [
                f"**当前价：** ${cur:.4f}",
                f"**支撑位：** ${sup:.4f}（距{d2sup:.1f}%）| 触底{t_sup}次",
                f"**压力位：** ${res:.4f}（距{d2res:.1f}%）| 触顶{t_res}次",
            ]
        body_lines += [
            f"**置信度：** {conf}%",
            f"**信号类型：** {sig_type.replace('scan_', '').replace('_', ' ')}",
        ]

        card = build_bingbu_card(
            action=action,
            proposal_id=code,
            pair=pair,
            reason=reason,
            approve_url=approve_url,
            reject_url=reject_url,
            body_text="\n".join(body_lines),
            expires_minutes=15,
        )
        # 覆盖header（用统一格式）
        card["card"]["header"] = {
            "title": {"tag": "plain_text", "content": f"{type_label} · {now_str}"},
            "template": color,
        }
        ok = _send_feishu(card)
        results.append({"id": code, "ok": ok})

    return {"cards_sent": len(results), "results": results}


def _send_feishu(card: dict) -> bool:
    """发送飞书卡片"""
    try:
        payload = json.dumps(card, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(FEISHU_WEBHOOK, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()).get("StatusCode", 0) == 0
    except Exception as e:
        print(f"[send_card] 飞书发送失败: {e}")
        return False




def main():

    print("[%s] 🚨 兵部下单审计开始..." % dt.datetime.now().strftime("%H:%M:%S"))

    positions = get_positions()

    print("  持仓: %d 个" % len(positions))

    positions, issues = audit(positions)

    print("  方向异常: %d 条" % len(issues))

    for iss in issues:

        print("  🔴 %s %s" % (iss["pair"], iss["side"]))

    if issues:

        new_proposals = make_proposals(issues)

        print("  新建提案: %d 条" % len(new_proposals))

        if new_proposals:
            result = send_card(issues, new_proposals, positions)
            print("  飞书: %s" % result.get("StatusMessage", "?"))
        else:
            print("  ⚠️ 异常持仓已在待审批中，跳过重复提案")

    else:

        print("  ✅ 方向正常")

    # 也检查已有的待审批提案并发送卡片
    proposals = load_proposals()
    pending = [p for p in proposals if p.get("status") == "pending" and p.get("proposal_type") == "order_audit"]
    if pending:
        print("  📋 已有待审批提案: %d 条" % len(pending))
        result = send_card([], pending, positions)
        print("  飞书(待审批): %s" % result.get("StatusMessage", "?"))

    return len(issues)




# ─────────────────────────────────────────────────────────────
# 自动扫描模式（逻辑一 + 逻辑二）
# ─────────────────────────────────────────────────────────────

def auto_scan() -> int:
    """自动扫描：逻辑一（入场信号）+ 逻辑二（对手信号冲突）"""
    print("[%s] 🚀 兵部自动S/R信号扫描..." % dt.datetime.now().strftime("%H:%M:%S"))

    # 获取持仓
    positions = get_positions()
    occupied_pairs = {p["pair"] for p in positions}
    print("  持仓: %d 个" % len(positions))

    # 获取白名单交易对
    all_pairs = get_whitelist_pairs()
    if not all_pairs:
        print("  ⚠️ 无法获取白名单，使用默认交易对")
        all_pairs = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT"]

    # 空仓交易对（逻辑一）
    flat_pairs = [p for p in all_pairs if p not in occupied_pairs]
    print("  空仓交易对: %d 个" % len(flat_pairs))

    # 逻辑一扫描
    entry_signals = scan_entry_signals(flat_pairs)
    print("  逻辑一[入场信号]: %d 条" % len(entry_signals))
    for s in entry_signals:
        icon = "🚀" if s["direction"] == "LONG" else "📉"
        print("  %s %s %s (信心%d)" % (
            icon, s["pair"], s["direction"],
            s["details"]["confidence"],
        ))

    # 逻辑二扫描
    counter_signals = scan_counter_signals(positions)
    print("  逻辑二[对手信号]: %d 条" % len(counter_signals))
    for s in counter_signals:
        print("  ⚠️ %s %s → %s (信心%d)" % (
            s["pair"], s["details"]["existing_side"],
            s["direction"], s["details"]["confidence"],
        ))

    all_signals = entry_signals + counter_signals
    if not all_signals:
        print("  ✅ 未检测到S/R信号")
        return 0

    # 生成提案
    new_proposals = make_proposals([], new_signals=all_signals)
    print("  新建提案: %d 条" % len(new_proposals))

    if new_proposals:
        # 发送飞书卡片
        result = send_card([], new_proposals, positions)
        print("  飞书(新提案): %s" % result.get("StatusMessage", "?"))

    # 也检查已有的待审批提案
    proposals = load_proposals()
    pending = [p for p in proposals if p.get("status") == "pending" and p.get("proposal_type") == "order_audit"]
    if pending:
        print("  📋 已有待审批提案: %d 条" % len(pending))
        result = send_card([], pending, positions)
        print("  飞书(待审批): %s" % result.get("StatusMessage", "?"))

    return len(all_signals)




if __name__ == "__main__":

    args = sys.argv[1:]

    if "--auto-scan" in args or "-s" in args:
        ret = auto_scan()
        sys.exit(0 if ret >= 0 else 1)
    else:
        ret = main()
        sys.exit(0)