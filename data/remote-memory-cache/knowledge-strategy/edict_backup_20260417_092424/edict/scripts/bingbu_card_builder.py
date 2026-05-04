#!/usr/bin/env python3
"""
兵部统一飞书卡片构建器
所有审批卡片统一格式：
  1. 卡片Header - 彩色标题
  2. 醒目审批区 - note背景标签 + 三行按钮（每按钮独立一行）
  3. 提案信息块 - 动作/交易对/原因/提案ID
  4. 卡片Body - 详情内容
"""

import json
from datetime import datetime as dt, timedelta as td
from typing import Optional

# ── 颜色映射 ───────────────────────────────────────────
_ACTION_EMOJI = {
    "inject_long_pair":   "📈",
    "inject_short_pair": "📉",
    "force_exit_pair":   "🔴",
    "emergency_exit_all": "🚨",
    "freeze_pair":       "❄️",
    "freeze":           "❄️",
    "black_swan_freeze": "🚨",
}

_ACTION_LABEL = {
    "inject_long_pair":   "注入做多信号",
    "inject_short_pair":  "注入做空信号",
    "force_exit_pair":    "强制平仓",
    "emergency_exit_all": "全市场双向强平",
    "freeze_pair":        "冻结指定交易对",
    "freeze":            "全市场冻结",
    "black_swan_freeze": "黑天鹅紧急接管",
}

_PROPOSAL_TYPE_LABEL = {
    "inject_long_pair":   "📈 入场信号提案",
    "inject_short_pair":  "📉 入场信号提案",
    "force_exit_pair":    "🔴 平仓提案",
    "emergency_exit_all": "🚨 紧急平仓提案",
    "freeze_pair":        "❄️ 冻结提案",
    "freeze":            "❄️ 全市场冻结提案",
    "black_swan_freeze": "🚨 黑天鹅提案",
    # 兜底
    "sr_guard_long":      "📈 S/R方向守卫",
    "sr_guard_short":     "📉 S/R方向守卫",
}

# Header颜色
_HEADER_COLOR = {
    "inject_long_pair":   "green",
    "inject_short_pair":  "orange",
    "force_exit_pair":    "red",
    "emergency_exit_all": "red",
    "freeze_pair":        "blue",
    "freeze":            "blue",
    "black_swan_freeze": "red",
}

# note背景色（按动作类型区分醒目程度）
# 每按钮独立底色：与标题Header颜色100%同步
_ACTION_BG = {
    "inject_long_pair":   "#2E7D32",   # 深绿（标题green）
    "inject_short_pair":  "#E65100",   # 深橙（标题orange）
    "force_exit_pair":   "#C62828",   # 深红（标题red）
    "emergency_exit_all": "#B71C1C",   # 暗红（标题red）
    "freeze_pair":        "#1565C0",   # 深蓝（标题blue）
    "freeze":            "#1565C0",
    "black_swan_freeze": "#B71C1C",
}
_REJECT_BG = "#C62828"   # 否决：深红（所有场景统一）
_THIRD_BG  = "#6A1B9A"   # 第三按钮：紫色

# 浅色背景用于 note 标签（飞书note元素支持的颜色上限）
_ACTION_BG_LIGHT = {
    "inject_long_pair":   "#E8F5E9",
    "inject_short_pair":  "#FFF3E0",
    "force_exit_pair":    "#FFEBEE",
    "emergency_exit_all": "#FFEBEE",
    "freeze_pair":        "#E3F2FD",
    "freeze":            "#E3F2FD",
    "black_swan_freeze":  "#FFEBEE",
}
_REJECT_BG_LIGHT = "#FFEBEE"
_THIRD_BG_LIGHT  = "#F3E5F5"


def _header_color(action: str) -> str:
    return _HEADER_COLOR.get(action, "red")


def _note_bg(action: str) -> str:
    return _ACTION_BG_LIGHT.get(action, "#F5F5F5")

def _btn_bg(action: str) -> str:
    """批准按钮底色：与标题颜色100%同步"""
    return _ACTION_BG.get(action, "#C62828")

def _reject_bg() -> str:
    """否决按钮底色：统一深红"""
    return _REJECT_BG

def _third_bg() -> str:
    """第三按钮底色：紫色"""
    return _THIRD_BG


