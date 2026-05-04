#!/usr/bin/env python3
"""
兵部舆情监测处理器（审核制）
所有干预均需人工审核后方可执行，不可自动执行。
"""

import json
import sys
import time
import random
import string
from datetime import datetime, timedelta
from pathlib import Path
import requests
import base64

# 路径配置
HOME = Path.home()
SENTIMENT_FILE = HOME / ".sentiment_latest.json"
EDICT_DATA = Path("/Users/luxiangnan/edict/data")
EDICT_DATA.mkdir(parents=True, exist_ok=True)

FREEZE_FILE = EDICT_DATA / "bingbu_freeze.json"
INJECT_FILE = EDICT_DATA / "bingbu_sentiment_inject.json"
PROPOSAL_FILE = EDICT_DATA / "bingbu_pending_proposals.json"
PENDING_FILE = EDICT_DATA / "pending_approvals.json"

# ── C-1/C-2 共享文件路径（与api_autopilot对齐）──
_STORAGE = Path("/Volumes/TianLu_Storage/tianlu_cache/autopilot")
_STORAGE.mkdir(parents=True, exist_ok=True)
MANUAL_EXIT_LOG = _STORAGE / "manual_exit_log.json"
INJECT_RESULT_FILE = _STORAGE / "inject_result.json"

# 兵部外网访问基础URL（通过环境变量传递，server.py 启动时设置）
import os as _os
from pathlib import Path as _Path

_PUBLIC_BASE_FILE = _Path(__file__).parent / "data" / ".public_base_url"

def _pub() -> str:
    """动态获取外网基础URL（优先环境变量，其次配置文件）"""
    env_val = _os.environ.get('BINGBU_PUBLIC_BASE', '')
    if env_val:
        return env_val
    # fallback: 从配置文件读取（server.py 启动时写入）
    if _PUBLIC_BASE_FILE.exists():
        try:
            return _PUBLIC_BASE_FILE.read_text().strip()
        except:
            pass
    return ''

# 飞书 Webhook（统一发到天禄量化交易汇报群）
FEISHU_BINGBU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"

def _feishu_post(card: dict, webhook: str = None) -> bool:
    """发送飞书卡片/消息，自动禁用代理（不走5020）"""
    url = webhook or FEISHU_BINGBU_WEBHOOK
    try:
        session = requests.Session()
        session.trust_env = False  # 禁用环境变量代理
        r = session.post(url, json=card, timeout=10)
        return r.status_code == 200
    except Exception:
        return False

