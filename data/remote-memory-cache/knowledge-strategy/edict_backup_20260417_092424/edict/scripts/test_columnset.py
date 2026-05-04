#!/usr/bin/env python3
"""column_set 按钮布局测试"""
import json, urllib.request

WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"

def send(card):
    payload = json.dumps(card, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(WEBHOOK, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

# column_set 等宽三按钮测试
card = {
    "msg_type": "interactive",
    "card": {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "🧪 column_set 按钮布局测试 · 2026-03-28"},
            "template": "red",
        },
        "elements": [
            # 操作区标题
            {"tag": "div", "text": {"tag": "lark_md", "content": "**【审批操作】请在以下按钮中选择**"}},
            {"tag": "hr"},
            # 三按钮并排（模拟巡查卡片：解冻/冻结提案/状态查询）
            {
                "tag": "column_set",
                "flex_mode": "weighted",
                "elements": [
                    {
                        "tag": "column",
                        "background": "#1565C0",  # 蓝色-解冻
                        "width": "stretch",
                        "elements": [{"tag": "lark_md", "content": "**🔓 [直接解冻](https://example.com)**"}],
                    },
                    {
                        "tag": "column",
                        "background": "#E65100",  # 橙色-冻结提案
                        "width": "stretch",
                        "elements": [{"tag": "lark_md", "content": "**🔒 [提交冻结提案](https://example.com)**"}],
                    },
                    {
                        "tag": "column",
                        "background": "#2E7D32",  # 绿色-状态查询
                        "width": "stretch",
                        "elements": [{"tag": "lark_md", "content": "**📊 [状态查询](https://example.com)**"}],
                    },
                ],
            },
            {"tag": "hr"},
            # 提案信息
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": (
                    "**动作：** ❄️ 全市场冻结\n"
                    "**原因：** 测试按钮背景色\n"
                    "**提案ID：** `TEST-20260328-001`"
                )},
            },
            {"tag": "hr"},
            # 批准/否决 双按钮（模拟提案卡片）
            {"tag": "div", "text": {"tag": "lark_md", "content": "**【提案审批】**"}},
            {
                "tag": "column_set",
                "flex_mode": "weighted",
                "elements": [
                    {
                        "tag": "column",
                        "background": "#C62828",
                        "width": "stretch",
                        "elements": [{"tag": "lark_md", "content": "**✅ [批准执行](https://example.com)**"}],
                    },
                    {
                        "tag": "column",
                        "background": "#B71C1C",
                        "width": "stretch",
                        "elements": [{"tag": "lark_md", "content": "**❌ [否决此提案](https://example.com)**"}],
                    },
                ],
            },
        ],
    },
}

result = send(card)
code = result.get("StatusCode", -1)
print(f"{'✅' if code == 0 else '❌'} column_set按钮测试: code={code}")
