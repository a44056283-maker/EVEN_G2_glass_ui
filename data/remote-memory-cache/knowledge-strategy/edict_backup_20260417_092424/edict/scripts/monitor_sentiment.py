#!/usr/bin/env python3
"""
兵部 · 舆情监控代理（含审批流程 + 黑天鹅Cooldown）
读取 ~/.sentiment_latest.json（聚合信号）

干预流程（双重保障）：
  1. 黑天鹅警报 → 写入 pending_approvals.json → 飞书通知门下省审批
  2. 审批通过 → 兵部执行 freeze_open()
  3. 紧急度≥9（保护本金）→ 提交审批，由门下省决定

审批命令：
  approve <alert_id>  → 批准执行
  reject  <alert_id>  → 否决执行
  python3 audit_guard.py approve/reject <id>
"""

import sys, json, os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

# ── 原子写入工具（防止并发写入导致文件损坏）────────────────
def _atomic_write_json(filepath: Path, data, indent: int = 2) -> None:
    """将data以JSON格式原子写入filepath（先写.tmp再rename）"""
    tmp = str(filepath) + ".tmp"
    Path(tmp).write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")
    os.replace(tmp, str(filepath))

# ── 路径配置（统一用硬编码绝对路径，禁止相对路径）────────
SENTIMENT_FILE = Path.home() / ".sentiment_latest.json"
EDICT_DATA_DIR = Path("/Users/luxiangnan/edict/data")
FREEZE_FILE    = EDICT_DATA_DIR / "bingbu_freeze.json"
INJECT_FILE    = EDICT_DATA_DIR / "bingbu_sentiment_inject.json"
INTERV_FILE    = EDICT_DATA_DIR / "bingbu_intervention.json"
PENDING_FILE   = EDICT_DATA_DIR / "pending_approvals.json"   # 统一写到这里
REJECTED_FILE  = EDICT_DATA_DIR / "bingbu_recently_rejected.json"

# ── Cooldown配置 ────────────────────────────────────────
FREEZE_COOLDOWN_MINUTES = 30   # 冻结冷却时间

# ── 飞书 Webhook（统一发到一个群：尚书省）─────────────────
SHANGSHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"
FEISHU_WEBHOOK = SHANGSHU_WEBHOOK   # 兼容旧代码
MENXIA_WEBHOOK = SHANGSHU_WEBHOOK   # 门下省审批也发到同一群


# ═══════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════

def load_sentiment() -> Optional[dict]:
    if not SENTIMENT_FILE.exists():
        return None
    try:
        return json.loads(SENTIMENT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_interventions() -> list:
    try:
        if INTERV_FILE.exists():
            return json.loads(INTERV_FILE.read_text())
    except:
        pass
    return []


def load_rejected_events() -> list:
    """加载最近被否决的黑天鹅事件"""
    try:
        if REJECTED_FILE.exists():
            return json.loads(REJECTED_FILE.read_text())
    except:
        pass
    return []


def is_event_recently_rejected(sentiment_data: dict, bs_cats: list) -> bool:
    """
    检查同一个黑天鹅事件是否在最近被否决过
    判断标准：FG值相同（允许fg=0旧格式）+ 理由重合 + 30分钟内
    """
    from datetime import timedelta
    fg = sentiment_data.get("fear_greed_value", 0)
    reasons = sentiment_data.get("reasons", [])
    bs_cats = bs_cats or []
    new_cats_key = "|".join(sorted(bs_cats)) if bs_cats else ""

    # 宽松匹配：FG ≤ 20（极度恐慌区间）时，只要FG相同就触发冷却
    # 不依赖精确的cats_key（新闻数量每次不同），避免重复创建审批
    for event in load_rejected_events():
        stored_fg = event.get("fg_value", 0)
        if stored_fg == 0:
            continue  # 旧格式无FG值，跳过

        # 极度恐慌区间（FG ≤ 20）：FG相同即触发6小时冷却
        # FG≤20 是持续数小时的市场状态，2小时冷却太短会反复创建审批
        if stored_fg == fg and fg <= 20:
            rejected_at = datetime.strptime(event["rejected_at"], "%Y-%m-%d %H:%M:%S")
            if datetime.now() - rejected_at < timedelta(hours=6):
                remaining = 6 * 3600 - (datetime.now() - rejected_at).total_seconds()
                print(f"[兵部舆情] ⏳ FG={fg}（极度恐慌）刚被否决（{int(remaining//60)}分钟前），6小时冷却中，跳过")
                return True
        elif stored_fg != fg:
            continue  # FG不同，跳过

        stored_cats_key = event.get("cats_key", "")

        # 判断是否为同类事件（精确匹配）
        same_event = False
        if new_cats_key and new_cats_key == stored_cats_key:
            same_event = True
        elif stored_cats_key:
            reasons_list = [r for r in stored_cats_key.split("|") if r]
            if any(r in reasons_list for r in reasons):
                same_event = True

        if same_event:
            rejected_at = datetime.strptime(event["rejected_at"], "%Y-%m-%d %H:%M:%S")
            if datetime.now() - rejected_at < timedelta(minutes=30):
                remaining = 30 * 60 - (datetime.now() - rejected_at).total_seconds()
                print(f"[兵部舆情] ⏳ 同类事件刚被否决（{int(remaining//60)}分钟前），跳过")
                return True
    return False


def save_rejected_event(sentiment_data: dict, bs_cats: list):
    """记录被否决的黑天鹅事件"""
    fg = sentiment_data.get("fear_greed_value", 0)
    # 用 reasons 而非 bs_cats 存储；bs_cats 只有类别（如"市场恐慌"），
    # 而 reasons 包含具体指标（如"Fear&Greed极低(14)"），用于精确比对
    reasons = sentiment_data.get("reasons", [])
    cats_key = "|".join(sorted(reasons)) if reasons else "|".join(sorted(bs_cats or []))
    events = load_rejected_events()
    events.insert(0, {
        "fg_value": fg,
        "cats_key": cats_key,
        "rejected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    events = events[:20]  # 保留最近20条
    REJECTED_FILE.write_text(json.dumps(events, ensure_ascii=False, indent=2))


def load_pending() -> list:
    try:
        if PENDING_FILE.exists():
            items = json.loads(PENDING_FILE.read_text())
            # 自动清理超时的审批（超过30分钟自动忽略）
            now = datetime.now()
            cleaned = []
            for item in items:
                if item.get("status") == "pending":
                    created = datetime.strptime(item.get("created_at", "2000-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S")
                    age_minutes = (now - created).total_seconds() / 60
                    if age_minutes > 30:
                        print(f"[兵部舆情] ⏰ 审批超时({age_minutes:.1f}min)，自动忽略: {item.get('id')}")
                        continue
                cleaned.append(item)
            if len(cleaned) != len(items):
                save_pending(cleaned)
            return cleaned
    except:
        pass
    return []


def save_pending(items: list):
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    PENDING_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2))


def save_intervention(action: str, reason: str, sentiment_data: dict):
    """记录干预到bingbu_intervention.json"""
    interventions = load_interventions()
    item = {
        "id": len(interventions) + 1,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "reason": reason,
        "sentiment": {
            "direction": sentiment_data.get("direction", ""),
            "confidence": sentiment_data.get("confidence", 0),
            "urgency": sentiment_data.get("urgency", 0),
            "fear_greed_value": sentiment_data.get("fear_greed_value", 0),
            "black_swan_categories": sentiment_data.get("black_swan_categories", []),
            "reasons": sentiment_data.get("reasons", []),
        },
        "result": "success",
    }
    interventions.insert(0, item)
    interventions = interventions[:200]
    INTERV_FILE.write_text(json.dumps(interventions, ensure_ascii=False, indent=2))


def get_last_freeze_time() -> Optional[datetime]:
    """从干预记录中找最近一次freeze时间"""
    for item in load_interventions():
        if item.get("action") == "freeze":
            try:
                return datetime.strptime(item["timestamp"], "%Y-%m-%d %H:%M:%S")
            except:
                pass
    return None


def is_freeze_on_cooldown() -> bool:
    """检查是否在冻结冷却期内"""
    last = get_last_freeze_time()
    if last is None:
        return False
    elapsed = datetime.now() - last
    on_cooldown = elapsed < timedelta(minutes=FREEZE_COOLDOWN_MINUTES)
    if on_cooldown:
        remaining = timedelta(minutes=FREEZE_COOLDOWN_MINUTES) - elapsed
        print(f"[兵部舆情] ⏳ 冻结冷却中，剩余 {int(remaining.total_seconds()//60)} 分钟")
    return on_cooldown


def feishu_to_bingbu(title: str, content: str, level: str = "INFO") -> None:
    """发送到兵部飞书（interactive card, template=red）"""
    try:
        import requests, urllib3
        urllib3.disable_warnings()
        icon = {"INFO": "✅", "WARN": "🟠", "ALERT": "🚨", "P0": "🔴"}.get(level, "ℹ️")
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"{icon} 【兵部舆情】{title}"},
                    "template": "red"
                },
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": content}}
                ]
            }
        }
        requests.post(FEISHU_WEBHOOK, json=card, timeout=10, verify=False)
    except Exception as e:
        print(f"[兵部舆情] 兵部飞书通知失败: {e}", file=sys.stderr)