# FreqTrade 机器人配置（全部 Basic Auth）
def _basic_auth(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"

FREQTRADE_CONFIGS = {
    9090: {
        "host": "http://127.0.0.1:9090",
        "auth": _basic_auth("freqtrade", "freqtrade"),
        "label": "Gate-17656685222",
        "exchange": "gate",
    },
    9091: {
        "host": "http://127.0.0.1:9091",
        "auth": _basic_auth("freqtrade", "freqtrade"),
        "label": "Gate-85363904550",
        "exchange": "gate",
    },
    9092: {
        "host": "http://127.0.0.1:9092",
        "auth": _basic_auth("freqtrade", "freqtrade"),
        "label": "Gate-15637798222",
        "exchange": "gate",
    },
    9093: {
        "host": "http://127.0.0.1:9093",
        "auth": _basic_auth("admin", "Xy@06130822"),
        "label": "OKX-15637798222",
        "exchange": "okx",
    },
    9094: {
        "host": "http://127.0.0.1:9094",
        "auth": _basic_auth("admin", "Xy@06130822"),
        "label": "OKX-BOT85363904550",
        "exchange": "okx",
    },
    9095: {
        "host": "http://127.0.0.1:9095",
        "auth": _basic_auth("admin", "Xy@06130822"),
        "label": "OKX-BOTa44056283",
        "exchange": "okx",
    },
    9096: {
        "host": "http://127.0.0.1:9096",
        "auth": _basic_auth("admin", "Xy@06130822"),
        "label": "OKX-BHB16638759999",
        "exchange": "okx",
    },
    9097: {
        "host": "http://127.0.0.1:9097",
        "auth": _basic_auth("admin", "Xy@06130822"),
        "label": "OKX-17656685222",
        "exchange": "okx",
    },
}

# 导入干预记录模块
sys.path.insert(0, str(Path(__file__).parent))
from intervention_store import add_intervention


# ─────────────────────────────────────────
#  工具函数
# ─────────────────────────────────────────

def _bot_state(port: int, cfg: dict) -> str:
    """获取机器人状态: running / stopped / starting"""
    try:
        resp = requests.get(
            f"{cfg['host']}/api/v1/show_config",
            headers={"Authorization": cfg["auth"]},
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json().get("state", "unknown")
    except:
        pass
    return "unknown"


def _ensure_running(port: int, cfg: dict) -> bool:
    """确保机器人处于 running 状态"""
    state = _bot_state(port, cfg)
    if state == "running":
        return True
    if state in ("stopped", "starting"):
        try:
            resp = requests.post(
                f"{cfg['host']}/api/v1/start",
                headers={"Authorization": cfg["auth"]},
                timeout=5,
            )
            if resp.status_code == 200:
                time.sleep(2)
                return _bot_state(port, cfg) == "running"
        except:
            pass
    return state == "running"


def load_sentiment() -> dict:
    """读取天福舆情数据"""
    if not SENTIMENT_FILE.exists():
        return {}
    try:
        with open(SENTIMENT_FILE) as f:
            return json.load(f)
    except:
        return {}


def _generate_code() -> str:
    """生成6位审批码"""
    return "".join(random.choices(string.digits, k=6))


def _get_bot_status_summary() -> str:
    """获取所有机器人状态摘要"""
    lines = []
    for port, cfg in FREQTRADE_CONFIGS.items():
        state = _bot_state(port, cfg)
        emoji = "🟢" if state == "running" else "🔴"
        lines.append(f"  {emoji} {cfg['label']}：{state}")
    return "\n".join(lines)


def _get_current_positions() -> list:
    """获取所有机器人当前持仓

    FreqTrade /api/v1/status 返回的 amount 字段：
    - 多头：正数（当前剩余持仓量）
    - 空头：负数（绝对值=当前剩余持仓量）
    因此必须用 abs() 取正值。
    """
    all_positions = []
    for port, cfg in FREQTRADE_CONFIGS.items():
        try:
            resp = requests.get(
                f"{cfg['host']}/api/v1/status",
                headers={"Authorization": cfg["auth"]},
                timeout=5,
            )
            if resp.status_code == 200:
                for pos in resp.json():
                    if pos.get("is_open"):
                        raw_amount = float(pos.get("amount") or 0)
                        all_positions.append({
                            "bot": cfg["label"],
                            "port": port,
                            "pair": pos.get("pair", "").replace(":USDT", ""),
                            "side": "SHORT" if pos.get("is_short") else "LONG",
                            "amount": round(abs(raw_amount), 4),
                            "pnl": round(float(pos.get("profit_abs") or 0), 2),
                            "profit_pct": round(float(pos.get("profit_pct") or 0), 2),
                            "entry": round(float(pos.get("open_rate") or 0), 2),
                            "liq": round(float(pos.get("liquidation_price") or 0), 2),
                            "lev": pos.get("leverage", 1),
                        })
        except:
            pass
    return all_positions


def _format_positions(positions: list) -> str:
    """格式化持仓列表"""
    if not positions:
        return "  ✅ 目前无持仓"
    lines = []
    for p in positions:
        pnl = p["pnl"]
        side = p["side"]
        # 做空盈亏判断：pnl > 0 = 赚钱，pnl < 0 = 亏钱
        is_profit = pnl >= 0
        pnl_label = "浮盈" if is_profit else "浮亏"
        pnl_emoji = "🟢" if is_profit else "🔴"
        # 做空 profit_pct 为负数时（表示赚钱），取绝对值显示
        pct = p["profit_pct"]
        pct_display = abs(pct) if (side == "SHORT" and pct < 0) else pct
        lines.append(
            f"  {pnl_emoji} {p['pair']} | {side} | "
            f"{p['amount']} | 入场 {p['entry']} | "
            f"{pnl_label} {pnl} USDT ({pct_display:+.2f}%) | "
            f"{p['lev']}x | 强平 {p['liq']}"
        )
    return "\n".join(lines)


# ─────────────────────────────────────────
#  S/R 位置检查（干预前置条件）
# ─────────────────────────────────────────

def _fetch_positions_sr(positions: list) -> list:
    """
    获取每个持仓的当前价格与S/R位置
    直接调用交易所公开API（Gate.io / OKX），无需认证
    S/R计算：近20根1h K线的摆动高/低点
    """
    import concurrent.futures

    def _fetch_one(pos: dict) -> dict:
        pair_raw = pos["pair"]
        # 统一格式：BTC/USDT → BTC_USDT
        pair_gate = pair_raw.replace("/", "_")
        pair_okx = pair_raw.replace("/", "-")
        current_price = 0.0
        support_levels = []
        resistance_levels = []

        # ── Gate.io 公开API ─────────────────
        try:
            # 当前价
            ticker_r = requests.get(
                f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={pair_gate}",
                timeout=8,
            )
            if ticker_r.status_code == 200:
                tickers = ticker_r.json()
                if tickers and isinstance(tickers, list):
                    current_price = float(tickers[0].get("last", 0))

            # 近500根15M K线（当日数据）
            Kline_r = requests.get(
                f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={pair_gate}&interval=15m&limit=500",
                timeout=8,
            )
            if Kline_r.status_code == 200:
                klines = Kline_r.json()
                if klines and isinstance(klines, list) and len(klines) > 0:
                    # 只用当日15M K线计算S/R
                    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                    today_start_ts = int(today_start.timestamp())
                    today_highs = [float(k[3]) for k in klines if int(k[0]) >= today_start_ts]
                    today_lows  = [float(k[4]) for k in klines if int(k[0]) >= today_start_ts]
                    if len(today_highs) >= 3:
                        recent_highs = sorted(today_highs)[-3:]
                        recent_lows  = sorted(today_lows)[:3]
                    elif today_highs:
                        recent_highs = [max(today_highs)]
                        recent_lows  = [min(today_lows)]
                    else:
                        recent_highs, recent_lows = [], []
                    resistance_levels = [{"level": round(h, 2)} for h in recent_highs]
                    support_levels    = [{"level": round(l, 2)} for l in recent_lows]
        except Exception as e:
            pass

        # ── OKX 公开API（备用）────────────────
        if not current_price:
            try:
                okx_r = requests.get(
                    f"https://www.okx.com/api/v5/market/ticker?instId={pair_okx}",
                    timeout=8,
                )
                if okx_r.status_code == 200:
                    d = okx_r.json()
                    if d.get("data"):
                        current_price = float(d["data"][0].get("last", 0))
            except:
                pass

        pos["current_price"] = current_price or pos.get("entry", 0)
        pos["support_levels"]   = support_levels
        pos["resistance_levels"] = resistance_levels
        pos["nearest_support"]    = support_levels[0]["level"]   if support_levels   else None
        pos["nearest_resistance"]  = resistance_levels[0]["level"] if resistance_levels else None

        # 计算距关键位距离
        current = current_price or pos.get("entry", 0)
        if current:
            if pos["side"] == "LONG" and pos["nearest_support"]:
                pos["dist_to_support_pct"] = round((current - pos["nearest_support"]) / current * 100, 2)
            elif pos["side"] == "SHORT" and pos["nearest_resistance"]:
                pos["dist_to_resistance_pct"] = round((pos["nearest_resistance"] - current) / current * 100, 2)

        return pos

    if not positions:
        return positions

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(_fetch_one, p): p for p in positions}
        results = []
        for f in concurrent.futures.as_completed(futures, timeout=20):
            results.append(f.result())
    return results


def _format_positions_with_sr(positions: list) -> str:
    """
    格式化持仓（含S/R位置信息）
    多单：显示压力位和距压力位距离
    空单：显示支撑位和距支撑位距离
    """
    if not positions:
        return "  ✅ 目前无持仓"

    lines = []
    for p in positions:
        pnl = p.get("pnl", 0)
        side = p["side"]
        is_profit = pnl >= 0
        pnl_label = "浮盈" if is_profit else "浮亏"
        pnl_emoji = "🟢" if is_profit else "🔴"
        if side == "LONG":
            r = p.get("nearest_resistance")
            dist = p.get("dist_to_resistance_pct")
            sr_info = f"压力{r} (距{dist}%)" if r and dist is not None else f"压力{r or '?'}"
        else:
            s = p.get("nearest_support")
            dist = p.get("dist_to_support_pct")
            sr_info = f"支撑{s} (距{dist}%)" if s and dist is not None else f"支撑{s or '?'}"

        lines.append(
            f"  {pnl_emoji} {p['pair']} | {side} | "
            f"入场{p.get('entry','?')} | 现价{p.get('current_price','?')} | "
            f"{pnl_label} {pnl} USDT | {p['lev']}x | "
            f"❄️{sr_info}"
        )
    return "\n".join(lines)


def _should_intervene(position: dict, action: str) -> dict:
    """
    判断是否应该干预（基于S/R位置）
    action: "stop_loss" / "take_profit" / "emergency_exit"
    返回: {should: bool, reason: str, distance_pct: float}
    """
    side = position.get("side")
    current = position.get("current_price", 0)
    entry = position.get("entry", 0)

    if not current or not entry:
        return {"should": False, "reason": "无当前价格数据"}

    if side == "LONG":
        support = position.get("nearest_support")
        if not support:
            return {"should": False, "reason": "无支撑位数据"}
        dist_to_support = round((current - support) / current * 100, 2)
        # 多单紧急平仓/止损：价格距支撑位 ≤5%
        if action in ("emergency_exit", "stop_loss"):
            if dist_to_support <= 5:
                return {
                    "should": True,
                    "reason": f"价格${current}距支撑${support}仅{dist_to_support}%",
                    "distance_pct": dist_to_support,
                }
            else:
                return {
                    "should": False,
                    "reason": f"价格${current}距支撑${support}为{dist_to_support}%（>5%），未到紧急位",
                    "distance_pct": dist_to_support,
                }
        # 多单止盈：价格接近压力位
        resistance = position.get("nearest_resistance")
        if action == "take_profit" and resistance:
            dist_to_resistance = round((resistance - current) / current * 100, 2)
            if dist_to_resistance <= 3:  # 距压力位3%内
                return {
                    "should": True,
                    "reason": f"价格接近压力位${resistance}（距{dist_to_resistance}%）",
                    "distance_pct": dist_to_resistance,
                }
            return {"should": False, "reason": f"距压力位${resistance}为{dist_to_resistance}%（>3%）"}

    elif side == "SHORT":
        resistance = position.get("nearest_resistance")
        if not resistance:
            return {"should": False, "reason": "无压力位数据"}
        dist_to_resistance = round((resistance - current) / current * 100, 2)
        # 空单紧急平仓/止损：价格距压力位 ≤5%
        if action in ("emergency_exit", "stop_loss"):
            if dist_to_resistance <= 5:
                return {
                    "should": True,
                    "reason": f"价格${current}距压力${resistance}仅{dist_to_resistance}%",
                    "distance_pct": dist_to_resistance,
                }
            return {
                "should": False,
                "reason": f"价格${current}距压力${resistance}为{dist_to_resistance}%（>5%），未到紧急位",
                "distance_pct": dist_to_resistance,
            }
        # 空单止盈：价格接近支撑位
        support = position.get("nearest_support")
        if action == "take_profit" and support:
            dist_to_support = round((current - support) / current * 100, 2)
            if dist_to_support <= 3:
                return {
                    "should": True,
                    "reason": f"价格接近支撑位${support}（距{dist_to_support}%）",
                    "distance_pct": dist_to_support,
                }
            return {"should": False, "reason": f"距支撑位${support}为{dist_to_support}%（>3%）"}

    return {"should": False, "reason": "条件不满足"}


# ─────────────────────────────────────────
#  舆情监测 → 提案生成（审核制核心）
#  所有黑天鹅干预必须先推送给用户审核，不自动执行
# ─────────────────────────────────────────

def check_sentiment_proposal() -> dict:
    """
    检查舆情，发现黑天鹅则生成干预提案推送审核。
    判断逻辑：
      1. 检测 black_swan_alert = True 且 2类以上
      2. 获取当前持仓及S/R位置
      3. 判断哪些持仓应该干预（多单价格≤支撑位，空单价格≥压力位）
      4. 生成提案推送给用户，用户批准后才执行
    防重复：如果已有 pending 的黑天鹅冻结提案，跳过
    返回: {triggered, action, reason, proposal_id}
    """
    sig = load_sentiment()
    if not sig:
        return {"triggered": False, "action": "none", "reason": "无舆情数据"}

    black_swan = sig.get("black_swan_alert", False)
    bs_cats = sig.get("black_swan_categories", [])
    urgency = sig.get("sentiment_urgency", 0)
    confidence = sig.get("sentiment_confidence", 0)
    fg_val = sig.get("fear_greed_value", 50)

    # ── 黑天鹅检测 ──────────────────────
    if not black_swan or len(bs_cats) < 2:
        return {"triggered": False, "action": "none", "reason": "未触发黑天鹅条件"}

    # ── 防重复：如果已有 pending 的黑天鹅冻结提案，跳过 ─
    existing = load_proposals()
    pending_bs = [
        p for p in existing
        if p["status"] == "pending"
        and p["action"] == "black_swan_freeze"
    ]
    if pending_bs:
        return {
            "triggered": False,
            "action": "already_pending",
            "reason": f"已有 pending 提案 {pending_bs[0]['id']}，等待审核中，不再重复推送",
            "pending_id": pending_bs[0]["id"],
        }

    # ── 获取持仓+S/R位置 ─────────────────
    positions = _get_current_positions()
    positions_sr = _fetch_positions_sr(positions)

    # ── 分析哪些持仓需要干预 ─────────────
    actionable_positions = []
    sr_summary = []

    for pos in positions_sr:
        # 紧急止损（价格已到S/R临界区）
        check = _should_intervene(pos, "emergency_exit")
        if check["should"]:
            actionable_positions.append({
                **pos,
                "intervene_action": "emergency_exit",
                "intervene_reason": check["reason"],
            })
            sr_summary.append(
                f"  ⚠️ {pos['pair']} {pos['side']}：{check['reason']} → 建议紧急平仓"
            )
        else:
            sr_summary.append(
                f"  ✅ {pos['pair']} {pos['side']}：{check['reason']} → 继续观望"
            )

    if not actionable_positions:
        # 有黑天鹅但价格未到关键位 → 推送观察通知，不干预
        summary_text = "\n".join(sr_summary)
        _send_black_swan_watch_notification(
            sig=sig,
            positions_sr=positions_sr,
            summary=summary_text,
        )
        return {
            "triggered": False,
            "action": "watch_only",
            "reason": "黑天鹅已识别，但价格未到关键位，继续观望",
            "sr_summary": sr_summary,
        }

    # ── 生成干预提案 ────────────────────
    proposal = create_proposal(
        action="black_swan_freeze",
        reason=f"黑天鹅爆发({len(bs_cats)}类: {', '.join(bs_cats)})，价格已到关键位",
        details={
            "urgency": urgency,
            "confidence": confidence,
            "fear_greed": fg_val,
            "black_swan_categories": bs_cats,
            "actionable_positions": actionable_positions,
            "watch_positions": [
                {k: v for k, v in p.items() if k != "support_levels" and k != "resistance_levels"}
                for p in positions_sr if not any(a["pair"] == p["pair"] for a in actionable_positions)
            ],
        },
        sentiment=sig,
        positions=positions_sr,  # 已附加S/R信息
    )

    return {
        "triggered": True,
        "action": "black_swan_freeze",
        "proposal_id": proposal.get("id"),
        "proposal_code": proposal.get("code"),
        "reason": f"黑天鹅{len(bs_cats)}类: {', '.join(bs_cats)}，{len(actionable_positions)}个持仓已到关键位",
        "actionable_count": len(actionable_positions),
        "watch_count": len(positions_sr) - len(actionable_positions),
    }


def _send_black_swan_watch_notification(sig: dict, positions_sr: list, summary: str) -> bool:
    """黑天鹅已识别但价格未到关键位 → 推送观察通知（不干预）"""
    bs_cats = sig.get("black_swan_categories", [])
    urgency = sig.get("sentiment_urgency", 0)
    fg_val = sig.get("fear_greed_value", 50)
    direction = sig.get("sentiment_direction", "NEUTRAL")

    card = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "⚠️ 兵部黑天鹅观察通知 ｜ 无需操作"},
                "template": "yellow",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": (
                        f"**🚨 黑天鹅已识别**（{len(bs_cats)}类: {', '.join(bs_cats)})\n"
                        f"**紧急度：{urgency}/10** | **恐惧指数：{fg_val}**\n\n"
                        f"**但价格未到关键位，所有持仓继续观望，不执行干预。**\n\n"
                        f"━━━━━━━━ 持仓状态 ━━━━━━━━\n{summary}\n\n"
                        f"**📌 处置建议**：保持监控，价格触及支撑/压力位时再干预"
                    )},
                },
            ],
        },
    }
    try:
        _feishu_post(card)
        return r.status_code == 200
    except:
        return False


