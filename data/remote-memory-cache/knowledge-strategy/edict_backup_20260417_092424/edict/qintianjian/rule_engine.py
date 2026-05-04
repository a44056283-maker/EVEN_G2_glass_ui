#!/usr/bin/env python3
"""
钦天监 · 规则引擎
6层规则评估：P0风控 → P1市场+资金流 → P2技术+情绪 → P3事件
所有规则触发后生成提案，写入 pending_approvals.json
不直接执行任何操作，只生成情报和提案
"""
import json
import math
import sys
import time
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ── 路径配置 ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = Path.home() / "edict" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
PROPOSALS_FILE = DATA_DIR / "qintianjian_proposals.json"
INTERVENTION_LOG = DATA_DIR / "logs" / "qintianjian.log"
INTERVENTION_LOG.parent.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BASE_DIR))
from data_collector import collect_all, fetch_funding_rate, fetch_btc_dominance, fetch_fear_greed

# ── 飞书配置 ─────────────────────────────────────────────
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"
FEISHU_ALERT_COOLDOWN = 300  # 5分钟防刷

# ── 动态获取公网入口（读取 server.py 写入的配置文件）───
def _get_public_base() -> str:
    pf = Path(__file__).parent / "data" / ".public_base_url"
    if pf.exists():
        return pf.read_text().strip()
    # 回退：从 dashboard server 的 data 目录读
    pf2 = Path.home() / "edict" / "dashboard" / "data" / ".public_base_url"
    if pf2.exists():
        return pf2.read_text().strip()
    return "http://127.0.0.1:7891"  # 最终回退

# ── 数据结构 ─────────────────────────────────────────────
@dataclass
class RuleResult:
    rule_id: str
    layer: str          # risk / market / flow / tech / sentiment / event
    level: str         # P0 / P1 / P2 / P3
    severity: str       # critical / high / medium / low
    urgency: int       # 1-10
    triggered: bool
    title: str
    reason: str
    current_value: str
    threshold: str
    action: str        # freeze / block_entry / alert / force_close / etc.
    data: dict = field(default_factory=dict)

@dataclass
class Proposal:
    id: str
    rule_id: str
    layer: str
    level: str
    severity: str
    urgency: int
    title: str
    reason: str
    current_value: str
    threshold: str
    action: str
    status: str        # pending / approved / rejected / executed / expired
    created_at: str
    decided_at: str = ""
    decided_by: str = ""
    market_data: dict = field(default_factory=dict)

# ── 工具函数 ─────────────────────────────────────────────
def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%m-%d %H:%M:%S")
    icons = {"INFO": "ℹ️", "WARN": "⚠️", "OK": "✅", "ERR": "🚨", "RULE": "📋"}
    line = f"[{ts}] {icons.get(level,'•')} {msg}"
    print(line)
    with open(INTERVENTION_LOG, "a") as f:
        f.write(line + "\n")

def load_proposals() -> list:
    try:
        if PROPOSALS_FILE.exists():
            with open(PROPOSALS_FILE) as f:
                return json.load(f)
    except:
        pass
    return []

def save_proposals(proposals: list):
    with open(PROPOSALS_FILE, "w") as f:
        json.dump(proposals, f, ensure_ascii=False, indent=2)

def proposal_id() -> str:
    ts = datetime.now().strftime("%m%d%H%M")
    return f"QT-{ts}-{abs(hash(str(time.time()))) % 10000:04d}"

def already_pending(rule_id: str) -> bool:
    """检查同一规则是否有待审批提案"""
    proposals = load_proposals()
    for p in proposals:
        if p.get("rule_id") == rule_id and p.get("status") == "pending":
            return True
    return False

