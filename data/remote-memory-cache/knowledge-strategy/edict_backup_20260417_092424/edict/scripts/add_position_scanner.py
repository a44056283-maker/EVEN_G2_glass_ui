#!/usr/bin/env python3
"""
加仓Scanner - 兵部提案系统
================================================================
扫描所有持仓，发现加仓机会后生成提案，等待爸审批后执行。
触发条件（优先级从高到低）：
  1. 支撑位触发（Primary）：价格距支撑位 < 3% → 触发加仓
  2. 浮亏比例触发（Secondary）：浮亏 >= 5% → 触发首次/二次加仓

执行流程：
  Scanner发现机会 → 生成提案 → 飞书卡片通知爸 → 爸审批 → 执行DCA
================================================================
"""

import json
import sys
import time
import urllib.request
import concurrent.futures
import datetime as dt
from pathlib import Path
from typing import Any

import requests as _req

# ── 配置 ──────────────────────────────────────────────────
EDICT_DATA      = Path("/Users/luxiangnan/edict/data")
PROPOSALS_FILE  = EDICT_DATA / "add_position_proposals.json"
BINGBU_API      = "http://127.0.0.1:7891/api/bingbu"
WEBHOOK_BINGBU  = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"

# 加仓参数（爸的方向）
_MAX_ADD_COUNT       = 2          # 最多加仓2次（首仓+2次=3单）
_SUPPORT_TRIGGER_PCT = 3.0       # 距支撑位 < 3% 触发
_DRAWDOWN_LEVELS    = [0.05, 0.10, 0.15]  # 浮亏5%/10%/15%三级触发
_COOLDOWN_HOURS      = 4         # 加仓冷却时间（小时）
_PROPOSAL_EXPIRE_MIN = 30        # 提案30分钟过期
_STAKE_PCT           = 0.30      # 每次加仓金额占余额比例

# DCA金字塔配置（与爸确认的方案）
_ENTRY_DISTRIBUTION = [0.40, 0.35, 0.25]  # 首仓40% / 一次35% / 二次25%

# ── 动态止盈档位（运行时读取机器人当前配置）───────────────────────
_EXIT_RUNTIME_FILES = [
    "/Users/luxiangnan/freqtrade/freqtrade/rpc/api_server/runtime_params_v61_gate_17656685222.json",
    "/Users/luxiangnan/freqtrade/freqtrade/rpc/api_server/runtime_params_v61_gate_85363904550.json",
    "/Users/luxiangnan/freqtrade/freqtrade/rpc/api_server/runtime_params_v61_gate_15637798222.json",
    "/Users/luxiangnan/freqtrade/freqtrade/rpc/api_server/runtime_params_v61_okx_15637798222.json",
]

def _load_exit_runtime() -> dict:
    """从任一机器人运行时参数文件读取当前生效的止盈配置"""
    for fpath in _EXIT_RUNTIME_FILES:
        try:
            if Path(fpath).exists():
                data = json.loads(Path(fpath).read_text())
                if data.get("base_exit_p1_profit") is not None:
                    return data
        except Exception:
            pass
    return {}

_exit_runtime = _load_exit_runtime()

_BASE_EXIT_P1_PROFIT = _exit_runtime.get("base_exit_p1_profit", 35.0)
_BASE_EXIT_P2_PROFIT = _exit_runtime.get("base_exit_p2_profit", 55.0)
_BASE_EXIT_P3_PROFIT = _exit_runtime.get("base_exit_p3_profit", 95.0)
_BASE_EXIT_P1_PCT    = _exit_runtime.get("base_exit_p1_pct", 20)
_BASE_EXIT_P2_PCT    = _exit_runtime.get("base_exit_p2_pct", 35)
_BASE_EXIT_P3_PCT    = _exit_runtime.get("base_exit_p3_pct", 45)