# ─────────────────────────────────────────
#  提案管理（审核制核心）
# ─────────────────────────────────────────

def load_proposals() -> list:
    """加载待审批提案（自动清除已超时提案）"""
    if not PROPOSAL_FILE.exists():
        return []
    try:
        proposals = json.loads(PROPOSAL_FILE.read_text())
        now = datetime.now()
        valid = []
        for p in proposals:
            expires_str = p.get("expires_at", "")
            if expires_str:
                try:
                    expires = datetime.fromisoformat(expires_str)
                    if expires <= now:
                        p["status"] = "expired"
                        continue
                except (ValueError, TypeError):
                    pass
            valid.append(p)
        if len(valid) != len(proposals):
            save_proposals(valid)
        return valid
    except:
        return []


def save_proposals(proposals: list):
    """保存提案列表"""
    PROPOSAL_FILE.write_text(json.dumps(proposals, ensure_ascii=False, indent=2))


def load_pending() -> list:
    """加载待审批黑天鹅提案（pending_approvals.json）"""
    if not PENDING_FILE.exists():
        return []
    try:
        return json.loads(PENDING_FILE.read_text())
    except:
        return []


def save_pending(pending: list):
    """保存待审批黑天鹅提案"""
    PENDING_FILE.write_text(json.dumps(pending, ensure_ascii=False, indent=2))