# ── Feishu 通知 ─────────────────────────────────────────
def send_feishu(proposal: dict, template: str = "red"):
    """发送飞书卡片提案"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    emoji_map = {"critical": "🚨", "high": "⚠️", "medium": "🟡", "low": "🟢"}
    emoji = emoji_map.get(proposal.get("severity", "medium"), "⚡")

    body_lines = [
        f"**当前值：** `{proposal.get('current_value', 'N/A')}`",
        f"**阈值：** `{proposal.get('threshold', 'N/A')}`",
        f"**原因：** {proposal.get('reason', 'N/A')}",
        f"**建议动作：** `{proposal.get('action', '观察')}`",
        f"**提案ID：** `{proposal.get('id', '')}`",
    ]
    # 添加市场数据
    md = proposal.get("market_data", {})
    if md.get("btc_price"):
        body_lines.append(f"**BTC价格：** `${md.get('btc_price', 0):,.0f}`")
    if md.get("rsi"):
        body_lines.append(f"**RSI：** `{md.get('rsi', 0):.1f}`")
    if md.get("fear_greed"):
        body_lines.append(f"**FG指数：** `{md.get('fear_greed', 0)} ({md.get('fg_label', '')})`")
    if md.get("open_count") is not None:
        body_lines.append(f"**当前持仓：** `{md.get('open_count', 0)} 仓位`")

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"【钦天监】{proposal.get('title', '')}"},
                "template": template,
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(body_lines)}},
                {"tag": "hr"},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "✅ 批准执行"},
                            "type": "primary",
                            "url": f"{_get_public_base()}/qintianjian/approve/{proposal['id']}",
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "❌ 否决"},
                            "type": "danger",
                            "url": f"{_get_public_base()}/qintianjian/reject/{proposal['id']}",
                        },
                    ],
                },
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"🕐 {ts} · 钦天监情报系统自动生成 · 请在15分钟内审批"}},
            ],
        },
    }
    try:
        import requests
        req = requests.Session()
        req.trust_env = False
        req.post(FEISHU_WEBHOOK, json=card, timeout=10)
        log(f"[飞书] ✅ 已发送提案: {proposal['id']} {proposal['title']}", "OK")
    except Exception as e:
        log(f"[飞书] ❌ 发送失败: {e}", "ERR")

def send_feishu_result(proposal: dict, result_action: str):
    """发送审批结果通知"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    is_approve = result_action == "approved"
    template = "green" if is_approve else "red"
    emoji = "✅" if is_approve else "❌"
    body = (
        f"{emoji} **{proposal.get('title', '')}**\n\n"
        f"**结果：** {'已批准执行' if is_approve else '已否决'}\n"
        f"**规则ID：** `{proposal.get('rule_id', '')}`\n"
        f"**动作：** `{proposal.get('action', '')}`\n"
        f"**审批时间：** {ts}\n"
        f"**审批人：** 爸"
    )
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"【钦天监】{'批准' if is_approve else '否决'} #{proposal.get('id', '')}"},
                "template": template,
            },
            "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": body}}],
        },
    }
    try:
        import requests
        req = requests.Session()
        req.trust_env = False
        req.post(FEISHU_WEBHOOK, json=card, timeout=10)
    except:
        pass

# ── 持仓统计 ─────────────────────────────────────────────
def get_position_stats(positions: list) -> dict:
    """计算持仓统计（日盈亏/最大持仓时间等）"""
    if not positions:
        return {"count": 0, "max_hours": 0, "worst_pnl_pct": 0, "total_pnl_abs": 0}

    now = datetime.now()
    max_hours = 0.0
    worst_pnl_pct = 0.0
    total_pnl = 0.0

    for p in positions:
        # 持仓时间
        opened = p.get("opened_at", "")
        if opened:
            try:
                opened_dt = datetime.strptime(opened[:19], "%Y-%m-%dT%H:%M:%S")
                hours = (now - opened_dt).total_seconds() / 3600
                max_hours = max(max_hours, hours)
            except:
                pass
        # 盈亏
        pnl_abs = p.get("pnl_abs", 0) or 0
        total_pnl += pnl_abs
        entry = p.get("entry_price", 1)
        current = p.get("current_price", entry)
        if entry > 0:
            pnl_pct = (current - entry) / entry * 100
            if p.get("is_short"):
                pnl_pct = -pnl_pct
            worst_pnl_pct = min(worst_pnl_pct, pnl_pct)

    return {
        "count": len(positions),
        "max_hours": max_hours,
        "worst_pnl_pct": worst_pnl_pct,
        "total_pnl_abs": total_pnl,
    }

# ══════════════════════════════════════════════════════════════════
# P0 · 风控层
# ══════════════════════════════════════════════════════════════════

