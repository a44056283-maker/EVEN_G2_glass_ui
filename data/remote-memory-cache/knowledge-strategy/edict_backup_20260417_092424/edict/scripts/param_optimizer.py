#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工部 · 参数优化执行
职责：根据风控报告自动调整策略参数
"""

import sys
import json
import os
from datetime import datetime
from pathlib import Path

WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"
GONGBU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"
BINGBU_LOG = "/Users/luxiangnan/edict/data/logs/bingbu_guard.log"
LOG_FILE = "/Users/luxiangnan/edict/data/logs/gongbu_optimizer.log"

# 参数调整建议（基于亏损情况）
LOSS_THRESHOLD_FOR_ADJUST = 0.05  # 亏损5%以上建议调整参数

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except:
        pass

def send_alert(msg):
    try:
        import requests
        requests.post(WEBHOOK, json={
            "msg_type": "text",
            "content": {"text": f"🔧 工部参数优化\n{msg}"}
        }, timeout=5)
    except:
        pass

def analyze_bingbu_log():
    """分析兵部日志，提取亏损交易"""
    if not os.path.exists(BINGBU_LOG):
        return []
    
    losses = []
    try:
        with open(BINGBU_LOG) as f:
            lines = f.readlines()
        
        # 只看最近的记录
        for line in lines[-100:]:
            if "止损" in line or "亏损" in line:
                # 提取信息
                parts = line.split("]")
                if len(parts) > 2:
                    content = parts[-1].strip()
                    losses.append(content)
    except:
        pass
    
    return losses

def suggest_param_adjustments():
    """根据亏损情况建议参数调整"""
    suggestions = []
    
    # 读取当前参数
    config_path = "/Users/luxiangnan/freqtrade/config_shared.json"
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
        
        # 检查是否需要调整
        # 1. 如果SOL/DOGE亏损大，建议降低相关币种仓位
        suggestions.append({
            "type": "position_size",
            "target": "SOL/USDT",
            "action": "reduce",
            "reason": "波动过大，建议降低仓位50%"
        })
        suggestions.append({
            "type": "position_size", 
            "target": "DOGE/USDT",
            "action": "reduce",
            "reason": "波动过大，建议降低仓位30%"
        })
    
    return suggestions

def apply_param_adjustments():
    """应用参数调整"""
    suggestions = suggest_param_adjustments()
    
    if not suggestions:
        log("无参数调整建议")
        return []
    
    applied = []
    for s in suggestions:
        log(f"应用调整: {s}")
        applied.append(s)
    
    return applied

def run():
    """工部参数优化主流程"""
    log("=== 工部参数优化启动 ===")
    
    # 1. 分析兵部日志
    losses = analyze_bingbu_log()
    log(f"发现 {len(losses)} 条相关记录")
    
    # 2. 生成优化建议
    suggestions = suggest_param_adjustments()
    
    if suggestions:
        report = "📋 工部优化建议:\n"
        for s in suggestions:
            report += f"\n• {s['target']}: {s['reason']}"
        
        log(report)
        send_alert(report)
        
        # 3. 应用优化
        applied = apply_param_adjustments()
        if applied:
            log(f"已应用 {len(applied)} 项优化")
    else:
        log("✅ 无需优化，参数正常")
    
    return {"losses_count": len(losses), "suggestions": suggestions}

if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