def create_proposal(
    action: str,
    reason: str,
    details: dict,
    sentiment: dict,
    positions: list = None,
) -> dict:
    """
    创建干预提案并推送飞书审核
    返回: {proposal_id, code, ...}
    """
    proposals = load_proposals()

    # 清除已过期提案（超过15分钟）
    now = datetime.now()
    valid_proposals = [
        p for p in proposals
        if datetime.fromisoformat(p["expires_at"]) > now
    ]

    code = _generate_code()
    expires_at = (now + timedelta(minutes=15)).isoformat()

    # 黑天鹅冻结：使用已附加S/R信息的持仓列表
    if positions is not None:
        positions_for_proposal = positions
    elif action == "black_swan_freeze":
        positions_for_proposal = _fetch_positions_sr(_get_current_positions())
    else:
        positions_for_proposal = _get_current_positions()

    proposal = {
        "id": f"IV-{len(valid_proposals) + 1:03d}",
        "code": code,
        "action": action,
        "reason": reason,
        "details": details,
        "sentiment": {
            "direction": sentiment.get("sentiment_direction", "NEUTRAL"),
            "confidence": sentiment.get("sentiment_confidence", 0),
            "urgency": sentiment.get("sentiment_urgency", 0),
            "fear_greed": sentiment.get("fear_greed_value", 50),
            "black_swan": sentiment.get("black_swan_alert", False),
        },
        "positions_before": positions_for_proposal,
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "expires_at": expires_at,
        "status": "pending",  # pending / approved / rejected / expired
        "executed_at": None,
        "result": None,
    }

    valid_proposals.insert(0, proposal)
    save_proposals(valid_proposals)

    # 推送飞书审核
    _send_approval_request(proposal)

    return proposal


def _send_approval_request(proposal: dict) -> bool:
    """发送审批请求到飞书群"""
    action_emoji = {
        "force_exit_pair": "🔴",
        "emergency_exit_all": "🚨",
        "inject_long_pair": "📈",
        "inject_short_pair": "📉",
        "freeze_pair": "❄️",
        "freeze": "❄️",
        "black_swan_freeze": "🚨",
    }.get(proposal["action"], "⚡")

    action_label = {
        "force_exit_pair": "指定交易对强制平仓",
        "emergency_exit_all": "全市场双向强平",
        "inject_long_pair": "指定交易对注入做多",
        "inject_short_pair": "指定交易对注入做空",
        "freeze_pair": "冻结指定交易对",
        "freeze": "全市场冻结",
        "black_swan_freeze": "黑天鹅紧急接管",
    }.get(proposal["action"], proposal["action"])

    # 持仓列表（黑天鹅提案显示带S/R信息）
    if proposal["action"] == "black_swan_freeze":
        positions_text = _format_positions_with_sr(proposal["positions_before"])
    else:
        positions_text = _format_positions(proposal["positions_before"])
    sentiment = proposal["sentiment"]

    # 格式化详情
    details = proposal.get("details", {})
    if proposal["action"] == "force_exit_pair":
        detail_text = f"交易对：{details.get('pair', '?')}\n执行操作：多空全平"
    elif proposal["action"] == "emergency_exit_all":
        detail_text = "执行操作：全市场所有持仓多空全平"
    elif proposal["action"] == "inject_long_pair":
        bs = details.get("balance_snapshot", {})
        est_stake = details.get("est_stake_amount")
        stake_pct = details.get("stake_pct")
        detail_text = (f"交易对：{details.get('pair', '?')}\n"
                       f"信号：做多\n"
                       f"信心度：{details.get('confidence', 80)}%\n"
                       f"可用余额：{bs.get('free_usdt', '?')} USDT\n"
                       f"预估下注：{est_stake} USDT ({stake_pct}%)")
    elif proposal["action"] == "inject_short_pair":
        bs = details.get("balance_snapshot", {})
        est_stake = details.get("est_stake_amount")
        stake_pct = details.get("stake_pct")
        detail_text = (f"交易对：{details.get('pair', '?')}\n"
                       f"信号：做空\n"
                       f"信心度：{details.get('confidence', 80)}%\n"
                       f"可用余额：{bs.get('free_usdt', '?')} USDT\n"
                       f"预估下注：{est_stake} USDT ({stake_pct}%)")
    elif proposal["action"] in ("freeze_pair", "freeze"):
        pair = details.get("pair", "全市场")
        detail_text = f"冻结范围：{pair}"
    elif proposal["action"] == "black_swan_freeze":
        # 黑天鹅干预详情
        cats = details.get("black_swan_categories", [])
        urgency = details.get("urgency", 0)
        fg = details.get("fear_greed", 50)
        actionable = details.get("actionable_positions", [])
        watch_pos = details.get("watch_positions", [])
        lines = [f"触发原因：黑天鹅({len(cats)}类: {', '.join(cats)})"]
        lines.append(f"紧急度：{urgency}/10 | 恐惧指数：{fg}")
        lines.append(f"\n需干预持仓（已到S/R关键位）：")
        for p in actionable:
            lines.append(f"  ⚠️ {p['pair']} {p['side']} {p.get('intervene_action','')}: {p.get('intervene_reason','')}")
        if watch_pos:
            lines.append(f"\n观望持仓（价格未到关键位）：")
            for p in watch_pos:
                sr = f"支撑{p.get('nearest_support')} / 压力{p.get('nearest_resistance')}"
                lines.append(f"  ✅ {p['pair']} {p['side']}：{p.get('intervene_reason', '继续观望')} | {sr}")
        detail_text = "\n".join(lines)

    # 分类配置：颜色、标题、标签
    _CATEGORY_MAP = {
        "freeze":              ("❄️ 冻结审批",  "blue",   "🧊 冻结类"),
        "freeze_pair":         ("❄️ 冻结审批",  "blue",   "🧊 冻结类"),
        "black_swan_freeze":   ("🚨 黑天鹅审批", "red",   "🧊 冻结类"),
        "force_exit_pair":     ("🔴 平仓审批",  "red",   "🚨 平仓类"),
        "emergency_exit_all":  ("🔴 平仓审批",  "red",   "🚨 平仓类"),
        "inject_long_pair":    ("📈 注入审批",  "green", "📈 注入类"),
        "inject_short_pair":   ("📉 注入审批",  "green", "📉 注入类"),
    }
    _cat = _CATEGORY_MAP.get(
        proposal["action"], ("⚡ 干预审批", "orange", "⚡ 其他类")
    )
    _card_title, _card_color, _cat_label = _cat

    # 执行命令说明（醒目+颜色）
    _EXEC_COLOR_MAP = {
        "freeze":              ("#0058D5", "❄️", "冻结全市场所有交易对",   "等级：L4（需手动解除）"),
        "freeze_pair":         ("#0058D5", "❄️", f"冻结指定交易对 {details.get('pair', '')}", f"等级：{details.get('level', 'L4')}"),
        "black_swan_freeze":   ("#D93031", "🚨", "黑天鹅紧急接管",       "冻结已达S/R临界位持仓 + 全市场冻结"),
        "force_exit_pair":     ("#D93031", "🔴", f"强制平仓指定交易对 {details.get('pair', '')}", "多空双向全平"),
        "emergency_exit_all":  ("#D93031", "🚨", "全市场双向强平",        "所有持仓多空全平"),
        "inject_long_pair":    ("#188038", "📈", f"注入做多信号 {details.get('pair', '')}", f"信心度：{details.get('confidence', 80)}%"),
        "inject_short_pair":   ("#188038", "📉", f"注入做空信号 {details.get('pair', '')}", f"信心度：{details.get('confidence', 80)}%"),
    }
    _ec = _EXEC_COLOR_MAP.get(
        proposal["action"], ("#E8A000", "⚡", proposal["action"], "")
    )
    _exec_color, _exec_emoji, _exec_main, _exec_sub = _ec

    _NOTE_BG = {
        "freeze": "#E3F2FD",
        "freeze_pair": "#E3F2FD",
        "black_swan_freeze": "#FFEBEE",
        "force_exit_pair": "#FFEBEE",
        "emergency_exit_all": "#FFEBEE",
        "inject_long_pair": "#E8F5E9",
        "inject_short_pair": "#FFF3E0",
    }.get(proposal["action"], "#FFF2E0")

    # 批准按钮底色：与标题Header颜色100%同步
    _APPROVE_BG = {
        "inject_long_pair":   "#2E7D32",  # 深绿
        "inject_short_pair":  "#E65100",  # 深橙
        "force_exit_pair":   "#C62828",  # 深红
        "emergency_exit_all": "#B71C1C",  # 暗红
        "freeze_pair":       "#1565C0",  # 深蓝
        "freeze":           "#1565C0",
        "black_swan_freeze": "#B71C1C",  # 暗红
    }.get(proposal["action"], "#C62828")
    _REJECT_BG = "#C62828"   # 否决：统一深红

    _pub_url = _pub()
    _code = proposal.get("code", proposal["id"])
    _approve_url = f"{_pub_url}/bingbu/approve?code={_code}"
    _reject_url  = f"{_pub_url}/bingbu/reject?code={_code}"

    card = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"{_card_title} · {datetime.now().strftime('%H:%M')}"},
                "template": _card_color,
            },
            "elements": [
                # ── ① 操作类型说明 ────────────────────────────
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**【执行操作】{_exec_emoji} {_exec_main} | {_exec_sub}**"}},
                {"tag": "hr"},
                # ── ② 原生按钮组（高识别度）─────────
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": f"✅ {_exec_main} 批准"},
                            "type": "primary",
                            "url": _approve_url,
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "❌ 否决此提案"},
                            "type": "danger",
                            "url": _reject_url,
                        },
                    ],
                },
                {"tag": "hr"},
                # ── ④ 提案信息 ────────────────────────────────────────
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": (
                        f"**动作：** {_exec_emoji} {action_label}\n"
                        f"**交易对：** `{details.get('pair', '全市场') or '全市场'}`\n"
                        f"**原因：** {proposal['reason']}\n"
                        f"**提案ID：** `{_code}`"
                    )},
                },
                {"tag": "hr"},
                # ── ⑤ 卡片Body ────────────────────────────────────────
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": (
                        f"━━━━━━━━ 详情 ━━━━━━━━\n{detail_text}\n\n"
                        f"━━━━━━━━ 触发依据 ━━━━━━━━\n"
                        f"• 信号方向：{sentiment['direction']}\n"
                        f"• 信心度：{sentiment['confidence']}%\n"
                        f"• 紧急度：{sentiment['urgency']}/10\n"
                        f"• 恐惧指数：{sentiment['fear_greed']}\n"
                        f"• 黑天鹅：{'⚠️ 是' if sentiment['black_swan'] else '✅ 否'}\n\n"
                        f"━━━━━━━━ 当前持仓 ━━━━━━━━\n{positions_text}"
                    )},
                },
            ],
        },
    }

    try:
        _feishu_post(card)
        return r.status_code == 200
    except:
        return False


