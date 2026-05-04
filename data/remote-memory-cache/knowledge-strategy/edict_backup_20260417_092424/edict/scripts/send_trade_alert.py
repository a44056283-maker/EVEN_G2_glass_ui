#!/usr/bin/env python3
"""
兵部 · 交易告警发送脚本
对接钉钉/飞书webhook，支持P0-P2分级告警
"""

import json
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [ALERT] %(message)s')
log = logging.getLogger('alert')

# ---------- 告警配置（可注入环境变量）----------
DINGTALK_WEBHOOK = "${DINGTALK_WEBHOOK}"
FEISHU_WEBHOOK = "${FEISHU_WEBHOOK}"
ALERT_LOG = Path(__file__).parent.parent / 'data' / 'logs' / 'sent_alerts.jsonl'
ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)


def send_dingtalk(level: str, title: str, message: str, alerts: list = None) -> bool:
    """发送钉钉告警"""
    webhook = DINGTALK_WEBHOOK
    if not webhook or "${" in webhook:
        log.info(f"钉钉Webhook未配置，跳过: {title}")
        return False

    try:
        import urllib.request
        emoji_map = {"P0": "🔴", "P1": "🚨", "P2": "🟠", "OK": "✅"}
        emoji = emoji_map.get(level, "ℹ️")

        content = f"{emoji} **{title}**\n{message}"
        if alerts:
            content += "\n\n📋 告警详情:"
            for a in alerts:
                content += f"\n• {a.get('message', str(a))}"

        payload = json.dumps({
            "msgtype": "text",
            "text": {"content": content}
        }).encode('utf-8')

        req = urllib.request.Request(
            webhook,
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                log.info(f"钉钉告警已发送: {title}")
                return True
    except Exception as e:
        log.warning(f"钉钉发送失败: {e}")
    return False


def send_feishu(level: str, title: str, message: str) -> bool:
    """发送飞书告警"""
    webhook = FEISHU_WEBHOOK
    if not webhook or "${" in webhook:
        return False

    try:
        import urllib.request
        payload = json.dumps({
            "msg_type": "text",
            "content": {"text": f"[{level}] {title}: {message}"}
        }).encode('utf-8')

        req = urllib.request.Request(
            webhook,
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                log.info(f"飞书告警已发送: {title}")
                return True
    except Exception as e:
        log.warning(f"飞书发送失败: {e}")
    return False


def send_alert(level: str, title: str, message: str, alerts: list = None):
    """统一告警入口：钉钉 + 飞书 + 日志"""
    # 保存到日志
    entry = {"level": level, "title": title, "message": message, "alerts": alerts or []}
    with open(ALERT_LOG, 'a') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    # 发送
    sent = send_dingtalk(level, title, message, alerts)
    sent = send_feishu(level, title, message) or sent
    return sent


def main():
    if len(sys.argv) < 3:
        print("用法: send_trade_alert.py <P0|P1|P2> <标题> <消息>")
        sys.exit(1)

    level = sys.argv[1]
    title = sys.argv[2]
    message = sys.argv[3]

    send_alert(level, title, message)


if __name__ == '__main__':
    main()
