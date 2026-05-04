#!/usr/bin/env python3
import json, urllib.request

SHANGSHU = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"
BASE_URL = "https://openclaw.tianlu2026.org"
EDICT_API = "http://127.0.0.1:7891"

def api_post(path, payload):
    req = urllib.request.Request(
        EDICT_API + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def send(task_id, title, from_dept, to_dept, proposal_title, detail):
    # 1. 先注册任务到 edict 数据库，让审批按钮能正确回调
    try:
        api_post('/api/register-review-task', {
            'taskId': task_id,
            'title': title,
            'fromDept': from_dept,
            'proposalTitle': proposal_title,
            'detail': detail,
        })
    except Exception as e:
        print(f"⚠️ 任务注册失败: {e}")

    # 2. 发送飞书卡片
    card = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"📋 {title}"},
                "subtitle": {"tag": "plain_text", "content": f"📤 {from_dept} → {to_dept}"},
                "template": "blue"
            },
            "elements": [
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**📝 提案：** {proposal_title}\n\n**📄 内容：**\n{detail}"
                    }
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**🆔 任务：** `{task_id}`"
                    }
                },
                {"tag": "hr"},
                {"tag": "div", "text": {"tag": "lark_md", "content": "**【操作审批】请在以下按钮中选择**"}},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "✅ 批准"},
                            "type": "primary",
                            "url": f"{BASE_URL}/api/review-action?taskId={task_id}&action=approve",
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "📝 修改意见"},
                            "type": "warning",
                            "url": f"{BASE_URL}/api/review-action?taskId={task_id}&action=modify",
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "❌ 拒绝"},
                            "type": "danger",
                            "url": f"{BASE_URL}/api/review-action?taskId={task_id}&action=reject",
                        },
                    ],
                },
            ]
        }
    }
    req = urllib.request.Request(
        SHANGSHU,
        data=json.dumps(card).encode(),
        headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req, timeout=10)
    print(f"已发送: {task_id}")

if __name__ == "__main__":
    send("ZZ-20260326-007", "【门下省】新任务", "中书省", "门下省", "V6.5参数优化", "• 当前:1.5→建议:1.3")