def approve_proposal(code: str, pair: str = "") -> dict:
    """
    审批通过，执行干预
    支持两个通道：
    1. 黑天鹅审批（pending_approvals.json）→ scripts/monitor_sentiment 版本
    2. 下单审计提案（bingbu_pending_proposals.json）→ dashboard 版本
    code: 审批码（id 或 code 字段均可）
    pair: 交易对（可选，S/R守卫需传入）
    """
    now = datetime.now()

    # ── 通道1：黑天鹅审批（pending_approvals.json）─────────────────
    pending = load_pending()
    for p in pending:
        if p.get("id") == code and p.get("status") == "pending":
            p["status"] = "approved"
            p["executed_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
            save_pending(pending)

            sig = p.get("sentiment", {})
            direction = sig.get("direction", "NEUTRAL")

            # 执行黑天鹅冻结/解冻
            p["code"] = p["id"]  # 确保有code字段供_send_execution_report使用
            if direction in ("SHORT", "LONG"):
                result = _do_emergency_exit_all()  # 全市场双向强平
                save_pending(pending)
                _send_execution_report(p, result)
                return {"ok": True, "proposal_id": p["id"], "action": "black_swan_force_exit", "result": result}
            elif direction == "NEUTRAL":
                result = _do_unfreeze_all()
                save_pending(pending)
                _send_execution_report(p, result)
                return {"ok": True, "proposal_id": p["id"], "action": "black_swan_unfreeze", "result": result}

    # ── 通道2：下单审计提案（bingbu_pending_proposals.json）─────────
    proposals = load_proposals()

    for p in proposals:
        if (p.get("code") == code or p.get("id") == code) and p.get("status") == "pending":
            expires_str = p.get("expires_at")
            if expires_str:
                try:
                    expires = datetime.fromisoformat(expires_str)
                    if expires <= now:
                        p["status"] = "expired"
                        save_proposals(proposals)
                        return {"ok": False, "error": f"审批码 {code} 已过期"}
                except (ValueError, TypeError):
                    pass  # 缺少或无效的expires_at，跳过过期检查

            # 执行干预
            action = p["action"]
            details = p.get("details", {})
            result = _execute_action(action, details)

            p["status"] = "approved"
            p["executed_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
            p["result"] = result

            save_proposals(proposals)

            # 写入干预历史
            add_intervention(action, p.get("reason", ""), p.get("sentiment", {}), result.get("success", False))

            _send_execution_report(p, result)

            return {"ok": True, "proposal_id": p["id"], "action": action, "result": result}

    return {"ok": False, "error": f"未找到待审批的提案码 {code}"}


def reject_proposal(code: str) -> dict:
    """拒绝干预提案（支持两个通道）"""
    now = datetime.now()

    # 通道1：黑天鹅审批
    pending = load_pending()
    for p in pending:
        if p.get("id") == code and p.get("status") == "pending":
            p["status"] = "rejected"
            p["rejected_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
            p["code"] = p["id"]  # 确保有code字段供_notify_rejected使用
            save_pending(pending)
            _notify_rejected(p)  # 发送拒绝通知到群里
            return {"ok": True, "proposal_id": p["id"], "action": "reject"}

    # 通道2：下单审计提案
    proposals = load_proposals()
    for p in proposals:
        if (p.get("code") == code or p.get("id") == code) and p.get("status") == "pending":
            p["status"] = "rejected"
            p["executed_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
            save_proposals(proposals)
            _notify_rejected(p)
            return {"ok": True, "proposal_id": p["id"], "action": p["action"]}
    return {"ok": False, "error": f"未找到待审批的提案码 {code}"}


def _execute_action(action: str, details: dict) -> dict:
    """执行已批准的干预动作"""
    if action == "force_exit_pair":
        return _do_force_exit_pair(details.get("pair", ""))
    elif action == "emergency_exit_all":
        return _do_emergency_exit_all()
    elif action == "inject_long_pair":
        return _do_inject_long_pair(details.get("pair", ""), details.get("confidence", 80))
    elif action == "inject_short_pair":
        return _do_inject_short_pair(details.get("pair", ""), details.get("confidence", 80))
    elif action == "freeze_pair":
        return _do_freeze(details.get("pair"), details.get("level", "L4"))
    elif action == "freeze":
        return _do_freeze(None, details.get("level", "L4"))
    elif action == "black_swan_freeze":
        # 黑天鹅紧急接管：强制平仓已达S/R临界位的持仓 + 全局冻结
        actionable = details.get("actionable_positions", [])
        results = []
        targets = []

        # 第一步：平掉已达S/R位的持仓
        pairs_exited = set()
        for pos in actionable:
            pair = pos.get("pair", "")
            if pair in pairs_exited:
                continue
            r = _do_force_exit_pair(pair)
            if r.get("success"):
                for t in r.get("targets", []):
                    t["reason"] = pos.get("intervene_reason", "")
                    targets.append(t)
                pairs_exited.add(pair)
            results.append(f"{pair}: {r.get('details', '')}")

        # 第二步：全局冻结（防止新开仓）
        freeze_result = _do_freeze(None, "L4")
        results.append(f"全局冻结: {freeze_result.get('details', '')}")

        return {
            "success": True,
            "details": " | ".join(results),
            "targets": targets,
        }
    elif action == "add_position":
        return _do_add_position(
            details.get("pair", ""),
            details.get("port"),
            details.get("side", "LONG"),
            details.get("stake_pct", 0.30),
            details.get("leverage", 1),
        )
    else:
        return {"success": False, "details": f"未知动作: {action}"}


def _send_execution_report(proposal: dict, result: dict):
    """发送执行结果到飞书"""
    status = "\U0001f7e2 成功" if result.get("success") else "\U0001f7e1 失败"
    action = proposal.get("action", "")

    # ── add_position 专用详细卡片 ──────────────────────────────
    if action == "add_position":
        pair = str(result.get("pair") or "?")
        side = (result.get("side") or "?").upper()
        stake = str(result.get("stake_amount") or "?")
        leverage = str(result.get("leverage") or "?")
        trade_id = result.get("trade_id")
        bot = str(result.get("bot") or "?")
        code_str = str(proposal.get("code") or proposal.get("id") or "")
        exec_time = str(proposal.get("executed_at") or "")
        direction_label = "做多" if side == "LONG" else "做空"
        content = (
            "**审批码：** `" + code_str + "`\n"
            "**执行状态：** " + status + "\n"
            "**执行时间：** " + exec_time + "\n"
            "━━━━━━━━━━━ 执行详情 ━━━━━━━━━━━\n"
            "**交易对：** " + pair + "\n"
            "**方向：** " + direction_label + "\n"
            "**加仓金额：** " + stake + " USDT\n"
            "**杠杆：** " + leverage + "x\n"
            "**机器人：** " + bot + "\n"
            + ("**Trade ID：** " + str(trade_id) + "\n" if trade_id else "")
            + "\n" + str(result.get("details") or "")
        )
        card = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": "\U0001f4c8 加仓执行回执 | " + pair},
                    "template": "green" if result.get("success") else "red",
                },
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                ],
            },
        }
        _feishu_post(card)
        return

    # ── force_exit_pair / emergency_exit_all 专用详细卡片 ───────────
    if action in ("force_exit_pair", "emergency_exit_all"):
        targets = result.get("targets") or []
        exit_details = str(result.get("details") or "")
        pair = str(proposal.get("details", {}).get("pair") or "全市场")
        code_str = str(proposal.get("code") or proposal.get("id") or "")
        exec_time = str(proposal.get("executed_at") or "")
        target_text = "\n".join([
            "  * " + str(t.get("pair") or "?") + " " + str(t.get("side") or "?") + " "
            + str(t.get("bot") or "?") + " 浮亏 " + str(round(t.get("pnl") or 0, 2)) + "U | 数量 " + str(t.get("amount") or "")
            for t in targets
        ]) if targets else "  （无匹配持仓）"
        content = (
            "**审批码：** `" + code_str + "`\n"
            "**执行状态：** " + status + "\n"
            "**执行时间：** " + exec_time + "\n"
            "━━━━━━━━━━━ 平仓详情 ━━━━━━━━━━━\n"
            + target_text + "\n\n"
            "━━━━━━━━━━━ 执行日志 ━━━━━━━━━━━\n" + exit_details
        )
        card = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": "\U0001f534 平仓执行回执 | " + pair},
                    "template": "red",
                },
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                ],
            },
        }
        _feishu_post(card)
        return

    # ── 其他动作（inject/freeze等）通用卡片 ───────────────────
    targets = result.get("targets") or []
    code_str = str(proposal.get("code") or proposal.get("id") or "")
    exec_time = str(proposal.get("executed_at") or "")
    target_text = "\n".join([
        "  * " + str(t.get("pair") or "?") + " @" + str(t.get("bot") or "?") + " "
        + str(t.get("side") or "?") + " 浮亏 " + str(t.get("pnl") or 0)
        for t in targets
    ]) if targets else "  （无匹配持仓）"
    content = (
        "**审批码：** `" + code_str + "`\n"
        "**动作：** " + str(proposal.get("action") or "") + "\n"
        "**原因：** " + str(proposal.get("reason") or "") + "\n\n"
        "**执行状态：** " + status + "\n"
        "**执行时间：** " + exec_time + "\n\n"
        "━━━━━━━━ 受影响持仓 ━━━━━━━━\n" + target_text + "\n\n"
        "━━━━━━━━ 执行详情 ━━━━━━━━\n" + str(result.get("details") or "")
    )
    card = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "\u2705 兵部干预已执行 | " + str(proposal.get("id") or "")},
                "template": "green" if result.get("success") else "red",
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                {"tag": "hr"},
            ],
        },
    }
    _feishu_post(card)


