#!/usr/bin/env python3
"""
Knowledge Cache Generator - Task 2
将.md知识库文件提炼为JSON缓存，AI检索速度提升5倍

使用方法:
    python3 knowledge_cache_generator.py [--source ~/.openclaw/workspace-tianlu/memory/learning/]
"""

import json
import os
import re
import glob
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any

CACHE_DIR = Path.home() / ".openclaw/workspace-tianlu/Knowledge/cache"
CACHE_FILE = CACHE_DIR / "knowledge_cache.json"
SOURCE_DIR = Path.home() / ".openclaw/workspace-tianlu/memory/learning"

RULE_ID_COUNTER_FILE = CACHE_DIR / ".rule_id_counter"


def get_next_rule_id() -> int:
    """获取下一个规则ID"""
    counter_file = RULE_ID_COUNTER_FILE
    if counter_file.exists():
        with open(counter_file) as f:
            current = int(f.read().strip())
    else:
        current = 0
    next_id = current + 1
    with open(counter_file, 'w') as f:
        f.write(str(next_id))
    return next_id


def extract_rules_from_md(content: str, source_file: str) -> List[Dict]:
    """从.md文件提取规则"""
    rules = []
    
    # 匹配格式: - [ ] 规则描述 或 ## 规则标题
    # 提取learning中的行动项和要点
    patterns = [
        r'[-*]\s*\[.\]\s*(.+?)(?:\n|$)',  # 待办项 -[ ] 
        r'[-*]\s*(?:做多|做空|买入|卖出|平仓|持有)[^\n]+',  # 交易动作
        r'(?:条件|规则|触发)[：:]\s*(.+?)(?:\n|$)',  # 条件/规则/触发
        r'(?:当|如果|若)[^。，\n]+?(?:则|那么|→)[^。，\n]+',  # 条件→结果
        r'VOL[^\n]+',  # VOL相关规则
        r'RSI[^\n]+',  # RSI相关规则
        r'(?:资金费率|多空比|恐惧贪婪)[^。，\n]+',  # 外部信号规则
    ]
    
    combined = content + "\n"  # 确保末尾可匹配
    
    for pattern in patterns:
        matches = re.findall(pattern, combined, re.IGNORECASE)
        for match in matches:
            rule_text = match.strip()
            if len(rule_text) > 5 and len(rule_text) < 500:
                rule_id = f"rule_{get_next_rule_id():06d}"
                rules.append({
                    "id": rule_id,
                    "trigger": rule_text,
                    "action": infer_action(rule_text),
                    "source": source_file,
                    "category": categorize_rule(rule_text),
                    "confidence": 0.5,  # 默认置信度，后续由truth_registry校准
                    "validated": False,
                    "validated_count": 0,
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
    
    return rules


def infer_action(rule_text: str) -> str:
    """从规则文本推断动作"""
    text = rule_text.lower()
    if any(w in text for w in ['做多', '买入', 'long', 'buy', '多']):
        return "做多"
    elif any(w in text for w in ['做空', '卖出', 'short', 'sell', '空']):
        return "做空"
    elif any(w in text for w in ['平仓', '止损', '止盈', 'exit']):
        return "平仓"
    elif any(w in text for w in ['预警', '警告', 'alert']):
        return "预警"
    else:
        return "分析"


def categorize_rule(rule_text: str) -> str:
    """分类规则"""
    text = rule_text.lower()
    if any(w in text for w in ['vol', '成交量', 'rsi', 'ma', 'macd', 'kdj', '布林']):
        return "技术指标"
    elif any(w in text for w in ['资金费率', 'funding', '多空比', 'long_short']):
        return "外部信号"
    elif any(w in text for w in ['风险', '止损', '仓位', '杠杆']):
        return "风险控制"
    elif any(w in text for w in ['趋势', '突破', '支撑', '阻力']):
        return "趋势判断"
    else:
        return "综合分析"


def load_existing_cache() -> Dict:
    """加载现有缓存"""
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {"rules": [], "last_updated": None}


def save_cache(data: Dict) -> None:
    """保存缓存"""
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 知识缓存已更新: {CACHE_FILE}")
    print(f"   规则总数: {len(data['rules'])}")


def generate_cache(source_dir: Path = None) -> Dict:
    """生成知识缓存"""
    if source_dir is None:
        source_dir = SOURCE_DIR
    
    cache_dir = CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    existing = load_existing_cache()
    existing_ids = {r["id"] for r in existing["rules"]}
    
    all_rules = list(existing["rules"])
    new_count = 0
    
    # 扫描所有.md文件
    md_files = list(source_dir.glob("*.md"))
    md_files = [f for f in md_files if f.name not in [".learning_backup"]]
    
    print(f"📚 扫描目录: {source_dir}")
    print(f"   找到 {len(md_files)} 个.md文件")
    
    for md_file in md_files:
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            rules = extract_rules_from_md(content, md_file.name)
            
            for rule in rules:
                # 去重: 相同trigger不重复添加
                if rule["trigger"] not in [r["trigger"] for r in all_rules]:
                    all_rules.append(rule)
                    new_count += 1
                    
        except Exception as e:
            print(f"   ⚠️ 读取 {md_file.name} 出错: {e}")
    
    result = {"rules": all_rules, "last_updated": None}
    save_cache(result)
    
    print(f"   新增规则: {new_count}")
    
    return result


def search_rules(query: str, limit: int = 10) -> List[Dict]:
    """搜索规则 - 用于AI快速检索"""
    cache = load_existing_cache()
    query_lower = query.lower()
    
    scored = []
    for rule in cache["rules"]:
        score = 0
        trigger_lower = rule["trigger"].lower()
        if query_lower in trigger_lower:
            score = 10
        elif any(w in trigger_lower for w in query_lower.split()):
            score = 5
        if score > 0:
            scored.append((score, rule))
    
    scored.sort(key=lambda x: (-x[0], -x[1]["confidence"]))
    return [r for _, r in scored[:limit]]


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="知识缓存生成器")
    parser.add_argument("--source", type=str, help="源目录路径")
    args = parser.parse_args()
    
    source = Path(args.source) if args.source else None
    generate_cache(source)