def feishu_to_menxia(title: str, content: str, alert_id: str = "",
                      proposal_id: str = "", pair: str = "", action: str = "freeze",
                      approve_url: str = "", reject_url: str = "",
                      extra_info: dict = None) -> None:
    """
    发送到门下省审批（统一卡片格式：按钮紧跟标题下方）

    用于：
    - 黑天鹅警报 → approve_url = /bingbu/approve?code=xxx
    - 执行报告/拒绝通知（无按鈕）→ approve_url=""
    """
    try:
        import requests, urllib3
        urllib3.disable_warnings()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        if approve_url and reject_url:
            # ── 审批请求卡片：按鈕在标题正下方 ─────────────────────
            card = _build_menxia_approval_card(
                title=title, content=content, alert_id=alert_id,
                proposal_id=proposal_id, pair=pair, action=action,
                approve_url=approve_url, reject_url=reject_url,
                extra_info=extra_info,
            )
        else:
            # ── 通知卡片（执行报告/拒绝）：无按鈕 ──────────────────
            card = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {"tag": "plain_text", "content": title},
                        "template": "green" if "已执行" in title or "已批准" in title else "grey",
                    },
                    "elements": [
                        {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                    ],
                },
            }
        requests.post(MENXIA_WEBHOOK, json=card, timeout=10, verify=False)
    except Exception as e:
        print(f"[兵部舆情] 门下省飞书通知失败: {e}", file=sys.stderr)


def _build_menxia_approval_card(title: str, content: str, alert_id: str,
                                 proposal_id: str, pair: str, action: str,
                                 approve_url: str, reject_url: str,
                                 extra_info: dict = None) -> dict:
    """
    构建门下省审批卡片（统一格式）：
      卡片Header → 按鈕区（标题正下方）→ 提案信息 → 内容详情
    """
    from pathlib import Path
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent))
    try:
        import bingbu_card_builder as _b
        return _b.build_bingbu_card(
            action=action,
            proposal_id=proposal_id or alert_id,
            pair=pair or "全市场",
            reason=title,
            approve_url=approve_url,
            reject_url=reject_url,
            body_text=content,
            expires_minutes=15,
            extra_info=extra_info,
        )
    except Exception:
        # 回退：手动构建卡片（原生button组件，视觉冲击力强）
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"🔔 【门下省待审批】{title} · {now_str}"},
                    "template": "red",
                },
                "elements": [
                    # ① 操作区标题
                    {"tag": "div", "text": {"tag": "lark_md", "content": "**【审批操作】请在以下按钮中选择**"}},
                    {"tag": "hr"},
                    # ② 原生按钮组
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {"tag": "plain_text", "content": "✅ 批准执行"},
                                "type": "primary",
                                "url": approve_url,
                            },
                            {
                                "tag": "button",
                                "text": {"tag": "plain_text", "content": "❌ 否决此提案"},
                                "type": "danger",
                                "url": reject_url,
                            },
                        ],
                    },
                    {"tag": "hr"},
                    # ③ 内容区
                    {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                ],
            },
        }


# ═══════════════════════════════════════════════════════
# 审批流程
# ═══════════════════════════════════════════════════════

def add_pending_approval(alert_id: str, alert_type: str, reason: str,
                          sentiment_data: dict, severity: str = "high") -> bool:
    """
    添加待审批项（写入 pending_approvals.json）
    返回 True=新增成功，False=已在队列中
    """
    pending = load_pending()
    # 检查是否已有相同FG的黑天鹅提案（同4小时内不重复）
    fg_val = sentiment_data.get("fear_greed_value", 0)
    if alert_type == "black_swan" and fg_val <= 20:
        for p in pending:
            p_fg = p.get("sentiment", {}).get("fear_greed", 0)
            if p_fg == fg_val and p.get("type") == "black_swan":
                print(f"[兵部舆情] ⏳ FG={fg_val}的黑天鹅提案已存在({p['id']})，跳过重复")
                return False
    # 检查ID是否已存在
    for p in pending:
        if p.get("id") == alert_id and p.get("status") == "pending":
            print(f"[兵部舆情] ⏳ 告警 {alert_id} 已在待审批队列中，跳过")
            return False

    item = {
        "id": alert_id,
        "type": alert_type,
        "reason": reason,
        "severity": severity,
        "action": "freeze",
        "sentiment": {
            "direction": sentiment_data.get("direction", ""),
            "confidence": sentiment_data.get("confidence", 0),
            "urgency": sentiment_data.get("urgency", 0),
            "fear_greed": sentiment_data.get("fear_greed_value", 0),
            "signal": sentiment_data.get("signal", ""),
            "reasons": sentiment_data.get("reasons", []),
        },
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "pending",
    }
    pending.append(item)
    save_pending(pending)
    return True