def _notify_rejected(proposal: dict):
    """发送拒绝通知"""
    card = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"❌ 兵部干预已拒绝 ｜ {proposal['id']}"},
                "template": "grey",
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**审批码： `{proposal.get('code', proposal['id'])}`**"}},
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": (
                        f"**动作：{proposal['action']}**\n"
                        f"**原因：{proposal['reason']}**\n\n"
                        f"⚠️ 此干预已被拒绝，未执行任何操作。"
                    )},
                },
            ],
        },
    }
    _feishu_post(card)


# ─────────────────────────────────────────
#  实际执行函数
# ─────────────────────────────────────────

# ── D-3 / C-2 辅助函数 ─────────────────────────────────────────────

def _get_balance_snapshot() -> dict:
    """获取余额快照（供inject提案使用）"""
    for port, cfg in list(FREQTRADE_CONFIGS.items())[:3]:  # 最多试3个bot
        try:
            r = requests.get(
                f"{cfg['host']}/api/v1/balance",
                headers={"Authorization": cfg["auth"]},
                timeout=5,
            )
            if r.status_code == 200:
                d = r.json()
                free_usdt = next(
                    (float(c.get("free", 0)) for c in d.get("currencies", [])
                     if c.get("currency", "").upper() in ("USDT", "USDC") and float(c.get("free", 0)) > 0),
                    0.0,
                )
                return {
                    "free_usdt": round(free_usdt, 2),
                    "source_bot": cfg["label"],
                }
        except Exception:
            continue
    return {"free_usdt": 0.0, "source_bot": "unknown"}