class RiskLayer:
    DAILY_LOSS_LIMIT = -5.0
    WEEKLY_LOSS_LIMIT = -15.0
    MAX_HOLDING_HOURS = 48
    TRAILING_LOSS_LIMIT = -2.0
    TRAILING_HOURS = 24

    @classmethod
    def check_all(cls, market_data: dict) -> list[RuleResult]:
        results = []
        results.append(cls.check_daily_loss(market_data))
        results.append(cls.check_weekly_loss(market_data))
        results.append(cls.check_max_holding(market_data))
        results.append(cls.check_trailing_loss(market_data))
        return [r for r in results if r.triggered]

    @classmethod
    def check_daily_loss(cls, md: dict) -> RuleResult:
        stats = md.get("stats", {})
        positions = md.get("positions", [])
        pos_stats = get_position_stats(positions)
        total_pnl = pos_stats.get("total_pnl_abs", 0)
        balances = md.get("balances", {})
        # 用第一个有余额的账户估算日盈亏百分比
        daily_pnl_pct = 0.0
        for port, bal in balances.items():
            total = bal.get("total", 1)
            if total > 10:
                daily_pnl_pct = total_pnl / total * 100
                break

        result = RuleResult(
            rule_id="R001", layer="risk", level="P0",
            triggered=False, severity="critical", urgency=10,
            title="单日亏损熔断",
            reason="", current_value=f"{daily_pnl_pct:+.2f}%",
            threshold=f"≤ {cls.DAILY_LOSS_LIMIT}%",
            action="freeze",
            data={"daily_pnl_pct": daily_pnl_pct}
        )
        if daily_pnl_pct <= cls.DAILY_LOSS_LIMIT:
            result.triggered = True
            result.reason = f"当前日盈亏 {daily_pnl_pct:+.2f}% ≤ 熔断阈值 {cls.DAILY_LOSS_LIMIT}%，建议全市场冻结"
            log(f"[触发] R001 单日亏损熔断: {daily_pnl_pct:+.2f}%", "ERR")
        return result

    @classmethod
    def check_weekly_loss(cls, md: dict) -> RuleResult:
        # 周盈亏用日盈亏估算（简化版，实际应从日志计算）
        stats = md.get("stats", {})
        positions = md.get("positions", [])
        pos_stats = get_position_stats(positions)
        balances = md.get("balances", {})
        weekly_pnl_pct = 0.0
        for port, bal in balances.items():
            total = bal.get("total", 1)
            if total > 10:
                # 简化：周 = 日 × 7（实际应从数据库读取）
                daily_pnl_pct = pos_stats.get("total_pnl_abs", 0) / total * 100
                weekly_pnl_pct = daily_pnl_pct * 7
                break

        result = RuleResult(
            rule_id="R002", layer="risk", level="P0",
            triggered=False, severity="critical", urgency=9,
            title="单周亏损暂停",
            reason="", current_value=f"{weekly_pnl_pct:+.2f}%（估算）",
            threshold=f"≤ {cls.WEEKLY_LOSS_LIMIT}%",
            action="pause_trading",
            data={"weekly_pnl_pct": weekly_pnl_pct}
        )
        if weekly_pnl_pct <= cls.WEEKLY_LOSS_LIMIT:
            result.triggered = True
            result.reason = f"估算周盈亏 {weekly_pnl_pct:+.2f}% ≤ 暂停阈值 {cls.WEEKLY_LOSS_LIMIT}%，建议暂停新开仓"
            log(f"[触发] R002 单周亏损暂停: {weekly_pnl_pct:+.2f}%", "ERR")
        return result

    @classmethod
    def check_max_holding(cls, md: dict) -> RuleResult:
        positions = md.get("positions", [])
        pos_stats = get_position_stats(positions)
        max_hours = pos_stats.get("max_hours", 0)
        oldest_pos = None
        now = datetime.now()
        for p in positions:
            opened = p.get("opened_at", "")
            if opened:
                try:
                    od = datetime.strptime(opened[:19], "%Y-%m-%dT%H:%M:%S")
                    hours = (now - od).total_seconds() / 3600
                    if hours >= max_hours:
                        oldest_pos = p
                except:
                    pass

        result = RuleResult(
            rule_id="R003", layer="risk", level="P0",
            triggered=max_hours > cls.MAX_HOLDING_HOURS,
            severity="high", urgency=8,
            title="最大持仓超时",
            reason="",
            current_value=f"{max_hours:.1f}小时（{oldest_pos.get('symbol','') if oldest_pos else 'N/A'}）",
            threshold=f"> {cls.MAX_HOLDING_HOURS}小时",
            action="force_close",
            data={"position": oldest_pos, "hours": max_hours}
        )
        if max_hours > cls.MAX_HOLDING_HOURS:
            sym = oldest_pos.get("symbol", "?") if oldest_pos else "?"
            result.reason = f"{sym} 持仓已达 {max_hours:.1f} 小时，超过{cls.MAX_HOLDING_HOURS}小时限制，建议强制平仓"
            log(f"[触发] R003 持仓超时: {max_hours:.1f}h", "WARN")
        return result

    @classmethod
    def check_trailing_loss(cls, md: dict) -> RuleResult:
        """持仓24小时以上仍未盈利，强制止损"""
        positions = md.get("positions", [])
        now = datetime.now()
        worst = None
        worst_pct = 0.0
        worst_hours = 0.0

        for p in positions:
            opened = p.get("opened_at", "")
            if not opened:
                continue
            try:
                od = datetime.strptime(opened[:19], "%Y-%m-%dT%H:%M:%S")
                hours = (now - od).total_seconds() / 3600
            except:
                continue
            if hours < cls.TRAILING_HOURS:
                continue
            entry = p.get("entry_price", 1)
            current = p.get("current_price", entry)
            if entry <= 0:
                continue
            pnl_pct = (current - entry) / entry * 100
            if p.get("is_short"):
                pnl_pct = -pnl_pct
            if pnl_pct < worst_pct:
                worst_pct = pnl_pct
                worst = p
                worst_hours = hours

        result = RuleResult(
            rule_id="R004", layer="risk", level="P0",
            triggered=worst is not None,
            severity="high", urgency=8,
            title="最大未盈利持仓",
            reason="",
            current_value=f"浮亏 {worst_pct:.2f}% / {worst_hours:.0f}h（{worst.get('symbol','') if worst else ''}）" if worst else "无",
            threshold=f"≤ {cls.TRAILING_LOSS_LIMIT}% 且 > {cls.TRAILING_HOURS}h",
            action="force_stop_loss",
            data={"position": worst, "pnl_pct": worst_pct, "hours": worst_hours}
        )
        if worst and worst_pct <= cls.TRAILING_LOSS_LIMIT:
            sym = worst.get("symbol", "?")
            result.reason = f"{sym} 持仓{worst_hours:.0f}小时仍浮亏 {worst_pct:.2f}%，超过拖尾止损阈值，建议强制止损"
            log(f"[触发] R004 拖尾止损: {worst_pct:.2f}%", "WARN")
            result.triggered = True
        return result