def _compute_exit_tiers(leverage: float, entry_price: float) -> list:
    """计算加仓后的3档止盈触发价
    真实涨幅 = BASE / 10（恒定，与杠杆无关）
    触发涨幅 = BASE × (leverage / 10)
    止盈价 = 入场价 × (1 + 真实涨幅/100)（所有杠杆同一价格）
    """
    m = leverage / 10.0
    # 真实涨幅 = BASE / 10（所有杠杆相同，决定止盈价）
    true_p1 = _BASE_EXIT_P1_PROFIT / 10.0
    true_p2 = _BASE_EXIT_P2_PROFIT / 10.0
    true_p3 = _BASE_EXIT_P3_PROFIT / 10.0
    # 触发涨幅 = BASE × (leverage / 10)（杠杆越高越快触发）
    trigger_p1 = _BASE_EXIT_P1_PROFIT * m
    trigger_p2 = _BASE_EXIT_P2_PROFIT * m
    trigger_p3 = _BASE_EXIT_P3_PROFIT * m
    # 卖出%：杠杆越高越早锁利，卖出比例越低
    pct2 = int(round(_BASE_EXIT_P2_PCT * (2.0 - m)))
    pct3 = int(round(_BASE_EXIT_P3_PCT * (2.0 - m)))
    pct1 = _BASE_EXIT_P1_PCT

    tiers = []
    for label, trigger, pct, true_pct in [
        ("P1", trigger_p1, pct1, true_p1),
        ("P2", trigger_p2, pct2, true_p2),
        ("P3", trigger_p3, pct3, true_p3),
    ]:
        if entry_price <= 0:
            continue
        # 止盈价由真实涨幅决定，所有杠杆同一价格
        # 做多(LONG)：价格涨到 exit_price_long = entry * (1 + true_pct/100) 止盈
        # 做空(SHORT)：价格跌到 exit_price_short = entry * (1 - true_pct/100) 止盈
        exit_price_long  = entry_price * (1 + true_pct / 100.0)
        exit_price_short = entry_price * (1 - true_pct / 100.0)
        tiers.append({
            "tier": label,
            "profit_pct": round(trigger, 1),   # 卡片显示触发涨幅
            "true_profit_pct": round(true_pct, 2),  # 真实涨幅
            "exit_pct": pct,
            "exit_price_long": round(exit_price_long, 4),
            "exit_price_short": round(exit_price_short, 4),
        })
    return tiers


# ── 工具函数 ──────────────────────────────────────────────

def _fetch_json(url: str, timeout: int = 8) -> Any:
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None


def _post_json(url: str, data: dict, timeout: int = 10) -> bool:
    try:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


# ── S/R 数据获取 ─────────────────────────────────────────

def fetch_sr_levels(pair: str) -> dict:
    """
    获取S/R级别（Gate.io K线，.swing高低点法）
    返回: {"support": float, "resistance": float, "current": float,
           "dist_support_pct": float, "dist_resistance_pct": float}
    """
    pair_clean = pair.split(":")[0]
    gate_pair  = pair_clean.replace("/", "_")
    result = {
        "support": 0.0, "resistance": 0.0, "current": 0.0,
        "dist_support_pct": 999.0, "dist_resistance_pct": 999.0,
    }
    try:
        tk = _req.get(
            f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={gate_pair}",
            timeout=8
        )
        if tk.status_code == 200 and tk.json():
            result["current"] = float(tk.json()[0].get("last", 0))

        kx = _req.get(
            f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={gate_pair}"
            f"&interval=15m&limit=500",
            timeout=8
        )
        if kx.status_code == 200:
            klines = kx.json()
            if klines and isinstance(klines, list) and len(klines) > 0:
                # 只用当日K线计算S/R
                today_start = dt.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                today_start_ts = int(today_start.timestamp())
                today_highs = [float(k[3]) for k in klines if int(k[0]) >= today_start_ts]
                today_lows  = [float(k[4]) for k in klines if int(k[0]) >= today_start_ts]
                if len(today_highs) >= 3:
                    result["resistance"] = sum(sorted(today_highs)[-3:]) / 3
                    result["support"]    = sum(sorted(today_lows)[:3]) / 3
                elif len(today_highs) > 0:
                    result["resistance"] = max(today_highs)
                    result["support"]    = min(today_lows)
    except Exception:
        pass

    cur = result["current"]
    sup = result["support"]
    res = result["resistance"]
    if cur > 0 and sup > 0:
        result["dist_support_pct"]    = abs(cur - sup) / cur * 100
    if cur > 0 and res > 0:
        result["dist_resistance_pct"] = abs(res - cur) / cur * 100

    return result


# ── 提案存储 ──────────────────────────────────────────────

def load_proposals() -> list:
    if not PROPOSALS_FILE.exists():
        return []
    try:
        proposals = json.loads(PROPOSALS_FILE.read_text())
        # 自动过期：清除已超时提案
        now = dt.datetime.now()
        valid = []
        for p in proposals:
            expires_str = p.get("expires_at", "")
            if expires_str:
                try:
                    expires = dt.datetime.strptime(expires_str, "%Y-%m-%d %H:%M:%S")
                    if expires <= now:
                        p["status"] = "expired"
                        continue
                except ValueError:
                    pass
            valid.append(p)
        if len(valid) != len(proposals):
            save_proposals(valid)
        return valid
    except Exception:
        return []


