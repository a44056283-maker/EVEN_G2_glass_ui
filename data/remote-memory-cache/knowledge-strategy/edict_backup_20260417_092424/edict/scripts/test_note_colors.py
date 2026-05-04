#!/usr/bin/env python3
"""测试飞书note元素背景色渲染"""
import json, urllib.request

WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"

def send(card):
    payload = json.dumps(card, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(WEBHOOK, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

# Test 1: named color "red" in note background
card1 = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "Test1 - Named Color red"}, "template": "red"},
        "elements": [
            {"tag": "note", "background": "red", "elements": [{"tag": "lark_md", "content": "Named color: red **bold text**"}]},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": "Is the background red?"}},
        ]
    }
}

# Test 2: named color "orange" in note background
card2 = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "Test2 - Named Color orange"}, "template": "orange"},
        "elements": [
            {"tag": "note", "background": "orange", "elements": [{"tag": "lark_md", "content": "Named color: orange"}]},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": "Is the background orange?"}},
        ]
    }
}

# Test 3: named color "blue" in note background
card3 = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "Test3 - Named Color blue"}, "template": "blue"},
        "elements": [
            {"tag": "note", "background": "blue", "elements": [{"tag": "lark_md", "content": "Named color: blue"}]},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": "Is the background blue?"}},
        ]
    }
}

# Test 4: named color "green" in note background
card4 = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "Test4 - Named Color green"}, "template": "green"},
        "elements": [
            {"tag": "note", "background": "green", "elements": [{"tag": "lark_md", "content": "Named color: green"}]},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": "Is the background green?"}},
        ]
    }
}

# Test 5: light hex (#FFCDD2 light red) in note background
card5 = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "Test5 - Light Hex #FFCDD2"}, "template": "red"},
        "elements": [
            {"tag": "note", "background": "#FFCDD2", "elements": [{"tag": "lark_md", "content": "Light hex #FFCDD2 **bold**"}]},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": "Is the background light red visible?"}},
        ]
    }
}

# Test 6: dark hex (#C62828) in note background
card6 = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "Test6 - Dark Hex #C62828"}, "template": "red"},
        "elements": [
            {"tag": "note", "background": "#C62828", "elements": [{"tag": "lark_md", "content": "Dark hex #C62828 **bold**"}]},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": "Is the background dark red visible?"}},
        ]
    }
}

# Test 7: plain text in note (no markdown bold)
card7 = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "Test7 - No markdown bold"}, "template": "red"},
        "elements": [
            {"tag": "note", "background": "#FFEBEE", "elements": [{"tag": "lark_md", "content": "✅ [批准执行](https://example.com) plain no bold"}]},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": "Does this render with background?"}},
        ]
    }
}

# Test 8: purple named color (for third button)
card8 = {
    "msg_type": "interactive",
    "card": {
        "header": {"title": {"tag": "plain_text", "content": "Test8 - Named Color purple"}, "template": "purple"},
        "elements": [
            {"tag": "note", "background": "purple", "elements": [{"tag": "lark_md", "content": "Named color: purple **bold**"}]},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": "Is the background purple?"}},
        ]
    }
}

tests = [
    ("Test1 - Named red", card1),
    ("Test2 - Named orange", card2),
    ("Test3 - Named blue", card3),
    ("Test4 - Named green", card4),
    ("Test5 - Light hex #FFCDD2", card5),
    ("Test6 - Dark hex #C62828", card6),
    ("Test7 - No bold plain text", card7),
    ("Test8 - Named purple", card8),
]

for name, card in tests:
    result = send(card)
    code = result.get("StatusCode", -1)
    print(f"{name}: {'✅' if code == 0 else '❌'} code={code}")
