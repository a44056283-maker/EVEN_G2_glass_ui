#!/usr/bin/env python3
"""测试飞书div背景色渲染 - 看div是否支持background"""
import json, urllib.request

WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"

def send(card):
    payload = json.dumps(card, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(WEBHOOK, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

# Feishu card elements that support "background" field:
# note, div, column_set, column, table, td

# Test: div with background - does it work?
card_div = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "Test DIV背景色"}, "template": "red"},
        "elements": [
            # div with background color + bold lark_md
            {
                "tag": "div",
                "background": "#C62828",
                "text": {
                    "tag": "lark_md",
                    "content": "**✅ [批准执行](https://example.com)**"
                }
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "Is this div background visible? (should be dark red)"
                }
            },
        ]
    }
}

# Test: div with light background
card_div_light = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "Test DIV浅色背景"}, "template": "red"},
        "elements": [
            {
                "tag": "div",
                "background": "#FFCDD2",
                "text": {
                    "tag": "lark_md",
                    "content": "**✅ [批准执行](https://example.com)** - light red bg"
                }
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "Is this light red div background visible?"
                }
            },
        ]
    }
}

# Test: div with named color background
card_div_named = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "Test DIV named color bg"}, "template": "red"},
        "elements": [
            {
                "tag": "div",
                "background": "red",
                "text": {
                    "tag": "lark_md",
                    "content": "**✅ [批准执行](https://example.com)** - named red bg"
                }
            },
            {"tag": "hr"},
        ]
    }
}

# Test: note with plain text (no bold) + dark hex
card_note_plain = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "Test NOTE plain text no bold"}, "template": "red"},
        "elements": [
            {
                "tag": "note",
                "background": "#C62828",
                "elements": [{"tag": "plain_text", "content": "Plain text no markdown"}]
            },
            {"tag": "hr"},
            {
                "tag": "note",
                "background": "#FFCDD2",
                "elements": [{"tag": "plain_text", "content": "Light red plain text"}]
            },
        ]
    }
}

# Test: full button card with note elements
card_note_full = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "Test NOTE完整按钮卡片"}, "template": "red"},
        "elements": [
            {"tag": "note", "background": "#E3F2FD",
             "elements": [{"tag": "lark_md", "content": "【审批操作】请在以下按钮中选择"}]},
            {"tag": "note", "background": "#C62828",
             "elements": [{"tag": "lark_md", "content": "**✅ [批准执行](https://example.com)**"}]},
            {"tag": "note", "background": "#B71C1C",
             "elements": [{"tag": "lark_md", "content": "**❌ [否决此提案](https://example.com)**"}]},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": "查看note背景色是否渲染"}},
        ]
    }
}

# Test: button using column_set for more prominent display
card_colset = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "Test column_set button area"}, "template": "red"},
        "elements": [
            {"tag": "note", "background": "#E3F2FD",
             "elements": [{"tag": "lark_md", "content": "【审批操作】请在以下按钮中选择"}]},
            {
                "tag": "column_set",
                "flex_mode": "one_third",
                "elements": [
                    {
                        "tag": "column",
                        "background": "#C62828",
                        "width": "stretch",
                        "elements": [{"tag": "lark_md", "content": "**✅ [批准](https://example.com)**"}]
                    },
                    {
                        "tag": "column",
                        "background": "#B71C1C",
                        "width": "stretch",
                        "elements": [{"tag": "lark_md", "content": "**❌ [否决](https://example.com)**"}]
                    },
                ]
            },
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": "column_set background test"}},
        ]
    }
}

tests = [
    ("DIV dark bg", card_div),
    ("DIV light bg", card_div_light),
    ("DIV named bg", card_div_named),
    ("NOTE plain text", card_note_plain),
    ("NOTE full buttons", card_note_full),
    ("COLUMN_SET buttons", card_colset),
]

for name, card in tests:
    result = send(card)
    code = result.get("StatusCode", -1)
    print(f"{name}: {'✅' if code == 0 else '❌'} code={code}")