def build_bingbu_card(
    action: str,
    proposal_id: str,
    pair: str,
    reason: str,
    approve_url: str,
    reject_url: str,
    body_text: str = "",
    expires_minutes: int = 15,
    extra_info: dict = None,
    send_to_shangshu: bool = False,
    third_button_text: str = "",
    third_button_url: str = "",
    third_button_type: str = "danger",
    approve_text: str = "",
) -> dict:
    """
    统一格式审批卡片（醒目按钮区，无URL文字泄露）

    参数:
        action            - 动作类型
        proposal_id       - 提案ID
        pair              - 交易对
        reason            - 原因
        approve_url       - 批准URL
        reject_url        - 拒绝URL
        body_text         - 卡片body内容
        expires_minutes   - 有效期
        extra_info        - 额外信息
        send_to_shangshu  - True=尚书省，False=兵部
        third_button_text  - 第三个按钮文字（如"仅平仓"）
        third_button_url   - 第三个按钮URL
        third_button_type  - 第三个按钮颜色（primary/danger/secondary）
        approve_text      - 自定义批准按钮文案（空则用默认emoji+动作）
    """
    now_str = dt.now().strftime("%Y-%m-%d %H:%M")
    expires = dt.now() + td(minutes=expires_minutes)
    expires_str = expires.strftime("%H:%M")

    color = _header_color(action)
    emoji = _ACTION_EMOJI.get(action, "⚡")
    type_label = _PROPOSAL_TYPE_LABEL.get(action, f"{emoji} 干预提案")
    note_bg = _note_bg(action)

    # ── 提案信息区 ───────────────────────────────────────
    pair_line = f"**交易对：** `{pair}`" if pair else ""
    action_label = _ACTION_LABEL.get(action, action)
    info_lines = [
        f"**动作：** {emoji} {action_label}",
        pair_line,
        f"**原因：** {reason}",
        f"**提案ID：** `{proposal_id}`",
        f"**有效期：** {expires_str} 前审批",
    ]
    if extra_info:
        for k, v in extra_info.items():
            if v:
                info_lines.append(f"**{k}：** {v}")
    info_block = "\n".join(line for line in info_lines if line)

    # ── 醒目审批按钮区 ──────────────────────────────────
    # 按钮用 action 容器 + 原生 button 组件，支持颜色+大字体+高识别度
    approve_label = approve_text or "批准执行"
    reject_label  = "否决此提案"
    third_label   = third_button_text or ""

    # 原生按钮 type: primary(蓝)/danger(红)/secondary(灰)
    # 批准按钮颜色与动作类型同步
    _APPROVE_BTN_TYPE = {
        "inject_long_pair":    "primary",   # 蓝色
        "inject_short_pair":   "warning",   # 橙色
        "force_exit_pair":    "danger",    # 红色
        "emergency_exit_all":  "danger",    # 红色
        "freeze_pair":        "primary",   # 蓝色
        "freeze":             "primary",   # 蓝色
        "black_swan_freeze":  "danger",    # 红色
    }.get(action, "primary")

    # 构造按钮列表
    _btn_url_map = {
        "inject_long_pair":   ("📈 " + approve_label, approve_url),
        "inject_short_pair":  ("📉 " + approve_label, approve_url),
        "force_exit_pair":    ("🔴 " + approve_label, approve_url),
        "emergency_exit_all":  ("🚨 " + approve_label, approve_url),
        "freeze_pair":        ("❄️ " + approve_label, approve_url),
        "freeze":             ("❄️ " + approve_label, approve_url),
        "black_swan_freeze":  ("🚨 " + approve_label, approve_url),
    }
    _reject_btn_url = ("❌ " + reject_label, reject_url)

    btn_actions = []

    # 批准按钮
    _a_text, _a_url = _btn_url_map.get(action, (approve_label, approve_url))
    btn_actions.append({
        "tag": "button",
        "text": {"tag": "plain_text", "content": _a_text},
        "type": _APPROVE_BTN_TYPE,
        "url": _a_url,
    })

    # 第三按钮（如有）
    if third_button_text and third_button_url:
        btn_actions.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": "⚡ " + third_label},
            "type": third_button_type or "secondary",
            "url": third_button_url,
        })

    # 否决按钮
    btn_actions.append({
        "tag": "button",
        "text": {"tag": "plain_text", "content": _reject_btn_url[0]},
        "type": "danger",
        "url": _reject_btn_url[1],
    })

    elements = [
        # ① 操作区标题
        {"tag": "div", "text": {"tag": "lark_md", "content": "**【审批操作】请在以下按钮中选择**"}},
        {"tag": "hr"},
        # ② 原生按钮组（action容器，视觉冲击力强）
        {"tag": "action", "actions": btn_actions},
        {"tag": "hr"},
        # ③ 提案信息
        {"tag": "div", "text": {"tag": "lark_md", "content": info_block}},
    ]

    if body_text:
        elements.append({"tag": "hr"})
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": body_text}})

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"{type_label} · {now_str}"},
                "template": color,
            },
            "elements": elements,
        }
    }
    return card


def send_bingbu_card(card: dict, webhook: str = None, to_shangshu: bool = False) -> bool:
    """发送飞书卡片（统一发到天禄量化交易汇报群，不走代理）"""
    REPORT_GROUP = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"
    if webhook is None:
        webhook = REPORT_GROUP
    try:
        import requests, urllib3
        urllib3.disable_warnings()
        session = requests.Session()
        session.trust_env = False  # 禁用环境变量代理
        r = session.post(webhook, json=card, timeout=10, verify=False)
        if r.status_code == 200:
            resp = r.json()
            return resp.get("StatusCode", -1) == 0
        return False
    except Exception as e:
        print(f"[build_bingbu_card] 飞书发送失败: {e}")
        return False