# ══════════════════════════════════════════════════════════════════
# P1 · 市场结构层
# ══════════════════════════════════════════════════════════════════

class MarketLayer:
    ATR_MIN_PCT = 1.5
    ADX_MIN = 25
    VWAP_MAX_DEV = 1.0

    @classmethod
    def check_all(cls, md: dict) -> list[RuleResult]:
        btc = md.get("symbols", {}).get("BTC", {})
        results = [
            cls.check_atr(btc),
            cls.check_adx(btc),
            cls.check_vwap(btc),
            cls.check_ema_direction(btc),
        ]
        return [r for r in results if r.triggered]

    @classmethod
    def check_atr(cls, btc: dict) -> RuleResult:
        atr_pct = btc.get("atr_pct", 0)
        price = btc.get("price", 0)
        result = RuleResult(
            rule_id="M001", layer="market", level="P1",
            triggered=False, severity="medium", urgency=6,
            title="ATR波动率过滤",
            reason="", current_value=f"ATR: {atr_pct:.2f}%",
            threshold=f"最小 {cls.ATR_MIN_PCT}%",
            action="block_entry",
            data={"atr_pct": atr_pct}
        )
        if 0 < atr_pct < cls.ATR_MIN_PCT:
            result.triggered = True
            result.reason = f"BTC ATR {atr_pct:.2f}% < {cls.ATR_MIN_PCT}%，低波动市场易扫损，建议阻止新开仓"
            log(f"[触发] M001 ATR过低: {atr_pct:.2f}%", "WARN")
        return result

    @classmethod
    def check_adx(cls, btc: dict) -> RuleResult:
        adx = btc.get("adx", 0)
        result = RuleResult(
            rule_id="M002", layer="market", level="P1",
            triggered=False, severity="medium", urgency=5,
            title="ADX趋势强度过滤",
            reason="", current_value=f"ADX: {adx:.1f}",
            threshold=f"最小 {cls.ADX_MIN}",
            action="block_entry",
            data={"adx": adx}
        )
        if 0 < adx < cls.ADX_MIN:
            result.triggered = True
            result.reason = f"ADX {adx:.1f} < {cls.ADX_MIN}，趋势不明显，建议阻止追趋势开仓"
            log(f"[触发] M002 ADX过低: {adx:.1f}", "WARN")
        return result

    @classmethod
    def check_vwap(cls, btc: dict) -> RuleResult:
        price = btc.get("price", 0)
        vwap = btc.get("vwap", 0)
        if not price or not vwap:
            return cls._empty("M003")
        dev = abs(price - vwap) / vwap * 100
        result = RuleResult(
            rule_id="M003", layer="market", level="P1",
            triggered=False, severity="medium", urgency=6,
            title="VWAP偏离过滤",
            reason="", current_value=f"偏离: {dev:.2f}%",
            threshold=f"最大 ±{cls.VWAP_MAX_DEV}%",
            action="block_entry",
            data={"deviation_pct": dev}
        )
        if dev > cls.VWAP_MAX_DEV:
            result.triggered = True
            result.reason = f"BTC偏离VWAP {dev:.2f}% > {cls.VWAP_MAX_DEV}%，追单风险高，建议等待回归"
            log(f"[触发] M003 VWAP偏离: {dev:.2f}%", "WARN")
        return result

    @classmethod
    def check_ema_direction(cls, btc: dict) -> RuleResult:
        price = btc.get("price", 0)
        ema50 = btc.get("ema50", 0)
        if not price or not ema50:
            return cls._empty("M004")
        above = price > ema50
        result = RuleResult(
            rule_id="M004", layer="market", level="P1",
            triggered=False, severity="low", urgency=3,
            title="EMA50方向信号",
            reason=f"BTC价格{'在EMA50上方（偏多）' if above else '在EMA50下方（偏空）'}",
            current_value="偏多" if above else "偏空",
            threshold="顺势操作",
            action="direction_bias",
            data={"above_ema50": above}
        )
        return result

    @classmethod
    def _empty(cls, rule_id: str) -> RuleResult:
        return RuleResult(
            rule_id=rule_id, layer="market", level="P1",
            triggered=False, severity="low", urgency=0,
            title=rule_id, reason="数据不足", current_value="N/A",
            threshold="N/A", action="none"
        )

