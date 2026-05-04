#!/usr/bin/env python3
"""
兵部提案重发脚本
将指定提案重新发送到汇报群（使用正确的卡片格式+原生按钮）
"""
import sys
import json
import os
from pathlib import Path
from datetime import datetime as dt

# 添加scripts目录到路径
sys.path.insert(0, str(Path(__file__).parent))
import bingbu_card_builder as builder

EDICT_DATA = Path("/Users/luxiangnan/edict/data")
WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"
BASE_URL = "https://openclaw.tianlu2026.org"
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

def _send(card):
    """发送飞书卡片"""
    import urllib.request
    try:
        payload = json.dumps(card, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(WEBHOOK, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read())
            code = resp.get("StatusCode", -1)
            print(f"  飞书响应: StatusCode={code}")
            return code == 0
    except Exception as e:
        print(f"  飞书发送失败: {e}")
        return False

def resend_proposal(proposal):
    """将单个提案以正确格式发送到汇报群"""
    code    = proposal["id"]
    pair    = proposal.get("pair", "")
    action  = proposal.get("action", "")
    reason  = proposal.get("reason", "")
    details = proposal.get("details", {})
    now_str = dt.now().strftime("%Y-%m-%d %H:%M")

    # 确定方向
    if "long" in action:
        emoji, color = "📈", "green"
        type_label = "📈 入场做多提案"
        approve_text = "📈 批准执行做多"
    elif "short" in action:
        emoji, color = "📉", "orange"
        type_label = "📉 入场做空提案"
        approve_text = "📉 批准执行做空"
    else:
        emoji, color = "⚡", "red"
        type_label = "⚡ 干预提案"
        approve_text = "⚡ 批准执行"

    # 按钮URL（使用正确的 /bingbu/approve?code= 格式）
    approve_url = f"{BASE_URL}/bingbu/approve?code={code}"
    reject_url  = f"{BASE_URL}/bingbu/reject?code={code}"

    # body内容
    cur    = details.get("current_price", 0)
    sup    = details.get("support", 0)
    res    = details.get("resistance", 0)
    d2sup  = details.get("dist_to_support_pct", 0)
    d2res  = details.get("dist_to_resistance_pct", 0)
    t_sup  = details.get("support_touches", 0)
    t_res  = details.get("resistance_touches", 0)
    conf   = details.get("confidence", 80)
    sig_type = details.get("signal_type", "")

    # 尝试从details中提取bot信息
    port = details.get("port", 0)
    bot_label = BOT_LABELS.get(port, f"端口 {port}") if port else ""

    body_lines = [
        f"**交易对：** {pair}",
    ]
    if bot_label:
        body_lines.append(f"**📍 持仓机器人：** {bot_label}（端口 {port}）")
    body_lines += [
        f"**当前价：** ${cur:.4f}",
        f"**支撑位：** ${sup:.4f}（距{d2sup:.1f}%）| 触底{t_sup}次",
        f"**压力位：** ${res:.4f}（距{d2res:.1f}%）| 触顶{t_res}次",
        f"**置信度：** {conf}%",
        f"**信号类型：** {sig_type}",
    ]
    body_text = "\n".join(body_lines)

    # 构建卡片（使用统一构建器）
    card = builder.build_bingbu_card(
        action=action,
        proposal_id=code,
        pair=pair,
        reason=reason,
        approve_url=approve_url,
        reject_url=reject_url,
        body_text=body_text,
        expires_minutes=15,
        approve_text=approve_text,
    )

    # 覆盖header
    card["card"]["header"] = {
        "title": {"tag": "plain_text", "content": f"{type_label} · {now_str}"},
        "template": color,
    }

    print(f"发送提案 {code}: {pair} {action}")
    return _send(card)

def main():
    proposals_file = EDICT_DATA / "bingbu_pending_proposals.json"
    if not proposals_file.exists():
        print("❌ 提案文件不存在")
        return

    proposals = json.loads(proposals_file.read_text())

    # 只重发 pending 状态的指定提案
    target_ids = ["BS-OA-0328152447-99", "BS-OA-TEST-03281525"]

    # 先更新提案状态为pending（因为已expired）
    updated = False
    for p in proposals:
        if p["id"] in target_ids and p.get("status") in ("expired", "pending"):
            old_status = p.get("status")
            p["status"] = "pending"
            p["expires_at"] = (dt.now() + __import__("datetime").timedelta(minutes=15)).isoformat()
            print(f"  {p['id']}: {old_status} → pending")
            updated = True

    if updated:
        tmp = str(proposals_file) + ".tmp"
        Path(tmp).write_text(json.dumps(proposals, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, str(proposals_file))
        print("✅ 提案状态已更新")

    # 重新加载（状态已更新）
    proposals = json.loads(proposals_file.read_text())

    print("\n📤 开始发送卡片到汇报群...\n")
    for p in proposals:
        if p["id"] in target_ids and p.get("status") == "pending":
            ok = resend_proposal(p)
            print(f"  {'✅' if ok else '❌'} {p['id']}\n")

if __name__ == "__main__":
    main()