def _poll_inject_confirm(pair: str, direction: str, timeout: int = 30) -> dict:
    """C-2: 轮询inject确认回执（api_autopilot处理后写入）"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(2)
        try:
            if INJECT_RESULT_FILE.exists():
                data = json.loads(INJECT_RESULT_FILE.read_text(encoding="utf-8"))
                if data.get("pair", "").replace(":USDT", "") == pair.replace(":USDT", ""):
                    return data
        except Exception:
            pass
    return {"status": "timeout"}


# ─────────────────────────────────────────────────────────────────

def _do_inject_long_pair(pair: str, confidence: int = 80) -> dict:
    """执行：注入做多信号（C-2确认回执 + D-3余额快照）"""
    try:
        # D-3: 获取余额快照
        balance = _get_balance_snapshot()
        stake_pct = min(0.10, 0.03 + confidence / 1000)
        est_stake = round(balance["free_usdt"] * stake_pct, 2)

        inject_data = {
            "sentiment_direction": "LONG",
            "sentiment_confidence": confidence,
            "sentiment_reason": f"兵部精准干预：{pair} 注入做多信号",
            "target_pair": pair,
            "timestamp": datetime.now().isoformat(),
            "source": "bingbu_precision_approved",
            # D-3: 余额快照（飞书卡片展示用）
            "balance_snapshot": {
                "free_usdt": balance["free_usdt"],
                "stake_pct": round(stake_pct * 100, 1),
                "est_stake_amount": est_stake,
            },
        }
        with open(INJECT_FILE, "w") as f:
            json.dump(inject_data, f, indent=2)

        # C-2: 等待api_autopilot确认
        confirm = _poll_inject_confirm(pair, "LONG")
        if confirm.get("status") == "success":
            return {"success": True, "details": f"✅ 做多信号已确认: {pair}", "trade_id": confirm.get("trade_id")}
        elif confirm.get("status") == "timeout":
            return {"success": True, "details": f"⚠️ 做多信号已写入(确认超时): {pair}"}
        else:
            return {"success": False, "details": f"❌ 做多信号失败: {confirm.get('error', 'unknown')}"}
    except Exception as e:
        return {"success": False, "details": str(e)}


def _do_inject_short_pair(pair: str, confidence: int = 80) -> dict:
    """执行：注入做空信号（C-2确认回执 + D-3余额快照）"""
    try:
        # D-3: 获取余额快照
        balance = _get_balance_snapshot()
        stake_pct = min(0.10, 0.03 + confidence / 1000)
        est_stake = round(balance["free_usdt"] * stake_pct, 2)

        inject_data = {
            "sentiment_direction": "SHORT",
            "sentiment_confidence": confidence,
            "sentiment_reason": f"兵部精准干预：{pair} 注入做空信号",
            "target_pair": pair,
            "timestamp": datetime.now().isoformat(),
            "source": "bingbu_precision_approved",
            # D-3: 余额快照
            "balance_snapshot": {
                "free_usdt": balance["free_usdt"],
                "stake_pct": round(stake_pct * 100, 1),
                "est_stake_amount": est_stake,
            },
        }
        with open(INJECT_FILE, "w") as f:
            json.dump(inject_data, f, indent=2)

        # C-2: 等待api_autopilot确认
        confirm = _poll_inject_confirm(pair, "SHORT")
        if confirm.get("status") == "success":
            return {"success": True, "details": f"✅ 做空信号已确认: {pair}", "trade_id": confirm.get("trade_id")}
        elif confirm.get("status") == "timeout":
            return {"success": True, "details": f"⚠️ 做空信号已写入(确认超时): {pair}"}
        else:
            return {"success": False, "details": f"❌ 做空信号失败: {confirm.get('error', 'unknown')}"}
    except Exception as e:
        return {"success": False, "details": str(e)}


def _do_force_exit_pair(pair: str) -> dict:
    """执行：指定交易对强制平仓"""
    results = []
    targets = []
    pair_norm = pair.replace(":USDT", "").strip()
    # 修复Bug: 收集所有平仓记录（避免循环内覆盖日志）
    all_exit_records = []

    for port, cfg in FREQTRADE_CONFIGS.items():
        if not _ensure_running(port, cfg):
            results.append(f"{port}: 机器人启动失败")
            continue
        try:
            resp = requests.get(
                f"{cfg['host']}/api/v1/status",
                headers={"Authorization": cfg["auth"]},
                timeout=5,
            )
            if resp.status_code != 200:
                continue
            positions = resp.json()
        except Exception as e:
            results.append(f"{port}: {e}")
            continue

        for pos in positions:
            if not pos.get("is_open"):
                continue
            pos_pair = pos.get("pair", "").replace(":USDT", "").strip()
            if pos_pair != pair_norm:
                continue
            trade_id = pos.get("trade_id")
            side = "SHORT" if pos.get("is_short") else "LONG"
            pnl = round(float(pos.get("profit_abs") or 0), 2)
            try:
                exchange = cfg.get("exchange", "gate")
                if exchange == "okx":
                    # OKX: 优先用 body 方式，405则降级为 DELETE
                    r = requests.post(
                        f"{cfg['host']}/api/v1/forceexit",
                        headers={"Authorization": cfg["auth"], "Content-Type": "application/json"},
                        json={"tradeid": trade_id},
                        timeout=10,
                    )
                    if r.status_code == 405:
                        r = requests.delete(
                            f"{cfg['host']}/api/v1/trades/{trade_id}",
                            headers={"Authorization": cfg["auth"], "Content-Type": "application/json"},
                            timeout=10,
                        )
                else:
                    # Gate: body 方式
                    r = requests.post(
                        f"{cfg['host']}/api/v1/forceexit",
                        headers={"Authorization": cfg["auth"]},
                        json={"tradeid": trade_id},
                        timeout=10,
                    )
                ok = r.status_code in (200, 201, 202)
                results.append(f"{pos_pair}@{port}(id={trade_id},{side}): {'ok' if ok else r.text[:50]}")
                targets.append({
                    "bot": cfg["label"], "port": port, "pair": pos_pair,
                    "side": side, "pnl": pnl, "trade_id": trade_id,
                })
                # C-1修复: 写入冷却记录（包含direction），收集到列表统一写入避免覆盖
                if ok:
                    all_exit_records.append({
                        "trade_id": int(trade_id),
                        "pair": pos_pair,
                        "port": port,
                        "direction": side,   # ✅ 修复: 添加direction字段（冷却生效关键）
                        "exited_amount": float(pos.get("amount", 0)),
                        "timestamp": datetime.now().isoformat(),
                        "source": "bingbu_manual",
                    })
            except Exception as e:
                results.append(f"{pos_pair}@{port}: {e}")

    # ✅ 修复Bug2: 统一写入所有平仓记录（JSON数组）避免覆盖
    if all_exit_records:
        try:
            MANUAL_EXIT_LOG.write_text(json.dumps({
                "exits": all_exit_records,
                "processed": False,
            }, ensure_ascii=False))
        except Exception:
            pass

    ok = any("ok" in r for r in results)
    return {"success": ok, "details": "; ".join(results), "targets": targets}


def _do_emergency_exit_all() -> dict:
    """执行：全市场双向强平"""
    results = []
    targets = []
    # 修复Bug: 收集所有平仓记录（避免循环内覆盖日志）
    all_exit_records = []

    for port, cfg in FREQTRADE_CONFIGS.items():
        if not _ensure_running(port, cfg):
            results.append(f"{port}: 机器人启动失败")
            continue
        try:
            resp = requests.get(
                f"{cfg['host']}/api/v1/status",
                headers={"Authorization": cfg["auth"]},
                timeout=5,
            )
            if resp.status_code != 200:
                continue
            positions = resp.json()
        except Exception as e:
            results.append(f"{port}: {e}")
            continue

        for pos in positions:
            if not pos.get("is_open"):
                continue
            trade_id = pos.get("trade_id")
            pair = pos.get("pair", "").replace(":USDT", "")
            side = "SHORT" if pos.get("is_short") else "LONG"
            pnl = round(float(pos.get("profit_abs") or 0), 2)
            try:
                exchange = cfg.get("exchange", "gate")
                if exchange == "okx":
                    # OKX: 优先用 body 方式，405则降级为 DELETE
                    r = requests.post(
                        f"{cfg['host']}/api/v1/forceexit",
                        headers={"Authorization": cfg["auth"], "Content-Type": "application/json"},
                        json={"tradeid": trade_id},
                        timeout=10,
                    )
                    if r.status_code == 405:
                        r = requests.delete(
                            f"{cfg['host']}/api/v1/trades/{trade_id}",
                            headers={"Authorization": cfg["auth"], "Content-Type": "application/json"},
                            timeout=10,
                        )
                else:
                    # Gate: body 方式
                    r = requests.post(
                        f"{cfg['host']}/api/v1/forceexit",
                        headers={"Authorization": cfg["auth"]},
                        json={"tradeid": trade_id},
                        timeout=10,
                    )
                ok = r.status_code in (200, 201, 202)
                results.append(f"[全平]{pair}@{port}(id={trade_id},{side}): {'ok' if ok else r.text[:50]}")
                targets.append({
                    "bot": cfg["label"], "port": port, "pair": pair,
                    "side": side, "pnl": pnl, "trade_id": trade_id,
                })
                # C-1修复: 写入冷却记录（包含direction），收集到列表统一写入避免覆盖
                if ok:
                    all_exit_records.append({
                        "trade_id": int(trade_id),
                        "pair": pair,
                        "port": port,
                        "direction": side,   # ✅ 修复: 添加direction字段（冷却生效关键）
                        "exited_amount": float(pos.get("amount", 0)),
                        "timestamp": datetime.now().isoformat(),
                        "source": "bingbu_emergency",
                    })
            except Exception as e:
                results.append(f"[全平]{pair}@{port}: {e}")

    # ✅ 修复Bug2: 统一写入所有平仓记录（JSON数组）避免覆盖
    if all_exit_records:
        try:
            MANUAL_EXIT_LOG.write_text(json.dumps({
                "exits": all_exit_records,
                "processed": False,
            }, ensure_ascii=False))
        except Exception:
            pass

    ok = any("ok" in r for r in results)
    return {"success": ok, "details": "; ".join(results), "targets": targets}


def _do_add_position(pair: str, port: int, side: str,
                    stake_pct: float, leverage: int) -> dict:
    """
    执行：DCA加仓
    - 获取指定bot的余额
    - 计算加仓金额 = 余额 × stake_pct
    - 调用forceenter追加仓位
    """
    if not port or port not in FREQTRADE_CONFIGS:
        return {"success": False, "details": f"未知端口: {port}"}

    cfg = FREQTRADE_CONFIGS[port]

    try:
        # 1. 获取余额
        resp = requests.get(
            f"{cfg['host']}/api/v1/balance",
            headers={"Authorization": cfg["auth"]},
            timeout=8,
        )
        if resp.status_code != 200:
            return {"success": False, "details": f"余额获取失败: {resp.status_code}"}

        bal_data = resp.json()
        # 尝试提取可用USDT余额
        free = 0.0
        try:
            # currencies 是 list: [{currency: "USDT", free: 61.93, ...}, ...]
            currencies = bal_data.get("currencies", [])
            if isinstance(currencies, list):
                for c in currencies:
                    if isinstance(c, dict) and c.get("currency", "").upper() in ("USDT", "USD", "USDT:USDT"):
                        free = float(c.get("free", 0))
                        break
                if not free and currencies:
                    # 回退：取第一个有余额的
                    for c in currencies:
                        if isinstance(c, dict):
                            f = float(c.get("free", 0))
                            if f > 0:
                                free = f
                                break
            elif isinstance(currencies, dict):
                # 某些版本可能是 dict
                usdt_data = currencies.get("USDT", {})
                if isinstance(usdt_data, dict):
                    free = float(usdt_data.get("free", 0))
        except Exception:
            free = 0.0

        if free <= 0:
            return {"success": False, "details": f"余额不足: ${free}"}

        # 2. 计算加仓金额
        stake_amount = round(free * stake_pct, 2)
        stake_amount = max(10, stake_amount)  # 最少$10

        # 3. 确定交易对格式
        # FreqTrade 内部使用 SOL/USDT:USDT 格式（pair:stake_currency），两个交易所通用
        pair_fmt = pair
        # 追加 stake_currency 后缀
        if ":" not in pair_fmt:
            pair_fmt = f"{pair_fmt}:USDT"

        # 4. 调用forceenter（追加仓位，不影响现有持仓）
        order_side = "short" if side == "SHORT" else "long"
        payload = {
            "pair": pair_fmt,
            "side": order_side,
            "stake_amount": stake_amount,
            "leverage": leverage if leverage > 1 else None,
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        r = requests.post(
            f"{cfg['host']}/api/v1/forceenter",
            headers={"Authorization": cfg["auth"], "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )

        ok = r.status_code in (200, 201, 202)
        trade_id = None
        if ok:
            try:
                result_data = r.json()
                trade_id = result_data.get("trade_id")
            except Exception:
                pass
            details = (f"加仓成功: {pair} {side} ${stake_amount} (余额${free:.0f}×{stake_pct*100:.0f}%)"
                        f" @{cfg['label']}")
        else:
            details = f"加仓失败: HTTP {r.status_code} {r.text[:80]}"

        return {
            "success": ok,
            "details": details,
            "trade_id": trade_id,
            "pair": pair,
            "side": side,
            "stake_amount": stake_amount,
            "leverage": leverage,
            "bot": cfg["label"],
        }

    except Exception as e:
        return {"success": False, "details": f"加仓异常: {e}"}


def _do_unfreeze_all() -> dict:
    """执行：解除全市场冻结"""
    try:
        if FREEZE_FILE.exists():
            existing = json.loads(FREEZE_FILE.read_text())
        else:
            existing = {}
        existing["frozen"] = False
        existing["frozen_pairs"] = []
        existing["timestamp"] = datetime.now().isoformat()
        FREEZE_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2))

        # 同时清除 bingbu_intervention_state.json 中的 force_executed 标志
        # 防止 bingbu_patrol 继续静默跳过
        STATE_FILE = Path("/Users/luxiangnan/edict/data/bingbu_intervention_state.json")
        if STATE_FILE.exists():
            try:
                state = json.loads(STATE_FILE.read_text())
            except Exception:
                state = {}
        else:
            state = {}
        state["force_executed"] = False
        state["force_executed_at"] = ""
        state["force_executed_alert_id"] = ""
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))

        return {"ok": True, "action": "unfreeze", "details": "全市场解除冻结"}
    except Exception as e:
        return {"ok": False, "action": "unfreeze", "details": str(e)}


def _do_freeze(pair: str = None, level: str = "manual") -> dict:
    """
    执行：冻结（支持分级时间冻结）
    level: L1(5min) / L2(15min) / L3(30min) / L4(手动)
    """
    # 分级时间配置
    LEVEL_DURATION = {
        "L1": timedelta(minutes=5),    # 轻微异常
        "L2": timedelta(minutes=15),   # 中度风险
        "L3": timedelta(minutes=30),   # 重大风险
        "L4": None,                    # 手动解除
    }
    LEVEL_LABEL = {
        "L1": "🟡 黄色警告(5分钟)",
        "L2": "🟠 橙色关注(15分钟)",
        "L3": "🔴 红色紧急(30分钟)",
        "L4": "⚫ 黑色极值(手动)",
    }

    duration = LEVEL_DURATION.get(level, None)
    expires_at = (datetime.now() + duration) if duration else None
    scope_label = f"{pair}" if pair else "全市场"

    try:
        if pair:
            existing = {}
            if FREEZE_FILE.exists():
                try:
                    existing = json.loads(FREEZE_FILE.read_text())
                except Exception:
                    existing = {}
            frozen_pairs: list = existing.get("frozen_pairs", [])
            if pair not in frozen_pairs:
                frozen_pairs.append(pair)
            freeze_data = {
                "frozen": True,
                "frozen_pairs": frozen_pairs,
                "level": level,
                "level_label": LEVEL_LABEL.get(level, level),
                "timestamp": datetime.now().isoformat(),
                "expires_at": expires_at.isoformat() if expires_at else None,
                "reason": f"兵部审核冻结: {scope_label} [{level}]",
                "scope": "pair_specific",
            }
        else:
            freeze_data = {
                "frozen": True,
                "frozen_pairs": [],
                "level": level,
                "level_label": LEVEL_LABEL.get(level, level),
                "timestamp": datetime.now().isoformat(),
                "expires_at": expires_at.isoformat() if expires_at else None,
                "reason": f"兵部审核冻结: 全市场 [{level}]",
                "scope": "global",
            }
        with open(FREEZE_FILE, "w") as f:
            json.dump(freeze_data, f, indent=2)
        exp_str = f"自动解除于 {expires_at.strftime('%H:%M')}" if expires_at else "需手动解除"
        return {"success": True, "details": f"冻结已执行: {scope_label} [{level}]，{exp_str}"}
    except Exception as e:
        return {"success": False, "details": str(e)}


# ─────────────────────────────────────────
#  旧版自动触发函数（已禁用，仅供手动调用）
# ─────────────────────────────────────────

def check_and_execute() -> dict:
    """
    ⚠️ 已禁用自动执行！仅保留接口兼容。
    所有干预必须经提案→审核→执行流程。
    """
    return {
        "action": "disabled",
        "reason": "自动执行已禁用，所有干预须经飞书审核",
        "result": "blocked",
        "targets": [],
    }


# ─────────────────────────────────────────
#  CLI 入口
# ─────────────────────────────────────────

def run_once():
    print(f"兵部舆情监测（审核制） - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("⚠️ 自动执行已禁用，所有干预须经飞书审核后执行")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="兵部舆情处理器（审核制）")
    parser.add_argument("--once", action="store_true", help="单次运行（仅播报状态，不干预）")
    args = parser.parse_args()
    run_once()