# ══════════════════════════════════════════════════════════════════
# P1 · 资金流层
# ══════════════════════════════════════════════════════════════════

class FlowLayer:
    BTC_D_THRESHOLD = 52.0
    FUNDING_MAX = 0.05
    OI_CHANGE_MAX = 20.0

    @classmethod
    def check_all(cls, md: dict) -> list[RuleResult]:
        btc = md.get("symbols", {}).get("BTC", {})
        sentiment = md.get("sentiment", {})
        results = [
            cls.check_btc_dominance(sentiment),
            cls.check_funding_rate(btc),
        ]
        return [r for r in results if r.triggered]

    @classmethod
    def check_btc_dominance(cls, sentiment: dict) -> RuleResult:
        btc_d = sentiment.get("btc_dominance", 50.0)
        strong = btc_d > cls.BTC_D_THRESHOLD
        result = RuleResult(
            rule_id="F001", layer="flow", level="P1",
            triggered=strong, severity="medium", urgency=6,
            title="BTC.Dominance强势预警",
            reason="",
            current_value=f"BTC.D: {btc_d:.1f}%",
            threshold=f"> {cls.BTC_D_THRESHOLD}%",
            action="direction_bias",
            data={"btc_dominance": btc_d}
        )
        if strong:
            result.reason = f"BTC.D {btc_d:.1f}% > {cls.BTC_D_THRESHOLD}%，BTC强势，不建议做空山寨"
            log(f"[触发] F001 BTC.D强势: {btc_d:.1f}%", "WARN")
        return result

    @classmethod
    def check_funding_rate(cls, btc: dict) -> RuleResult:
        fr = btc.get("funding_rate", 0)
        fr_e8 = btc.get("funding_rate_e8", 0)
        fr_display = fr_e8 / 1e8 * 100 if fr_e8 else fr * 100
        result = RuleResult(
            rule_id="F002", layer="flow", level="P1",
            triggered=False, severity="high", urgency=7,
            title="资金费率异常预警",
            reason="",
            current_value=f"费率: {fr_display:+.3f}%",
            threshold=f"> {cls.FUNDING_MAX}%",
            action="block_entry",
            data={"funding_rate": fr, "funding_rate_pct": fr_display}
        )
        if abs(fr_display) > cls.FUNDING_MAX:
            direction = "正费率（多头付钱给空头）" if fr_display > 0 else "负费率（空头付钱给多头）"
            result.triggered = True
            result.reason = f"资金费率 {fr_display:+.3f}% 过高（阈值 {cls.FUNDING_MAX}%），{direction}，极端市场可能反转"
            log(f"[触发] F002 资金费率过高: {fr_display:+.3f}%", "WARN")
        return result

