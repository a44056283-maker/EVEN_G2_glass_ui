#!/usr/bin/env python3
"""
兵部综合巡查播报脚本
直接curl API生成飞书卡片，不走AI生成，永久免疫超时
"""
import json, urllib.request, urllib.error
from datetime import datetime

BINGBU_API = "http://127.0.0.1:7891/api"
BOTS = [9090, 9091, 9092, 9093, 9094, 9095, 9096, 9097]
EDICT_DATA = "/Users/luxiangnan/edict/data"
SHANGSHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"

def http_get(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return None

def check_bots():
    statuses = {}
    for port in BOTS:
        ok = http_get(f"http://localhost:{port}/api/v1/ping") is not None
        statuses[port] = "🟢正常" if ok else "🔴离线"
    return statuses

def get_positions():
    return http_get(f"{BINGBU_API}/bingbu/positions") or {}

def get_sentiment():
    return http_get(f"{BINGBU_API}/sentiment") or {}

def get_latest_intervention():
    try:
        with open(f"{EDICT_DATA}/bingbu_intervention.json") as f:
            items = json.load(f)
            if items:
                return items[0]
    except:
        pass
    return None

def get_freeze_status():
    try:
        with open(f"{EDICT_DATA}/bingbu_freeze.json") as f:
            return json.load(f)
    except:
        return {"frozen": False, "frozen_pairs": []}

def get_intervention_state():
    """读取干预状态，判断是否需要播报"""
    try:
        with open(f"{EDICT_DATA}/bingbu_intervention_state.json") as f:
            return json.load(f)
    except:
        return {}

def scan_conflict_positions(direction: str) -> tuple:
    """
    扫描方向冲突持仓：
    - direction == "SHORT" → 有多头持仓 = 冲突
    - direction == "LONG" → 有空头持仓 = 冲突
    返回 (has_conflict, conflict_details)
    """
    positions = get_positions()
    pos_list = positions.get("positions", [])
    conflicts = []
    for p in pos_list:
        amount = float(p.get("amount", 0))
        is_long = p.get("side") == "LONG"   # 使用 side 字段判断，不依赖 amount 符号
        pair = p.get("pair", "?")
        pnl = p.get("unrealized_pnl", 0)
        if direction == "SHORT" and is_long:
            conflicts.append(f"  ⚠️ {pair}: 多头浮盈{pnl:.2f}U")
        elif direction == "LONG" and not is_long:
            conflicts.append(f"  ⚠️ {pair}: 空头浮盈{pnl:.2f}U")
    return len(conflicts) > 0, conflicts

def should_broadcast(positions: dict, sentiment: dict, bot_status: dict = None) -> tuple:
    """
    判断本次巡查是否需要播报：
    返回 (should_send, reason)
    - (True, "有冲突持仓")   → 扫描到冲突持仓，需要播报
    - (True, "机器人掉线")   → 有机器人离线，需要播报
    - (True, "有持仓")      → 正常巡查，有持仓就播报
    ⚠️ 不再允许静默跳过：所有状态都应让用户看到
    """
    # 检测机器人掉线（必须播报）
    if bot_status:
        offline_bots = [port for port, status in bot_status.items() if "离线" in status]
        if offline_bots:
            return True, f"⚠️ 机器人掉线: {offline_bots}"

    state = get_intervention_state()
    urgency = sentiment.get("sentiment_urgency", 0)
    direction = sentiment.get("sentiment_direction", "NEUTRAL")
    force_executed = state.get("force_executed", False)
    force_executed_at = state.get("force_executed_at", "")

    # ⚠️ 强制播报：即使刚执行过黑天鹅，也要告知用户当前状态
    if force_executed:
        count = positions.get("count", 0)
        if direction in ("SHORT", "LONG"):
            has_conflict, conflicts = scan_conflict_positions(direction)
            if has_conflict:
                return True, f"黑天鹅平仓后仍有冲突持仓: {len(conflicts)}个"
            else:
                return True, f"黑天鹅已于{force_executed_at}平仓，当前无冲突持仓（需关注）"
        # NEUTRAL → 标记需关注
        return True, f"黑天鹅已于{force_executed_at}执行，方向={direction}，需关注"

    # 紧急度≥9 → 必须播报，让用户知道黑天鹅已触发
    if urgency >= 9 and direction in ("SHORT", "LONG"):
        return True, f"🚨 黑天鹅触发（紧急度={urgency}），需审批"

    # 有持仓就播报
    count = positions.get("count", 0)
    if count > 0:
        return True, f"正常巡查，有{count}个持仓"

    # 无持仓也播报（告知状态）
    return True, "无持仓，正常"

def get_news_from_pool():
    """从sentiment_pool读取最新新闻（带URL）"""
    try:
        with open(f"{EDICT_DATA}/sentiment_pool.json") as f:
            pool = json.load(f)
        news_items = pool.get("news", {}).get("items", [])[:4]
        return news_items
    except:
        return []

def build_card(positions, sentiment, bot_status, intervention, freeze):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_pnl = positions.get("total_pnl", 0)
    count = positions.get("count", 0)

    # Bot状态行
    bot_line = " | ".join([f"Bot-{p}: {s}" for p, s in bot_status.items()])

    # 冻结状态
    frozen = freeze.get("frozen", False)
    frozen_pairs = freeze.get("frozen_pairs", [])
    if frozen:
        freeze_txt = f"🔴已冻结{frozen_pairs}" if frozen_pairs else "🔴已冻结"
    else:
        freeze_txt = "✅正常"

    # 最新干预
    if intervention:
        action = intervention.get("action", "")
        reason = intervention.get("reason", "")
        ts = intervention.get("timestamp", "")
        action_emoji = {"freeze": "❄️", "unfreeze": "🔥", "freeze_pair": "❄️",
                        "inject_long": "📈", "inject_short": "📉",
                        "emergency_exit_all": "⚡", "force_exit_pair": "💥"}.get(action, "📌")
        inter_txt = f"{action_emoji}{action} | {reason} | {ts}"
    else:
        inter_txt = "✅无干预"

    # 舆情
    sig = sentiment.get("sentiment_signal", "N/A")
    conf = sentiment.get("sentiment_confidence", 0)
    fg_val = sentiment.get("fear_greed_value", 0)
    fg_label = sentiment.get("fear_greed_label", "")
    sentiment_txt = f"{sig}（信心{conf}%）| 恐惧贪婪{fg_val}={fg_label}" if fg_val else f"{sig}（信心{conf}%）"

    # 持仓摘要按交易所分组
    pos_list = positions.get("positions", [])
    gate_pos = [p for p in pos_list if p.get("exchange") == "Gate.io"]
    okx_pos = [p for p in pos_list if p.get("exchange") == "OKX"]

    # 格式化各交易所持仓
    def fmt_pos(pos):
        lines = []
        by_pair = {}
        for p in pos:
            pair = p.get("pair", "?")
            by_pair.setdefault(pair, []).append(p)
        for pair, ps in by_pair.items():
            sides = {}
            for p in ps:
                side = p.get("side", "?")
                sides[side] = f"{p.get('amount')}×{p.get('leverage')}x @{p.get('current_price')}"
            side_str = " / ".join([f"{s}({v})" for s, v in sides.items()])
            pnl = sum(p.get("unrealized_pnl", 0) for p in ps)
            pnl_str = f"+{pnl:.2f}" if pnl >= 0 else f"{pnl:.2f}"
            lines.append(f"  • {pair}: {side_str} | 浮盈{pnl_str}")
        return "\n".join(lines) if lines else "  （无持仓）"

    gate_txt = fmt_pos(gate_pos)
    okx_txt = fmt_pos(okx_pos)

    # 新闻舆情（从sentiment_pool读取）
    news_items = get_news_from_pool()
    news_content = ""
    if news_items:
        news_lines = []
        for n in news_items[:3]:
            src = n.get("source", "?")
            title = n.get("title", "")[:45]
            url = n.get("url", "")
            sent = n.get("sentiment", "neutral")
            emoji = "🔴" if sent == "negative" else "🟢" if sent == "positive" else "⚪"
            news_lines.append(f"{emoji} [{src}] {title}\n   🔗 {url}")
        news_content = "\n".join(news_lines)
    else:
        news_content = "暂无数据"

    # 按钮（巡查卡片专用，审批类操作需要提案系统）
    # unfreeze 为保护性操作可直接执行；freeze 需要走提案审批
    btn_base = "https://openclaw.tianlu2026.org"

    # Feishu interactive card（统一格式：标题 → 原生按钮 → 持仓总览 → 状态 → 新闻）
    card = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"🛡️ 兵部巡查播报 {now}"},
                "template": "blue"
            },
            "elements": [
                # ── ① 快速操作按钮（原生button组件，高识别度）──────────────
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": "**【快速操作】请在以下按钮中选择**"},
                },
                {"tag": "hr"},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "🔓 直接解冻"},
                            "type": "primary",
                            "url": f"{btn_base}/bingbu/unfreeze",
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "🔒 提交冻结提案"},
                            "type": "warning",
                            "url": f"{btn_base}/bingbu/freeze",
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "📊 状态查询"},
                            "type": "secondary",
                            "url": f"{btn_base}/bingbu/status",
                        },
                    ],
                },
                {"tag": "hr"},
                # ── ② 持仓总览 ──────────────────────────────────────
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**📋 持仓概览**\n"
                            f"总仓位：{count}个 | 总浮盈：{'+' if total_pnl >= 0 else ''}{total_pnl:.2f} USDT\n\n"
                            f"**Gate.io（{len(gate_pos)}个仓位）**\n{gate_txt}\n\n"
                            f"**OKX（{len(okx_pos)}个仓位）**\n{okx_txt}"
                        )
                    }
                },
                {"tag": "hr"},
                # ── ③ 系统状态 ────────────────────────────────────
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**🤖 Bot状态**：{bot_line}\n\n"
                            f"**❄️ 冻结状态**：{freeze_txt}\n\n"
                            f"**📌 最新干预**：{inter_txt}\n\n"
                            f"**🤖 舆情信号**：{sentiment_txt}"
                        )
                    }
                },
                {"tag": "hr"},
                # ── ④ 今日要闻 ────────────────────────────────────
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**📰 今日要闻**\n{news_content}"
                        )
                    }
                }
            ]
        }
    }
    return card

def send_card(card):
    payload = json.dumps(card, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        SHANGSHU_WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def main():
    positions = get_positions()
    sentiment = get_sentiment()
    bot_status = check_bots()
    intervention = get_latest_intervention()
    freeze = get_freeze_status()

    # 判断是否需要播报
    should_send, reason = should_broadcast(positions, sentiment, bot_status)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 巡查 | 仓位:{positions.get('count',0)} | 判断:{reason}")

    if not should_send:
        # 静默跳过，不发飞书卡片
        return True

    card = build_card(positions, sentiment, bot_status, intervention, freeze)
    result = send_card(card)

    code = result.get("StatusCode", -1)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 兵部巡查完成 | 仓位:{positions.get('count',0)} | "
          f"浮盈:{positions.get('total_pnl',0):.2f} | 飞书:{code}")
    return code == 0

if __name__ == "__main__":
    ok = main()
    exit(0 if ok else 1)