def save_proposals(proposals: list):
    PROPOSALS_FILE.write_text(json.dumps(proposals, ensure_ascii=False, indent=2))


def _gen_code() -> str:
    return f"AP-{dt.datetime.now().strftime('%m%d%H%M%S')}{dt.datetime.now().microsecond // 1000:03d}"


def create_proposal(pos: dict, sr: dict, trigger_type: str,
                    trigger_value: float, add_index: int) -> dict:
    """生成一条加仓提案"""
    pair        = pos["pair"]
    side        = pos["side"]
    cur         = sr.get("current", 0)
    sup         = sr.get("support", 0)
    res         = sr.get("resistance", 0)
    d2s         = sr.get("dist_support_pct", 0)
    d2r         = sr.get("dist_resistance_pct", 0)
    drawdown    = abs(pos.get("profit_pct", 0)) / 100.0
    entry_dist  = _ENTRY_DISTRIBUTION[min(add_index, len(_ENTRY_DISTRIBUTION) - 1)]
    stake_pct   = _STAKE_PCT

    if trigger_type == "support":
        reason = (f"加仓提案：{pair} 距支撑位仅 {d2s:.1f}%（< {_SUPPORT_TRIGGER_PCT}%），"
                  f"建议加仓{entry_dist*100:.0f}%仓位（{side}，第{add_index+1}次）")
    else:
        reason = (f"加仓提案：{pair} 浮亏 {drawdown*100:.1f}%，"
                  f"建议加仓{entry_dist*100:.0f}%仓位（{side}，第{add_index+1}次）")

    # 计算加仓后的新入场价（平均）
    entry_price = pos.get("entry_price", 0)
    leverage    = pos.get("leverage", 1)
    exit_tiers  = _compute_exit_tiers(leverage, entry_price)

    return {
        "id":           _gen_code(),
        "status":       "pending",
        "pair":         pair,
        "side":         side,
        "port":         pos.get("port"),
        "bot":          pos.get("bot"),
        "trigger_type": trigger_type,          # "support" / "drawdown"
        "trigger_value": round(trigger_value, 3),
        "support":      round(sup, 6),
        "resistance":   round(res, 6),
        "dist_support_pct":    round(d2s, 2),
        "dist_resistance_pct": round(d2r, 2),
        "current_price": round(cur, 6),
        "entry_price":  round(entry_price, 6),
        "leverage":     leverage,
        "profit_pct":   pos.get("profit_pct", 0),
        "drawdown_pct": round(drawdown * 100, 2),
        "unrealized_pnl": pos.get("unrealized_pnl", 0),
        "amount":       pos.get("amount", 0),
        "liquidation_price": pos.get("liquidation_price", 0),
        "add_index":    add_index,            # 0=首次加仓, 1=二次加仓
        "stake_pct":    stake_pct,           # 加仓金额占余额比例
        "entry_distribution": entry_dist,    # 本次加仓资金占比
        "max_add_index": _MAX_ADD_COUNT,      # 最大加仓次数
        "exit_tiers":   exit_tiers,           # 3档止盈触发价（联动展示）
        "reason":       reason,
        "created_at":   dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "expires_at":   (dt.datetime.now() + dt.timedelta(minutes=_PROPOSAL_EXPIRE_MIN)
                         ).strftime("%Y-%m-%d %H:%M:%S"),
        "cooldown_until": (dt.datetime.now() + dt.timedelta(hours=_COOLDOWN_HOURS)
                           ).strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_add_count(pair: str) -> int:
    """从已完成/执行中的提案统计某交易对的加仓次数"""
    proposals = load_proposals()
    count = 0
    for p in proposals:
        if (p.get("pair") == pair
                and p.get("status") in ("pending", "approved", "executed")):
            idx = p.get("add_index", 0)
            if idx + 1 > count:
                count = idx + 1
    return count


def get_last_add_time(pair: str) -> dt.datetime | None:
    """获取某交易对上次加仓时间"""
    proposals = load_proposals()
    latest = None
    for p in proposals:
        if (p.get("pair") == pair and p.get("status") == "executed"
                and p.get("executed_at")):
            try:
                t = dt.datetime.strptime(p["executed_at"], "%Y-%m-%d %H:%M:%S")
                if latest is None or t > latest:
                    latest = t
            except Exception:
                pass
    return latest


def is_in_cooldown(pair: str) -> bool:
    """检查是否在冷却期内"""
    last = get_last_add_time(pair)
    if last is None:
        return False
    elapsed = (dt.datetime.now() - last).total_seconds() / 3600
    return elapsed < _COOLDOWN_HOURS


# ── 核心扫描逻辑 ─────────────────────────────────────────

def scan_position(pos: dict) -> dict | None:
    """
    扫描单条持仓，返回提案（如果有）或None
    """
    pair    = pos.get("pair", "?")
    side    = pos.get("side", "?")
    cur_pct = pos.get("profit_pct", 0)   # 已有字段：盈亏百分比（如 -6.3）
    drawdown = abs(cur_pct) / 100.0

    # 已达最大加仓次数
    add_count = get_add_count(pair)
    if add_count >= _MAX_ADD_COUNT:
        return None

    # 检查冷却期
    if is_in_cooldown(pair):
        return None

    # 获取S/R数据
    sr = fetch_sr_levels(pair)
    d2s = sr.get("dist_support_pct", 999.0)
    d2r = sr.get("dist_resistance_pct", 999.0)
    sup = sr.get("support", 0)
    cur = sr.get("current", 0)

    # ── 优先级1：支撑位触发 ────────────────────────────
    # 做多（LONG）：价格跌向支撑位时加仓
    # 做空（SHORT）：价格涨向压力位时加仓
    if side == "LONG" and d2s < _SUPPORT_TRIGGER_PCT and cur > 0 and sup > 0:
        return create_proposal(pos, sr, "support", d2s, add_count)
    if side == "SHORT" and d2r < _SUPPORT_TRIGGER_PCT and cur > 0 and sr.get("resistance", 0) > 0:
        return create_proposal(pos, sr, "support", d2r, add_count)

    # ── 优先级2：浮亏比例触发 ────────────────────────
    # 只有无支撑位信号时才启用
    if drawdown >= _DRAWDOWN_LEVELS[min(add_count, len(_DRAWDOWN_LEVELS) - 1)]:
        # 避免和支撑位触发重复提案
        return create_proposal(pos, sr, "drawdown", drawdown * 100, add_count)

    return None


def scan() -> list:
    """扫描所有持仓，返回提案列表"""
    # 获取所有持仓
    data = _fetch_json(f"{BINGBU_API}/positions")
    if not data:
        print("[add_scanner] 无法获取持仓")
        return []
    positions = data.get("positions", [])
    if not positions:
        print("[add_scanner] 无持仓")
        return []

    proposals = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(scan_position, positions))

    for p in results:
        if p:
            proposals.append(p)

    return proposals