def submit_for_approval(sentiment_data: dict, bs_cats: list) -> bool:
    """
    提交黑天鹅冻结审批
    1. 检查Cooldown
    2. 检查同类事件是否刚被否决
    3. 生成告警ID
    4. 写入pending_approvals
    5. 通知门下省
    """
    if is_freeze_on_cooldown():
        print("[兵部舆情] ⏳ 冻结冷却中，跳过提交审批")
        return False

    # 检查同类事件是否刚被否决（防止同事件重复产生审批）
    if is_event_recently_rejected(sentiment_data, bs_cats):
        return False

    # 生成告警ID
    ts = datetime.now()
    alert_id = f"BS-{ts.strftime('%m%d%H%M')}-{abs(hash(str(bs_cats))) % 10000:04d}"

    reason = f"黑天鹅警报 | {'/'.join(bs_cats)} | FG={sentiment_data.get('fear_greed_value','?')} | 信心={sentiment_data.get('confidence','?')}"

    added = add_pending_approval(
        alert_id=alert_id,
        alert_type="black_swan",
        reason=reason,
        sentiment_data=sentiment_data,
        severity="critical",
    )

    if added:
        # 飞书通知门下省
        fg_val = sentiment_data.get('fear_greed_value', 0)
        reasons = sentiment_data.get('reasons', [])
        BASE_URL = "https://openclaw.tianlu2026.org"
        msg = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 当前市场：Fear&Greed = {fg_val}/100（{'极度恐慌' if fg_val <= 20 else '恐慌'}）\n"
            f"📈 信心指数：{sentiment_data.get('confidence','?')}%\n"
            f"📋 触发原因：{' | '.join(reasons) if reasons else '综合市场极度恐慌'}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 **建议动作：冻结全市场**\n"
            f"批准后 → 全市场Bot禁止开仓，防止逆势交易被套\n"
            f"否决后 → Bot继续正常交易（可能继续亏损）"
        )
        feishu_to_menxia(
            title=f"🚨 黑天鹅警报 [{alert_id}]",
            content=msg,
            alert_id=alert_id,
            proposal_id=alert_id,
            pair="全市场",
            action="freeze",
            approve_url=f"{BASE_URL}/bingbu/approve?code={alert_id}",
            reject_url=f"{BASE_URL}/bingbu/reject?code={alert_id}",
            extra_info={
                "恐惧指数": f"{fg_val}/100",
                "置信度": f"{sentiment_data.get('confidence','?')}%",
                "触发类型": ' | '.join(reasons) if reasons else '综合恐慌',
            },
        )
        feishu_to_bingbu("⏳ 审批已提交", f"告警ID={alert_id}，等待门下省审批", "WARN")

    return added


# ═══════════════════════════════════════════════════════
# 兵部动作（执行层）
# ═══════════════════════════════════════════════════════

def do_freeze() -> bool:
    """执行冻结（供审批通过后调用）"""
    try:
        payload = {
            "frozen": True,
            "reason": "approved_black_swan",
            "last_freeze_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cooldown_minutes": FREEZE_COOLDOWN_MINUTES,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        tmp = str(FREEZE_FILE) + ".tmp"
        Path(tmp).write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        os.replace(tmp, str(FREEZE_FILE))
        print("[兵部舆情] ✅ 冻结标记已写入 (bingbu_freeze.json)")
        return True
    except Exception as e:
        print(f"[兵部舆情] ❌ 冻结标记写入失败: {e}", file=sys.stderr)
        return False


def do_unfreeze() -> None:
    """解除冻结"""
    try:
        if FREEZE_FILE.exists():
            os.remove(FREEZE_FILE)
            print("[兵部舆情] ✅ 已解除冻结标记")
    except Exception as e:
        print(f"[兵部舆情] ❌ 解除冻结失败: {e}", file=sys.stderr)


def do_force_exit() -> list:
    """强制平所有多头仓位（只平多头，跳过空头）"""
    import requests
    results = []
    # 区分 Gate (9090-9092) 和 OKX (9093) 的 API 差异
    # Gate: POST /api/v1/forceexit/{trade_id}
    # OKX: POST /api/v1/forceexit (body) 或 DELETE /api/v1/trades/{trade_id}
    ports = {
        9090: ("freqtrade", "freqtrade", "gate"),
        9091: ("freqtrade", "freqtrade", "gate"),
        9092: ("freqtrade", "freqtrade", "gate"),
        9093: ("admin", "Xy@06130822", "okx"),
        9094: ("admin", "Xy@06130822", "okx"),
        9095: ("admin", "Xy@06130822", "okx"),
        9096: ("admin", "Xy@06130822", "okx"),
        9097: ("admin", "Xy@06130822", "okx"),
    }
    for port, (user, pwd, exchange) in ports.items():
        try:
            import base64
            creds = base64.b64encode(f"{user}:{pwd}".encode()).decode()
            headers_gate = {"Authorization": f"Basic {creds}"}
            headers_okx = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
            r = requests.get(f"http://localhost:{port}/api/v1/status",
                             headers=headers_gate, timeout=10)
            if r.status_code != 200:
                results.append(f"[端口{port}]: 认证失败({r.status_code})")
                continue
            positions = r.json()
            long_count = 0
            short_count = 0
            for pos in positions:
                # 检查持仓方向：amount > 0 为多头，amount < 0 为空头
                amount = float(pos.get("amount", 0))
                if amount > 0:
                    long_count += 1
                    trade_id = pos.get("trade_id")
                    pair = pos.get("pair")
                    if exchange == "gate":
                        # Gate: URL路径方式
                        rr = requests.post(f"http://localhost:{port}/api/v1/forceexit/{trade_id}",
                                           headers=headers_gate, timeout=15)
                    else:
                        # OKX: 优先用 body 方式，失败则用 DELETE
                        rr = requests.post(f"http://localhost:{port}/api/v1/forceexit",
                                          headers=headers_okx,
                                          json={"tradeid": trade_id},
                                          timeout=15)
                        if rr.status_code == 405:
                            # OKX 不支持 body 方式，降级为 DELETE
                            rr = requests.delete(f"http://localhost:{port}/api/v1/trades/{trade_id}",
                                                headers=headers_okx, timeout=15)
                    msg = "成功" if rr.status_code in (200, 201) else f"失败({rr.status_code})"
                    results.append(f"{pair}[{port}]({exchange}):{msg}")
                else:
                    short_count += 1
            if long_count == 0 and short_count > 0:
                results.append(f"[端口{port}]({exchange}): 无多头持仓({short_count}个空头跳过)")
            elif long_count == 0 and short_count == 0:
                results.append(f"[端口{port}]({exchange}): 无持仓")
        except Exception as e:
            results.append(f"[端口{port}]: {e}")
    return results


# ── 冻结/解冻 ──────────────────────────────────────────────────────
FREQTRADE_WHITELIST = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "DOGE/USDT:USDT"]

