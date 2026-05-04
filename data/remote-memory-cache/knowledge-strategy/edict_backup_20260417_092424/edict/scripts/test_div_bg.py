#!/usr/bin/env python3
"""测试飞书div背景色渲染"""
import json, urllib.request

WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"

def send(card):
    payload = json.dumps(card, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(WEBHOOK, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

# Test 1: div with background + 链接
card1 = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "Test1 - div背景+链接"}, "template": "red"},
        "elements": [
            {
                "tag": "div",
                "background": "#C62828",
                "text": {"tag": "lark_md", "content": "**✅ [批准执行](https://example.com)**"}
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": "上面的div背景是深红色吗?"}
            },
        ]
    }
}

# Test 2: div with named color background
card2 = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "Test2 - div背景named color"}, "template": "red"},
        "elements": [
            {
                "tag": "div",
                "background": "red",
                "text": {"tag": "lark_md", "content": "**✅ 批准执行** - named red bg"}
            },
            {"tag": "hr"},
        ]
    }
}

# Test 3: div with light hex background
card3 = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "Test3 - div浅色背景"}, "template": "red"},
        "elements": [
            {
                "tag": "div",
                "background": "#FFCDD2",
                "text": {"tag": "lark_md", "content": "**✅ 批准执行** - 浅红色背景可见吗?"}
            },
            {"tag": "hr"},
        ]
    }
}

# Test 4: div with background + plain_text tag (no markdown)
card4 = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "Test4 - div背景+plain_text"}, "template": "red"},
        "elements": [
            {
                "tag": "div",
                "background": "#C62828",
                "text": {"tag": "plain_text", "content": "✅ 批准执行 plain text"}
            },
            {"tag": "hr"},
        ]
    }
}

# Test 5: button component (飞书原生按钮)
card5 = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "Test5 - 原生button组件"}, "template": "red"},
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": "原生按钮组件测试:"}
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "✅ 批准执行"},
                        "type": "primary",
                        "url": "https://example.com"
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "❌ 否决"},
                        "type": "danger",
                        "url": "https://example.com"
                    },
                ]
            },
            {"tag": "hr"},
        ]
    }
}

# Test 6: button with text + div background
card6 = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "Test6 - button+div背景"}, "template": "red"},
        "elements": [
            {
                "tag": "div",
                "background": "#C62828",
                "text": {"tag": "lark_md", "content": "深红背景div + 按钮:"}
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "✅ 批准执行"},
                        "type": "primary",
                        "url": "https://example.com"
                    },
                ]
            },
            {"tag": "hr"},
        ]
    }
}

# Test 7: 完整卡片 - div背景按钮 + 原生button混合
card7 = {
    "msg_type": "interactive",
    "card": {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "Test7 - 完整审批卡片测试 · 2026-03-28"},
            "template": "red",
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": "**【审批操作】请在以下按钮中选择**"}},
            {"tag": "hr"},
            # 方案A: div背景色按钮
            {
                "tag": "div",
                "background": "#C62828",
                "text": {"tag": "lark_md", "content": "**✅ [批准执行](https://example.com)**"}
            },
            {"tag": "hr"},
            # 方案B: 原生button
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "✅ 批准执行 (原生按钮)"},
                        "type": "primary",
                        "url": "https://example.com"
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "❌ 否决 (原生按钮)"},
                        "type": "danger",
                        "url": "https://example.com"
                    },
                ]
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": (
                    "**动作：** ❄️ 全市场冻结\n"
                    "**原因：** 测试背景色渲染\n"
                    "**提案ID：** `TEST-20260328-002`"
                )},
            },
        ],
    },
}

tests = [
    ("div+bg+链接", card1),
    ("div+named颜色", card2),
    ("div+浅色背景", card3),
    ("div+plain_text", card4),
    ("原生button组件", card5),
    ("div背景+button混合", card6),
    ("完整审批卡片7", card7),
]

for name, card in tests:
    result = send(card)
    code = result.get("StatusCode", -1)
    print(f"{'✅' if code == 0 else '❌'} {name}: code={code}")