# ══════════════════════════════════════════════════════════════════
# P2 · 技术信号层
# ══════════════════════════════════════════════════════════════════

class TechLayer:
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    BB_SQUEEZE = 80.0
    VOL_RATIO_MIN = 3.0

    @classmethod
    def check_all(cls, md: dict) -> list[RuleResult]:
        btc = md.get("symbols", {}).get("BTC", {})
        results = [
            cls.check_rsi(btc),
            cls.check_bollinger(btc),
            cls.check_volume(btc),
        ]
        return [r for r in results if r.triggered]

    @classmethod
    def check_rsi(cls, btc: dict) -> RuleResult:
        rsi = btc.get("rsi", 50)
        result = RuleResult(
            rule_id="T001", layer="tech", level="P2",
            triggered=False, severity="medium", urgency=6,
            title="RSI极值信号",
            reason="", current_value=f"RSI: {rsi:.1f}",
            threshold=f"<{cls.RSI_OVERSOLD} 超卖 / >{cls.RSI_OVERBOUGHT} 超买",
            action="signal_boost",
            data={"rsi": rsi}
        )
        if rsi < cls.RSI_OVERSOLD:
            result.triggered = True
            result.reason = f"RSI {rsi:.1f} < {cls.RSI_OVERSOLD}，极度恐慌可能反弹，关注做多机会"
            result.data["signal"] = "oversold"
            log(f"[触发] T001 RSI超卖: {rsi:.1f}", "WARN")
        elif rsi > cls.RSI_OVERBOUGHT:
            result.triggered = True
            result.reason = f"RSI {rsi:.1f} > {cls.RSI_OVERBOUGHT}，极度贪婪可能回调，关注做空机会"
            result.data["signal"] = "overbought"
            log(f"[触发] T001 RSI超买: {rsi:.1f}", "WARN")
        return result

    @classmethod
    def check_bollinger(cls, btc: dict) -> RuleResult:
        bb_width = btc.get("bb_width", 100)
        result = RuleResult(
            rule_id="T002", layer="tech", level="P2",
            triggered=False, severity="low", urgency=4,
            title="布林带收口预警",
            reason="", current_value=f"带宽: {bb_width:.1f}%",
            threshold=f"< {cls.BB_SQUEEZE}%",
            action="watch_breakout",
            data={"bb_width": bb_width}
        )
        if bb_width < cls.BB_SQUEEZE:
            result.triggered = True
            result.reason = f"布林带收口 {bb_width:.1f}% < {cls.BB_SQUEEZE}%，突破在即，关注方向选择"
            log(f"[触发] T002 布林带收口: {bb_width:.1f}%", "INFO")
        return result

    @classmethod
    def check_volume(cls, btc: dict) -> RuleResult:
        vr = btc.get("vol_ratio", 1.0)
        result = RuleResult(
            rule_id="T003", layer="tech", level="P2",
            triggered=False, severity="medium", urgency=5,
            title="量能爆发确认",
            reason="", current_value=f"量比: {vr:.1f}x",
            threshold=f"> {cls.VOL_RATIO_MIN}x",
            action="confirm_breakout",
            data={"vol_ratio": vr}
        )
        if vr > cls.VOL_RATIO_MIN:
            result.triggered = True
            result.reason = f"成交量放大 {vr:.1f} 倍，突破信号得到量能确认，机会信号增强"
            log(f"[触发] T003 量能爆发: {vr:.1f}x", "INFO")
        return result

# ══════════════════════════════════════════════════════════════════
# P2 · 情绪层
# ══════════════════════════════════════════════════════════════════

