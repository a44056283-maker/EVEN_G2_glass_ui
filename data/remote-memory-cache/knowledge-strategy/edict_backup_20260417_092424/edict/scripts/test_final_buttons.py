#!/usr/bin/env python3
"""用bingbu_card_builder发送测试卡片"""
import sys
sys.path.insert(0, "/Users/luxiangnan/edict/scripts")
from bingbu_card_builder import build_bingbu_card, send_bingbu_card

# 测试：冻结提案
card = build_bingbu_card(
    action="freeze",
    proposal_id="TEST-20260328-001",
    pair="全市场",
    reason="测试按钮UI效果",
    approve_url="https://example.com/approve",
    reject_url="https://example.com/reject",
    body_text="这是测试卡片，验证原生button组件是否正常渲染。",
    expires_minutes=15,
    extra_info={"提交方": "兵部巡查", "优先级": "高"},
)
ok = send_bingbu_card(card)
print(f"{'✅' if ok else '❌'} 冻结提案卡片: {'成功' if ok else '失败'}")