def do_freeze_all() -> tuple:
    """
    冻结所有Bot的新开仓（通过黑名单实现）
    返回 (frozen_pairs, results)
    """
    import requests
    results = []
    ports = {
        9090: ("freqtrade", "freqtrade"),
        9091: ("freqtrade", "freqtrade"),
        9092: ("freqtrade", "freqtrade"),
        9093: ("admin", "Xy@06130822"),
        9094: ("admin", "Xy@06130822"),
        9095: ("admin", "Xy@06130822"),
        9096: ("admin", "Xy@06130822"),
        9097: ("admin", "Xy@06130822"),
    }
    frozen_pairs = []

    for port, (user, pwd) in ports.items():
        try:
            import base64
            creds = base64.b64encode(f"{user}:{pwd}".encode()).decode()
            headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
            # 获取当前白名单
            r = requests.get(f"http://localhost:{port}/api/v1/whitelist",
                            headers=headers, timeout=5)
            if r.status_code != 200:
                results.append(f"[端口{port}]: 白名单获取失败({r.status_code})")
                continue
            whitelist = r.json().get("whitelist", [])
            if not whitelist:
                results.append(f"[端口{port}]: 白名单为空，跳过")
                continue
            # 将白名单添加到黑名单
            payload = {"blacklist": whitelist}
            r2 = requests.post(f"http://localhost:{port}/api/v1/blacklist",
                               headers=headers, json=payload, timeout=10)
            if r2.status_code == 200:
                results.append(f"[端口{port}]: 冻结{len(whitelist)}个交易对")
                frozen_pairs.extend(whitelist)
            else:
                results.append(f"[端口{port}]: 冻结失败({r2.status_code})")
        except Exception as e:
            results.append(f"[端口{port}]: {e}")

    return list(set(frozen_pairs)), results


def do_unfreeze_all(frozen_pairs: list) -> tuple:
    """
    解除冻结（仅移除冻结时添加的交易对，不影响原有黑名单）
    frozen_pairs: do_freeze_all() 返回的冻结交易对列表
    返回 (unfrozen_pairs, results)
    """
    import requests
    results = []
    ports = {
        9090: ("freqtrade", "freqtrade"),
        9091: ("freqtrade", "freqtrade"),
        9092: ("freqtrade", "freqtrade"),
        9093: ("admin", "Xy@06130822"),
        9094: ("admin", "Xy@06130822"),
        9095: ("admin", "Xy@06130822"),
        9096: ("admin", "Xy@06130822"),
        9097: ("admin", "Xy@06130822"),
    }
    unfrozen_pairs = []

    if not frozen_pairs:
        return [], ["无冻结交易对，跳过"]

    for port, (user, pwd) in ports.items():
        try:
            import base64
            creds = base64.b64encode(f"{user}:{pwd}".encode()).decode()
            headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
            # 只移除冻结时添加的交易对
            payload = {"blacklist": frozen_pairs}
            r2 = requests.delete(f"http://localhost:{port}/api/v1/blacklist",
                                headers=headers, json=payload, timeout=10)
            if r2.status_code == 200:
                results.append(f"[端口{port}]: 解冻{len(frozen_pairs)}个交易对")
                unfrozen_pairs.extend(frozen_pairs)
            else:
                results.append(f"[端口{port}]: 解冻失败({r2.status_code}) {r2.text[:50]}")
        except Exception as e:
            results.append(f"[端口{port}]: {e}")

    # 同时清除 force_executed 标志，防止 bingbu_patrol 继续静默
    try:
        state = _load_intervention_state()
        state["force_executed"] = False
        state["force_executed_at"] = ""
        state["force_executed_alert_id"] = ""
        _save_intervention_state(state)
    except Exception:
        pass

    return list(set(unfrozen_pairs)), results


# ── 干预状态追踪（防止重复播报）─────────────────────────────────────
INTERVENTION_STATE_FILE = Path.home() / "edict/data/bingbu_intervention_state.json"

def _load_intervention_state() -> dict:
    try:
        if INTERVENTION_STATE_FILE.exists():
            return json.loads(INTERVENTION_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"last_action": None, "last_action_time": None, "last_direction": None}

def _save_intervention_state(state: dict) -> None:
    try:
        INTERVENTION_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

def do_force_exit_by_trade_id(port: int, trade_id: str) -> tuple:
    """
    精准平仓：指定端口 + 指定 trade_id
    返回 (has_target, results_list)
    """
    import requests
    ports_cfg = {
        9090: ("freqtrade", "freqtrade", "gate"),
        9091: ("freqtrade", "freqtrade", "gate"),
        9092: ("freqtrade", "freqtrade", "gate"),
        9093: ("admin", "Xy@06130822", "okx"),
        9094: ("admin", "Xy@06130822", "okx"),
        9095: ("admin", "Xy@06130822", "okx"),
        9096: ("admin", "Xy@06130822", "okx"),
        9097: ("admin", "Xy@06130822", "okx"),
    }
    if port not in ports_cfg:
        return False, [f"[端口{port}]: 不支持的端口"]
    user, pwd, exchange = ports_cfg[port]
    try:
        import base64
        creds = base64.b64encode(f"{user}:{pwd}".encode()).decode()
        headers_gate = {"Authorization": f"Basic {creds}"}
        headers_okx = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
        if exchange == "gate":
            rr = requests.post(
                f"http://localhost:{port}/api/v1/forceexit/{trade_id}",
                headers=headers_gate, timeout=15,
            )
        else:
            rr = requests.post(
                f"http://localhost:{port}/api/v1/forceexit",
                headers=headers_okx, json={"tradeid": trade_id}, timeout=15,
            )
            if rr.status_code == 405:
                rr = requests.delete(
                    f"http://localhost:{port}/api/v1/trades/{trade_id}",
                    headers=headers_okx, timeout=15,
                )
        msg = "成功" if rr.status_code in (200, 201) else f"失败({rr.status_code})"
        return True, [f"端口{port} trade_id={trade_id}: {msg}"]
    except Exception as e:
        return False, [f"[端口{port}]: {e}"]