class SentimentLayer:
    FEAR_EXTREME = 10
    FEAR_THRESHOLD = 25
    GREED_THRESHOLD = 75

    @classmethod
    def check_all(cls, md: dict) -> list[RuleResult]:
        sentiment = md.get("sentiment", {})
        fg = sentiment.get("fear_greed", 50)
        results = [
            cls.check_fg_extreme(fg),
            cls.check_fg_fear(fg),
            cls.check_fg_greed(fg),
        ]
        return [r for r in results if r.triggered]

    @classmethod
    def check_fg_extreme(cls, fg: int) -> RuleResult:
        result = RuleResult(
            rule_id="S001", layer="sentiment", level="P2",
            triggered=False, severity="high", urgency=8,
            title="FG极度恐慌逆向机会",
            reason="", current_value=f"FG: {fg}",
            threshold=f"≤ {cls.FEAR_EXTREME}",
            action="reverse_signal",
            data={"fear_greed": fg}
        )
        if fg <= cls.FEAR_EXTREME:
            result.triggered = True
            result.reason = f"FG={fg} 极度恐慌，市场可能触底反弹，关注逆向买入机会"
            log(f"[触发] S001 FG极度恐慌: {fg}", "WARN")
        return result

    @classmethod
    def check_fg_fear(cls, fg: int) -> RuleResult:
        result = RuleResult(
            rule_id="S002", layer="sentiment", level="P2",
            triggered=False, severity="medium", urgency=6,
            title="恐惧区间禁止做空",
            reason="", current_value=f"FG: {fg}",
            threshold=f"< {cls.FEAR_THRESHOLD}",
            action="block_short",
            data={"fear_greed": fg}
        )
        if fg < cls.FEAR_THRESHOLD:
            result.triggered = True
            result.reason = f"FG={fg} 处于恐惧区间，不建议做空"
            log(f"[触发] S002 FG恐惧禁止做空: {fg}", "INFO")
        return result

    @classmethod
    def check_fg_greed(cls, fg: int) -> RuleResult:
        result = RuleResult(
            rule_id="S003", layer="sentiment", level="P2",
            triggered=False, severity="medium", urgency=6,
            title="贪婪区间禁止做多",
            reason="", current_value=f"FG: {fg}",
            threshold=f"> {cls.GREED_THRESHOLD}",
            action="block_long",
            data={"fear_greed": fg}
        )
        if fg > cls.GREED_THRESHOLD:
            result.triggered = True
            result.reason = f"FG={fg} 处于贪婪区间，不建议做多"
            log(f"[触发] S003 FG贪婪禁止做多: {fg}", "INFO")
        return result

# ══════════════════════════════════════════════════════════════════
# P3 · 事件层
# ══════════════════════════════════════════════════════════════════

class EventLayer:
    @classmethod
    def check_all(cls, md: dict) -> list[RuleResult]:
        results = [
            cls.check_etf_expiry(),
        ]
        return [r for r in results if r.triggered]

    @classmethod
    def check_etf_expiry(cls) -> RuleResult:
        now = datetime.now()
        day = now.day
        weekday = now.weekday()  # 0=周一
        is_expiry = day >= 22 and weekday == 4
        result = RuleResult(
            rule_id="E001", layer="event", level="P3",
            triggered=is_expiry, severity="medium", urgency=5,
            title="ETF期权到期周预警",
            reason=f"每月第四周五，期权大量到期，大幅波动概率高" if is_expiry else "",
            current_value=now.strftime("%Y-%m-%d"),
            threshold="每月第四周五",
            action="reduce_position",
            data={"is_expiry_week": is_expiry}
        )
        if is_expiry:
            log("[触发] E001 ETF到期周", "WARN")
        return result

# ══════════════════════════════════════════════════════════════════
# 提案生成
# ══════════════════════════════════════════════════════════════════