# ── 提案去重 ──────────────────────────────────────────────

def has_pending(pair: str) -> bool:
    """某交易对是否有待审批提案"""
    proposals = load_proposals()
    return any(p.get("pair") == pair and p.get("status") == "pending"
               for p in proposals)


# ── 飞书卡片 ─────────────────────────────────────────────

def _send_card(card: dict) -> bool:
    try:
        payload = json.dumps(card, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(WEBHOOK_BINGBU, data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception as e:
        print(f"[add_scanner] 飞书发送失败: {e}")
        return False


def send_proposal_cards(proposals: list):
    """为每个提案发送一张审批卡片"""
    now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    base_url = "https://openclaw.tianlu2026.org"

    for p in proposals:
        pair     = p["pair"]
        side     = p["side"]
        trigger  = p["trigger_type"]
        trigger_v = p["trigger_value"]
        add_idx  = p["add_index"]
        dist_s   = p["dist_support_pct"]
        dist_r   = p["dist_resistance_pct"]
        cur      = p["current_price"]
        sup      = p["support"]
        res      = p["resistance"]
        profit   = p["profit_pct"]
        stake_pct = p["stake_pct"]
        code     = p["id"]

        color = "green" if side == "LONG" else "orange"
        emoji = "📈" if side == "LONG" else "📉"
        type_label = f"{emoji} 加仓提案 · {now_str}"

        approve_url = f"{base_url}/bingbu/add_position/approve?code={code}"
        reject_url  = f"{base_url}/bingbu/add_position/reject?code={code}"

        if trigger == "support":
            if side == "LONG":
                trigger_txt = f"**触发条件：** 支撑位触发（距支撑 {dist_s:.1f}%）"
            else:
                trigger_txt = f"**触发条件：** 压力位触发（距压力 {dist_r:.1f}%）"
        else:
            trigger_txt = f"**触发条件：** 浮亏触发（浮亏 {trigger_v:.1f}%）"

        # ── 止盈档位（联动展示）────────────────────────
        # profit_pct=触发涨幅，true_pct=真实涨幅
        # 做多(LONG)：价格涨到 exit_price_long 止盈
        # 做空(SHORT)：价格跌到 exit_price_short 止盈
        exit_tiers = p.get("exit_tiers", [])
        leverage   = p.get("leverage", 1)
        entry_p    = p.get("entry_price", 0)
        tier_lines = []
        for t in exit_tiers:
            true_pct = t.get("true_profit_pct", 0)
            if side == "LONG":
                exit_price_str = f"${t['exit_price_long']:.4f}"
            else:
                exit_price_str = f"${t['exit_price_short']:.4f}"
            tier_lines.append(
                f"  • {t['tier']}：触发≥{t['profit_pct']:.1f}% → "
                f"止盈价 {exit_price_str}（真实涨幅{true_pct:.1f}%，卖出{t['exit_pct']}%）"
            )
        tier_block = (
            f"**📌 止盈档位（{leverage}X杠杆，入场价 ${entry_p:.4f}）：**\n" + "\n".join(tier_lines)
            if tier_lines
            else ""
        )

        body_lines = [
            f"**📍 持仓机器人：** {p.get('bot', '?')}（端口 {p.get('port', '?')}）",
            f"**📊 浮亏金额：** ${p.get('unrealized_pnl', 0):.2f}",
            f"**💵 持仓量：** {p.get('amount', 0):.4f}",
            f"**📐 持仓方向：** {side}",
            f"**💲 入场价：** ${entry_p:.4f}",
            f"**💲 当前价：** ${cur:.4f}",
            f"**⚡ 杠杆：** {leverage}x",
            f"**🔻 强平价：** ${p.get('liquidation_price', 0):.4f}",
            f"**📊 支撑位：** ${sup:.4f}（距 {dist_s:.1f}%）",
            f"**📊 压力位：** ${res:.4f}（距 {dist_r:.1f}%）",
            f"**➕ 加仓序号：** 第 {add_idx + 1} 次（共 {_MAX_ADD_COUNT} 次上限）",
            f"**💵 加仓金额：** 余额 × {stake_pct*100:.0f}%",
            f"**⏱ 冷却时间：** {_COOLDOWN_HOURS} 小时",
        ]

        card = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": type_label},
                    "template": color,
                },
                "elements": [
                    {
                        "tag": "note",
                        "elements": [
                            {"tag": "plain_text", "content": f"{emoji} 加仓提案等待审批"},
                        ],
                    },
                    {"tag": "hr"},
                    {
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": "\n".join(body_lines)},
                    },
                    {"tag": "hr"},
                    {
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": tier_block},
                    },
                    {"tag": "hr"},
                    {
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": f"**{p['reason']}**"},
                    },
                    {"tag": "hr"},
                    {
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": f"**审批码：** `{code}`"},
                    },
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {"tag": "plain_text", "content": f"{emoji} 批准加仓"},
                                "type": "primary",
                                "url": approve_url,
                            },
                            {
                                "tag": "button",
                                "text": {"tag": "plain_text", "content": "❌ 否决"},
                                "type": "danger",
                                "url": reject_url,
                            },
                        ],
                    },
                ],
            },
        }
        _send_card(card)


# ── 主流程 ───────────────────────────────────────────────

def main():
    ts = dt.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] 📊 加仓Scanner启动")

    new_proposals = scan()
    if not new_proposals:
        print(f"  ✅ 无加仓机会")
        return 0

    # 过滤掉已有pending的交易对（避免重复提案）
    existing_pending = load_proposals()
    pending_pairs = {p["pair"] for p in existing_pending if p["status"] == "pending"}
    to_add = [p for p in new_proposals if p["pair"] not in pending_pairs]

    if not to_add:
        print(f"  ⏭️  所有交易对已有pending提案，跳过")
        return 0

    # 保存新提案
    all_proposals = existing_pending + to_add
    save_proposals(all_proposals)
    print(f"  📝 新增 {len(to_add)} 条提案：{[p['pair'] for p in to_add]}")

    # 发送飞书卡片
    send_proposal_cards(to_add)
    print(f"  📤 已发送 {len(to_add)} 张飞书审批卡片")

    return len(to_add)


if __name__ == "__main__":
    n = main()
    sys.exit(0)