def do_force_exit_by_direction(direction: str) -> tuple:
    """
    按信号方向平仓：
    - direction == "SHORT" → 平所有多头（LONG）
    - direction == "LONG"  → 平所有空头（SHORT）
    - direction == "NEUTRAL" → 不操作
    返回 (has_conflict, results_list)
    """
    import requests
    if direction not in ("SHORT", "LONG"):
        return False, ["方向为NEUTRAL，跳过平仓"]

    results = []
    ports = {
        9090: ("freqtrade", "freqtrade", "gate"),
        9091: ("freqtrade", "freqtrade", "gate"),
        9092: ("freqtrade", "freqtrade", "gate"),
        9093: ("admin", "Xy@06130822", "okx"),
        9094: ("admin", "Xy@06130822", "okx"),
        9095: ("admin", "Xy@06130822", "okx"),
        9096: ("admin", "Xy@06130822", "okx"),
        9097: ("admin", "Xy@06130822", "okx"),
    }
    has_target = False

    for port, (user, pwd, exchange) in ports.items():
        try:
            import base64
            creds = base64.b64encode(f"{user}:{pwd}".encode()).decode()
            headers_gate = {"Authorization": f"Basic {creds}"}
            headers_okx = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
            r = requests.get(f"http://localhost:{port}/api/v1/status",
                           headers=headers_gate, timeout=10)
            if r.status_code != 200:
                results.append(f"[端口{port}]: 认证失败({r.status_code})")
                continue
            positions = r.json()
            for pos in positions:
                amount = float(pos.get("amount", 0))
                is_long = amount > 0
                target_side = "LONG" if direction == "SHORT" else "SHORT"
                should_close = (direction == "SHORT" and is_long) or (direction == "LONG" and not is_long)
                if not should_close:
                    continue
                has_target = True
                trade_id = pos.get("trade_id")
                pair = pos.get("pair")
                if exchange == "gate":
                    rr = requests.post(f"http://localhost:{port}/api/v1/forceexit/{trade_id}",
                                      headers=headers_gate, timeout=15)
                else:
                    rr = requests.post(f"http://localhost:{port}/api/v1/forceexit",
                                      headers=headers_okx,
                                      json={"tradeid": trade_id},
                                      timeout=15)
                    if rr.status_code == 405:
                        rr = requests.delete(f"http://localhost:{port}/api/v1/trades/{trade_id}",
                                          headers=headers_okx, timeout=15)
                msg = "成功" if rr.status_code in (200, 201) else f"失败({rr.status_code})"
                results.append(f"{pair}[{port}]({exchange}):{msg}")
        except Exception as e:
            results.append(f"[端口{port}]: {e}")

    if not has_target:
        return False, ["无冲突持仓，跳过平仓"]
    return True, results


def write_inject_file(direction: str, confidence: int, reason: str, target_pair: str = "") -> None:
    """写入注入文件"""
    try:
        payload = {
            "sentiment_direction": direction,
            "sentiment_confidence": confidence,
            "sentiment_reason": reason,
            "target_pair": target_pair,
            "source": "兵部舆情监控",
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        }
        tmp = str(INJECT_FILE) + ".tmp"
        Path(tmp).write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        os.replace(tmp, str(INJECT_FILE))
    except Exception as e:
        print(f"[兵部舆情] ❌ 注入文件写入失败: {e}", file=sys.stderr)


# ═══════════════════════════════════════════════════════
# 主监控函数
# ═══════════════════════════════════════════════════════

def monitor_sentiment(force: bool = False) -> list[dict]:
    """
    主监控函数
    force=True: 强制执行（execute_approved_action调用，跳过重复检查）
    force=False: 正常模式（带重复播报防护）
    """
    alerts = []
    sig = load_sentiment()

    if sig is None:
        return [{"type": "info", "level": "INFO",
                 "message": f"信号文件不存在 ({SENTIMENT_FILE})"}]

    direction   = sig.get("direction", "NEUTRAL")
    confidence  = sig.get("confidence", 0)
    urgency     = sig.get("urgency", 0)
    signal      = sig.get("signal", "")
    black_swan  = sig.get("black_swan_alert", False)
    bs_cats     = sig.get("black_swan_categories", [])
    fg_val      = sig.get("fear_greed_value", 50)
    reasons     = sig.get("reasons", [])
    top_news    = sig.get("top_news", [])
    fetch_time  = sig.get("fetch_time", "")

    print(f"[兵部舆情] [{fetch_time}] signal={signal} dir={direction} "
          f"conf={confidence} urg={urgency} bs={black_swan}({'/'.join(bs_cats)}) "
          f"fg={fg_val} | 理由:{' '.join(reasons)}")

    # ── Fallback保护层：FG≤20时强制推导方向，避免NEUTRAL误导 ───────────
    # aggregator层可能在恐慌场景仍输出NEUTRAL，这里兜底
    if fg_val <= 20 and direction == "NEUTRAL":
        direction = "SHORT"
        print(f"[兵部舆情] ⚠️ FG={fg_val}≤20且方向为NEUTRAL，强制覆盖为SHORT（恐慌市场做空为主）")

    # ── 紧急度 ≥9 → 冻结机制（走审批流程）──────────────────────────────
    if urgency >= 9:
        feishu_to_bingbu("🚨 紧急度警报",
                         f"紧急度={urgency} | 方向={direction}\n需要门下省审批才能执行冻结",
                         "ALERT")
        submitted = submit_for_approval(sig, ["urgency"])
        if submitted:
            alerts.append({
                "type": "urgency_pending",
                "level": "ALERT",
                "message": f"紧急度={urgency}，已提交审批",
            })
        return alerts

    # ── 黑天鹅处理 → 提交审批（不走自动干预）──────────────────────────
    if black_swan and bs_cats:
        alert_msg = (
            f"🚨 黑天鹅警报！{'/'.join(bs_cats)}\n"
            f"信号: {signal} | 信心:{confidence}\n"
            f"Fear&Greed: {fg_val}\n"
            f"理由: {' | '.join(reasons) if reasons else '综合市场极度恐慌'}"
        )

        feishu_to_bingbu("🚨 黑天鹅预警", alert_msg, "ALERT")

        # 走审批流程
        submitted = submit_for_approval(sig, bs_cats)
        if submitted:
            alerts.append({
                "type": "black_swan_pending",
                "level": "ALERT",
                "message": f"黑天鹅警报已提交审批，等待门下省确认 | {' | '.join(reasons)}",
            })
        else:
            alerts.append({
                "type": "black_swan_cooldown",
                "level": "WARN",
                "message": "黑天鹅条件满足但处于Cooldown，跳过",
            })
        # 黑天鹅优先级高于普通紧急干预，黑天鹅存在时跳过 urgency>=9 块
        return alerts

    # ── 紧急度 ≥9 → 冻结机制（走审批流程）──────────────────────────────
    # 独立于黑天鹅之外，高紧急度信号也能触发，但需要审批
    if urgency >= 9:
        feishu_to_bingbu("🚨 紧急度警报",
                         f"紧急度={urgency} | 方向={direction}\n需要门下省审批才能执行冻结",
                         "ALERT")
        submitted = submit_for_approval(sig, ["urgency"])
        if submitted:
            alerts.append({
                "type": "urgency_pending",
                "level": "ALERT",
                "message": f"紧急度={urgency}，已提交审批",
            })
        return alerts

    # ── 正常信号处理 ───────────────────────────────
    if direction == "LONG" and confidence >= 65:
        inject_reason = f"舆情做多 | 信心{confidence} | {signal} | {' '.join(reasons)}"
        write_inject_file("LONG", confidence, inject_reason)
        alerts.append({
            "type": "long_signal",
            "level": "OK",
            "message": inject_reason,
        })

    elif direction == "NEUTRAL" or signal == "观望":
        alerts.append({
            "type": "neutral",
            "level": "INFO",
            "message": f"观望信号 conf={confidence}，不干预",
        })

    else:
        alerts.append({
            "type": "other",
            "level": "INFO",
            "message": f"direction={direction} conf={confidence}，等待条件",
        })

    return alerts