def submit_proposal(rule: RuleResult, md: dict) -> Optional[Proposal]:
    """将规则结果转为提案并发送飞书"""
    if already_pending(rule.rule_id):
        log(f"[跳过] {rule.rule_id} 已有待审批提案", "INFO")
        return None

    proposals = load_proposals()
    p = Proposal(
        id=proposal_id(),
        rule_id=rule.rule_id,
        layer=rule.layer,
        level=rule.level,
        severity=rule.severity,
        urgency=rule.urgency,
        title=rule.title,
        reason=rule.reason,
        current_value=rule.current_value,
        threshold=rule.threshold,
        action=rule.action,
        status="pending",
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        market_data={
            "btc_price": md.get("symbols", {}).get("BTC", {}).get("price", 0),
            "rsi": md.get("symbols", {}).get("BTC", {}).get("rsi", 0),
            "fear_greed": md.get("sentiment", {}).get("fear_greed", 0),
            "fg_label": md.get("sentiment", {}).get("fg_label", ""),
            "open_count": len(md.get("positions", [])),
            "atr_pct": md.get("symbols", {}).get("BTC", {}).get("atr_pct", 0),
            "funding_rate": md.get("symbols", {}).get("BTC", {}).get("funding_rate_e8", 0) / 1e8 * 100,
        }
    )
    proposals.append(asdict(p))
    save_proposals(proposals)
    log(f"[提案] {p.id} {p.rule_id} {p.title} → {p.action}", "RULE")

    # 发送飞书（按严重程度选颜色）
    template = {"critical": "red", "high": "orange", "medium": "yellow", "low": "blue"}.get(p.severity, "red")
    send_feishu(asdict(p), template)
    return p

# ══════════════════════════════════════════════════════════════════
# 规则引擎主函数
# ══════════════════════════════════════════════════════════════════

LAYER_MAP = {
    "risk": RiskLayer,
    "market": MarketLayer,
    "flow": FlowLayer,
    "tech": TechLayer,
    "sentiment": SentimentLayer,
    "event": EventLayer,
}

def run_engine(submit: bool = True) -> dict:
    """
    运行完整规则引擎
    1. 采集数据
    2. 评估所有规则
    3. 提交审批提案
    返回：{triggered: [rules], market_data: {...}}
    """
    log("开始采集市场数据...", "INFO")
    md = collect_all()
    btc = md.get("symbols", {}).get("BTC", {})
    log(f"BTC=${btc.get('price',0):,.0f} RSI={btc.get('rsi',0):.1f} FG={md.get('sentiment',{}).get('fear_greed',0)} ATR={btc.get('atr_pct',0):.2f}%", "INFO")

    all_triggered = []

    for layer_name, layer_class in LAYER_MAP.items():
        try:
            results = layer_class.check_all(md)
            for r in results:
                all_triggered.append(r)
                if submit:
                    submit_proposal(r, md)
        except Exception as e:
            log(f"[错误] {layer_name}层检查失败: {e}", "ERR")

    # 按 urgency 降序
    all_triggered.sort(key=lambda r: -r.urgency)

    log(f"规则检查完成: {len(all_triggered)} 项触发", "INFO")
    return {
        "triggered": [asdict(r) for r in all_triggered],
        "market_data": md,
    }

def approve_proposal(proposal_id: str) -> dict:
    """批准提案并返回执行动作"""
    proposals = load_proposals()
    for p in proposals:
        if p.get("id") == proposal_id and p.get("status") == "pending":
            p["status"] = "approved"
            p["decided_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            p["decided_by"] = "爸"
            save_proposals(proposals)
            send_feishu_result(p, "approved")
            log(f"[审批] ✅ 批准: {proposal_id} {p.get('title','')}", "OK")
            return {"ok": True, "proposal": p, "action": p.get("action"), "rule_id": p.get("rule_id")}
    return {"ok": False, "error": "提案不存在或状态不是pending"}

def reject_proposal(proposal_id: str) -> dict:
    """否决提案"""
    proposals = load_proposals()
    for p in proposals:
        if p.get("id") == proposal_id and p.get("status") == "pending":
            p["status"] = "rejected"
            p["decided_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            p["decided_by"] = "爸"
            save_proposals(proposals)
            send_feishu_result(p, "rejected")
            log(f"[审批] ❌ 否决: {proposal_id} {p.get('title','')}", "OK")
            return {"ok": True, "proposal": p}
    return {"ok": False, "error": "提案不存在或状态不是pending"}

def get_proposals(status: str = None, limit: int = 50) -> list:
    """获取提案列表"""
    proposals = load_proposals()
    if status:
        proposals = [p for p in proposals if p.get("status") == status]
    return sorted(proposals, key=lambda p: p.get("created_at", ""), reverse=True)[:limit]

if __name__ == "__main__":
    result = run_engine()
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