# ═══════════════════════════════════════════════════════
# 审批执行入口（供外部调用）
# ═══════════════════════════════════════════════════════

def execute_approved_action(alert_id: str, pair: str = "") -> bool:
    """审批通过，支持黑天鹅(pending_approvals.json)和下单审计(bingbu_pending_proposals.json)两种通道
    pair: 交易对，用于在code重复时精准定位提案（如同一分钟内多个提案）"""
    pending = load_pending()
    for p in pending:
        if p.get("id") == alert_id and p.get("status") == "pending":
            p["status"] = "approved"
            p["approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_pending(pending)

            sig = p.get("sentiment", {})
            direction = sig.get("direction", "NEUTRAL")
            urgency = sig.get("urgency", 0)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 黑天鹅审批通过 → 方向对比平仓一次 + 冻结
            if direction in ("SHORT", "LONG"):
                has_conflict, exit_results = do_force_exit_by_direction(direction)
                save_intervention("black_swan_force_exit",
                                  f"黑天鹅审批通过，方向={direction}，强制平仓",
                                  sig)
                # 设置执行标记，防止重复平仓
                _save_intervention_state({
                    "last_action": "force_exit",
                    "last_action_time": now_str,
                    "last_direction": direction,
                    "is_frozen": False,
                    "force_executed": True,
                    "force_executed_at": now_str,
                    "force_executed_alert_id": alert_id,
                })
                feishu_to_bingbu("✅ 黑天鹅审批已执行",
                                 f"告警ID={alert_id}，方向={direction}，强制平仓\n{' '.join(exit_results)}",
                                 "P0")
                alerts_msg = f"强制平仓: {'; '.join(exit_results)}" if exit_results else "无冲突持仓"
                feishu_to_menxia("✅ 黑天鹅已执行",
                                 f"告警ID={alert_id}\n方向={direction}，{alerts_msg}")
            elif direction == "NEUTRAL":
                frozen_pairs, unfreeze_results = do_unfreeze_all([])
                save_intervention("unfreeze_all", f"黑天鹅审批通过，方向=NEUTRAL，解除冻结", sig)
                _save_intervention_state({
                    "last_action": "unfreeze",
                    "last_action_time": now_str,
                    "last_direction": "NEUTRAL",
                    "is_frozen": False,
                    "force_executed": True,
                    "force_executed_at": now_str,
                    "force_executed_alert_id": alert_id,
                })
                feishu_to_bingbu("✅ 黑天鹅审批已执行",
                                 f"告警ID={alert_id}，方向=NEUTRAL，解除冻结",
                                 "INFO")

            return True

    # 下单审计/兵部守卫通道(BS-前缀) → bingbu_pending_proposals.json → 执行对应动作
    if alert_id.startswith("BS-"):
        import json
        from typing import Optional as _json2
        BINGBU_PENDING = Path("/Users/luxiangnan/edict/data/bingbu_pending_proposals.json")
        if BINGBU_PENDING.exists():
            bpending = _json2.loads(BINGBU_PENDING.read_text())
            for p in bpending:
                _proposal_pair = p.get("pair", "")
                _pair_match = not pair or _proposal_pair == pair
                if p.get("id") == alert_id and p.get("status") == "pending" and _pair_match:
                    pair_clean = _proposal_pair.split(":")[0] or ""
                    action = p.get("action", "")
                    ok = False

                    if action in ("inject_long_pair", "inject_short_pair"):
                        target_close = "LONG" if action == "inject_short_pair" else "SHORT"
                        # ── 优先：精准定位持仓平仓 ──────────────────
                        target_port = p.get("details", {}).get("port", 0)
                        target_trade_id = p.get("details", {}).get("trade_id", "")
                        if target_port and target_trade_id:
                            has_conflict, exit_results = do_force_exit_by_trade_id(
                                target_port, target_trade_id)
                            if not has_conflict:
                                exit_results = [f"端口{target_port} trade_id={target_trade_id}: 未找到持仓（可能已平）"]
                        else:
                            # 兜底：trade_id为空时，按方向+交易对搜索
                            has_conflict, exit_results = do_force_exit_by_direction(target_close)
                            if not has_conflict:
                                exit_results = [f"{pair_clean} 方向={target_close}: 全市场无匹配持仓"]
                        # 2. 注入信号（写入 bingbu_sentiment_inject.json）
                        inject_dir = "SHORT" if action == "inject_short_pair" else "LONG"
                        confidence = p.get("details", {}).get("confidence", 80)
                        reason = p.get("reason", f"兵部S/R扫描干预：{pair_clean} {inject_dir}")
                        try:
                            write_inject_file(inject_dir, confidence, reason, pair_clean)
                        except Exception as inj_err:
                            print(f"[execute_approved_action] ⚠️ 注入信号写入失败（平仓已完成）: {inj_err}")
                            save_intervention(f"audit_{action}",
                                              f"审计提案执行异常：{pair_clean} {inject_dir}，"
                                              f"平仓成功但信号注入失败：{inj_err}",
                                              {})
                            feishu_to_bingbu("⚠️ 下单审计提案部分执行",
                                             f"{alert_id} {action} {pair_clean}\n"
                                             f"平仓：{' '.join(exit_results)}\n"
                                             f"信号注入：失败 {inj_err}",
                                             "WARN")
                            ok = False
                        else:
                            save_intervention(f"audit_{action}",
                                              f"审计提案执行：{pair_clean} {inject_dir}，"
                                              f"平仓结果：{' '.join(exit_results)}",
                                              {})
                            ok = True
                            feishu_to_bingbu("✅ 下单审计提案已执行",
                                             f"{alert_id} {action} {pair_clean} @ 端口{target_port}\n"
                                             f"Trade ID: `{target_trade_id}`\n"
                                             f"平仓：{' '.join(exit_results)}\n"
                                             f"信号注入：{inject_dir} @ 信心{confidence}",
                                             "INFO")

                    elif action == "force_exit_pair":
                        # 原有平仓逻辑
                        try:
                            sys.path.insert(0, "/Users/luxiangnan/edict/dashboard")
                            from monitor_sentiment import _do_force_exit_pair
                            r = _do_force_exit_pair(pair_clean)
                            ok = r.get("success", False)
                        except Exception as ex:
                            ok = False
                            print("[execute_approved_action] force_exit error: " + str(ex))
                        feishu_to_bingbu("✅ 下单审计提案已执行",
                                         f"{alert_id} force_exit {pair_clean} → {'成功' if ok else '失败'}",
                                         "INFO")

                    elif action == "emergency_exit_all":
                        # 全市场双向强平
                        try:
                            sys.path.insert(0, "/Users/luxiangnan/edict/dashboard")
                            from monitor_sentiment import _do_emergency_exit_all
                            r = _do_emergency_exit_all()
                            ok = r.get("success", False)
                        except Exception as ex:
                            ok = False
                            print("[execute_approved_action] emergency_exit_all error: " + str(ex))
                        feishu_to_bingbu("✅ 全市场双向强平已执行",
                                         f"{alert_id} emergency_exit_all\n{r.get('details', '')}",
                                         "P0")

                    elif action in ("freeze_pair", "freeze"):
                        # 分级冻结
                        level = p.get("details", {}).get("level", "L4")
                        try:
                            sys.path.insert(0, "/Users/luxiangnan/edict/dashboard")
                            from monitor_sentiment import _do_freeze
                            r = _do_freeze(pair_clean or None, level)
                            ok = r.get("success", False)
                        except Exception as ex:
                            ok = False
                            print("[execute_approved_action] freeze error: " + str(ex))
                        scope = f"{pair_clean}" if pair_clean else "全市场"
                        feishu_to_bingbu("✅ 冻结已执行",
                                         f"{alert_id} freeze {scope} [{level}]\n{r.get('details', '')}",
                                         "WARN")

                    elif action == "black_swan_freeze":
                        # 黑天鹅冻结（bingbu_pending_proposals.json里的黑天鹅提案）
                        try:
                            # do_force_exit_by_direction 和 do_freeze 都是本文件本地函数（546/351行），无需跨文件import
                            has_conflict, exit_results = do_force_exit_by_direction("LONG")
                            _, exit_short = do_force_exit_by_direction("SHORT")
                            exit_results = (exit_results or []) + (exit_short or [])
                            do_freeze()
                            save_intervention("black_swan_freeze",
                                              f"黑天鹅冻结审批通过，全平+冻结",
                                              {})
                            ok = True
                        except Exception as ex:
                            ok = False
                            print("[execute_approved_action] black_swan_freeze error: " + str(ex))
                        feishu_to_bingbu("✅ 黑天鹅冻结已执行",
                                         f"{alert_id} black_swan_freeze\n{' '.join(exit_results or [])}",
                                         "P0")

                    else:
                        feishu_to_bingbu("⚠️ 未知动作类型",
                                         f"{alert_id} action={action}，跳过执行", "WARN")

                    p["status"] = "approved"
                    p["executed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    p["result"] = "ok" if ok else "failed"
                    _atomic_write_json(BINGBU_PENDING, bpending)
                    return ok

    # ── Bingbu API 提案通道（IV- 前缀）──────────────────────────
    if alert_id.startswith("IV-"):
        BINGBU_PENDING = Path("/Users/luxiangnan/edict/data/bingbu_pending_proposals.json")
        if BINGBU_PENDING.exists():
            bpending = _json2.loads(BINGBU_PENDING.read_text())
            for p in bpending:
                if p.get("id") == alert_id and p.get("status") == "pending":
                    pair = p.get("details", {}).get("pair", "").split(":")[0] or ""
                    pair_clean = pair
                    action = p.get("action", "")
                    ok = False

                    if action in ("inject_long_pair", "inject_short_pair"):
                        target_close = "LONG" if action == "inject_short_pair" else "SHORT"
                        # ── 优先：精准定位持仓平仓 ──────────────────
                        target_port = p.get("details", {}).get("port", 0)
                        target_trade_id = p.get("details", {}).get("trade_id", "")
                        if target_port and target_trade_id:
                            has_conflict, exit_results = do_force_exit_by_trade_id(
                                target_port, target_trade_id)
                            if not has_conflict:
                                exit_results = [f"端口{target_port} trade_id={target_trade_id}: 未找到持仓（可能已平）"]
                        else:
                            has_conflict, exit_results = do_force_exit_by_direction(target_close)
                        inject_dir = "SHORT" if action == "inject_short_pair" else "LONG"
                        confidence = p.get("details", {}).get("confidence", 80)
                        reason = p.get("reason", f"兵部S/R扫描干预：{pair_clean} {inject_dir}")
                        write_inject_file(inject_dir, confidence, reason, pair_clean)
                        save_intervention(f"audit_{action}",
                                        f"审计提案执行：{pair_clean} {inject_dir}，"
                                        f"平仓结果：{' '.join(exit_results)}",
                                        {})
                        ok = True
                        feishu_to_bingbu("✅ 下单审计提案已执行",
                                         f"{alert_id} {action} {pair_clean} @ 端口{target_port}\n"
                                         f"Trade ID: `{target_trade_id}`\n"
                                         f"平仓：{' '.join(exit_results)}\n"
                                         f"信号注入：{inject_dir} @ 信心{confidence}",
                                         "INFO")

                    elif action == "force_exit_pair":
                        try:
                            sys.path.insert(0, "/Users/luxiangnan/edict/dashboard")
                            from monitor_sentiment import _do_force_exit_pair
                            r = _do_force_exit_pair(pair_clean)
                            ok = r.get("success", False)
                        except Exception as ex:
                            ok = False
                            print("[execute_approved_action] force_exit error: " + str(ex))
                        feishu_to_bingbu("✅ 下单审计提案已执行",
                                         f"{alert_id} force_exit {pair_clean} → {'成功' if ok else '失败'}",
                                         "INFO")

                    elif action == "emergency_exit_all":
                        try:
                            sys.path.insert(0, "/Users/luxiangnan/edict/dashboard")
                            from monitor_sentiment import _do_emergency_exit_all
                            r = _do_emergency_exit_all()
                            ok = r.get("success", False)
                        except Exception as ex:
                            ok = False
                            print("[execute_approved_action] emergency_exit_all error: " + str(ex))
                        feishu_to_bingbu("✅ 全市场双向强平已执行",
                                         f"{alert_id} emergency_exit_all\n{r.get('details', '')}",
                                         "P0")

                    elif action in ("freeze_pair", "freeze"):
                        level = p.get("details", {}).get("level", "L4")
                        try:
                            sys.path.insert(0, "/Users/luxiangnan/edict/dashboard")
                            from monitor_sentiment import _do_freeze
                            r = _do_freeze(pair_clean or None, level)
                            ok = r.get("success", False)
                        except Exception as ex:
                            ok = False
                            print("[execute_approved_action] freeze error: " + str(ex))
                        scope = f"{pair_clean}" if pair_clean else "全市场"
                        feishu_to_bingbu("✅ 冻结已执行",
                                         f"{alert_id} freeze {scope} [{level}]\n{r.get('details', '')}",
                                         "WARN")

                    elif action == "black_swan_freeze":
                        try:
                            has_conflict, exit_results = do_force_exit_by_direction("LONG")
                            _, exit_short = do_force_exit_by_direction("SHORT")
                            exit_results = (exit_results or []) + (exit_short or [])
                            do_freeze()
                            save_intervention("black_swan_freeze",
                                              f"黑天鹅冻结审批通过，全平+冻结",
                                              {})
                            ok = True
                        except Exception as ex:
                            ok = False
                            print("[execute_approved_action] black_swan_freeze error: " + str(ex))
                        feishu_to_bingbu("✅ 黑天鹅冻结已执行",
                                         f"{alert_id} black_swan_freeze\n{' '.join(exit_results or [])}",
                                         "P0")

                    else:
                        feishu_to_bingbu("⚠️ 未知动作类型",
                                         f"{alert_id} action={action}，跳过执行", "WARN")

                    p["status"] = "approved"
                    p["executed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    p["result"] = "ok" if ok else "failed"
                    _atomic_write_json(BINGBU_PENDING, bpending)
                    return ok

    return False


def reject_pending_action(alert_id: str) -> bool:
    """否决，支持黑天鹅(pending_approvals.json)和下单审计(bingbu_pending_proposals.json)两种通道"""
    # 黑天鹅通道
    pending = load_pending()
    for p in pending:
        if p.get("id") == alert_id and p.get("status") == "pending":
            p["status"] = "rejected"
            p["rejected_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_pending(pending)
            if p.get("type") == "black_swan":
                sig = p.get("sentiment", {})
                bs_cats_rej = sig.get("black_swan_categories", []) or sig.get("reasons", [])
                save_rejected_event(sig, bs_cats_rej)
            feishu_to_bingbu("❌ 审批否决",
                             f"告警ID={alert_id} 已否决，兵部不执行冻结", "WARN")
            return True
    # 下单审计通道(BS-OA-前缀)
    if alert_id.startswith("BS-OA-"):
        from pathlib import Path
        BINGBU_PENDING = Path("/Users/luxiangnan/edict/data/bingbu_pending_proposals.json")
        if BINGBU_PENDING.exists():
            import json as _json
            bpending = _json.loads(BINGBU_PENDING.read_text())
            for p in bpending:
                if p.get("id") == alert_id and p.get("status") == "pending":
                    p["status"] = "rejected"
                    p["rejected_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    _atomic_write_json(BINGBU_PENDING, bpending)
                    feishu_to_bingbu("❌ 下单审计提案已否决",
                                     f"{alert_id} 已否决，不执行平仓", "INFO")
                    return True
    return False


# ═══════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    args = sys.argv[1:]

    # 审批命令入口
    if len(args) == 2 and args[0] == "approve":
        ok = execute_approved_action(args[1])
        print(f"✅ 审批执行: {'成功' if ok else '失败'}")
        exit(0 if ok else 1)
    elif len(args) == 2 and args[0] == "reject":
        ok = reject_pending_action(args[1])
        print(f"✅ 已否决: {'成功' if ok else '未找到'}")
        exit(0 if ok else 1)

    # 正常监控
    force_mode = "--force" in args
    result = monitor_sentiment(force=force_mode)
    if result:
        for a in result:
            print(f"  [{a['level']}] {a['message']}")

# 别名函数（供 server.py 调用）
def approve_proposal(code: str, pair: str = "") -> dict:
    """批准干预提案（server.py 调用的别名）"""
    ok = execute_approved_action(code, pair)
    return {"ok": ok, "action": "approve", "code": code}


def reject_pending_action(alert_id: str) -> bool:
    """
    否决干预提案，支持两个通道：
    1. 黑天鹅审批（pending_approvals.json）
    2. 下单审计提案（bingbu_pending_proposals.json）
    否决后发通知到群里
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── 通道1：黑天鹅审批（pending_approvals.json）─────────────────
    pending = load_pending()
    for p in pending:
        if p.get("id") == alert_id and p.get("status") == "pending":
            p["status"] = "rejected"
            p["rejected_at"] = now_str
            save_pending(pending)

            sig = p.get("sentiment", {})
            fg = sig.get("fear_greed", 0)
            cats = sig.get("reasons", [])

            # 记录被否决事件（用于冷却期判断）
            save_rejected_event({"fear_greed_value": fg, "reasons": cats}, cats)

            # 发否决通知到汇报群
            feishu_to_bingbu("❌ 黑天鹅提案已否决",
                             f"告警ID={alert_id}，FG={fg}，已被否决（{now_str}）",
                             "WARN")
            return True

    # ── 通道2：下单审计提案（bingbu_pending_proposals.json）─────────
    if alert_id.startswith("BS-"):
        import json as _j2
        BINGBU_PENDING = Path("/Users/luxiangnan/edict/data/bingbu_pending_proposals.json")
        if BINGBU_PENDING.exists():
            bpending = _j2.loads(BINGBU_PENDING.read_text())
            for p in bpending:
                if p.get("id") == alert_id and p.get("status") == "pending":
                    p["status"] = "rejected"
                    p["rejected_at"] = now_str
                    _atomic_write_json(BINGBU_PENDING, bpending)

                    action = p.get("action", "")
                    pair = p.get("details", {}).get("pair", "全市场")

                    # 发否决通知到汇报群
                    feishu_to_bingbu("❌ 下单审计提案已否决",
                                     f"提案ID={alert_id}，动作={action}，交易对={pair}，已被否决（{now_str}）",
                                     "INFO")
                    return True

    return False


def reject_proposal(code: str) -> dict:
    """拒绝干预提案（server.py 调用的别名）"""
    ok = reject_pending_action(code)
    return {"ok": ok, "action": "reject", "code": code}
