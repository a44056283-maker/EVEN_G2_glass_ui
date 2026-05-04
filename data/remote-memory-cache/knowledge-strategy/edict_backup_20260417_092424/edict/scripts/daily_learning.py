#!/usr/bin/env python3
"""
太子每日学习脚本 - 知识库驱动版
每天14:00执行，从知识库提取主题内容学习，生成学习笔记并同步到移动硬盘
"""

import json
import sys
from pathlib import Path
from datetime import datetime

HOME = Path.home()
WORKSPACE_ROOT = HOME / ".openclaw" / "workspace-tianlu"
KB_DIR = Path("/Volumes/TianLu_Storage/Knowledge_Strategy_Base")
LEARNING_DIR = WORKSPACE_ROOT / "memory" / "learning"

TODAY = datetime.now().strftime("%Y-%m-%d")
TIME_SLOT = datetime.now().strftime("%H%M")


def get_week_cycle():
    """4周学习循环"""
    month = datetime.now().month
    return (month - 1) % 4 + 1


def get_today_topic():
    """获取今天的学习主题"""
    week = get_week_cycle()
    day = datetime.now().weekday()  # 0=周一

    schedule = {
        1: [  # 第1周：技术分析
            ("缠论", "分型识别", "K线顶底分型的定义、包含关系处理、Python识别代码"),
            ("缠论", "笔与线段", "笔的构成规则、上升笔下降笔识别、线段划分"),
            ("缠论", "中枢与背驰", "中枢定义、3笔重叠区间、背驰判断方法"),
            ("威科夫", "吸筹阶段", "吸筹5阶段：冻成虫、高高潮、弹簧、测试、上涨"),
            ("威科夫", "派发阶段", "派发5阶段：高潮、创造新高、高潮2、回落测试"),
            ("技术分析", "支撑阻力", "关键SR位识别、三维共振、突破确认"),
            ("技术分析", "K线形态", "锤子、吞没、十字星、pin bar识别"),
        ],
        2: [  # 第2周：交易心理学
            ("心理学", "损失厌恶", "损失厌恶心理、处置效应规避、卖出时机判断"),
            ("心理学", "过度自信", "过度自信5个表现、过度交易识别、交易频率监控"),
            ("心理学", "锚定效应", "锚定心理、参考点依赖、最低价执念"),
            ("心理学", "羊群FOMO", "FOMO触发机制、24小时冷静期、逆向交易"),
            ("心理学", "确认偏差", "选择性关注、忽视反证、逆向思考方法"),
            ("心理学", "近期偏差", "近期事件放大、滚动绩效、长期数据验证"),
            ("心理学", "综合复盘", "偏差清单、触发场景、应对策略"),
        ],
        3: [  # 第3周：仓位管理
            ("仓位", "凯利公式", "f*=(W·R-(1-W))/R、半凯利、币圈用1/4凯利"),
            ("仓位", "ATR止损", "ATR计算、2×ATR止损、动态调整"),
            ("仓位", "强平计算", "强平价公式、保证金率、杠杆倍数关系"),
            ("仓位", "VaR风险", "风险价值、波动率计算、置信区间"),
            ("仓位", "盈亏比", "盈亏比优化、2:1最小、胜率匹配"),
            ("仓位", "仓位分配", "固定比例、波动率调整、风险预算"),
            ("仓位", "风控规则", "硬性规则、动态调整、异常处理"),
        ],
        4: [  # 第4周：量化回测
            ("回测", "回测陷阱", "过拟合、前视偏差、生存者偏差"),
            ("回测", "夏普比率", "夏普公式、索提诺、风险调整收益"),
            ("回测", "参数优化", "参数扫描、最优参数、过度拟合风险"),
            ("回测", "绩效归因", "盈利来源、亏损分析、归因方法"),
            ("回测", "策略迭代", "策略改进、回测验证、实盘对比"),
            ("回测", "策略评估", "胜率、盈亏比、最大回撤、索提诺"),
            ("回测", "周总结", "本周学习总结、下周计划、知识库更新"),
        ],
    }

    topics = schedule.get(week, schedule[1])
    return topics[day]


def get_kb_content(category: str, topic: str) -> str:
    """从知识库提取相关内容"""
    kb_files = {
        ("仓位", "凯利公式"): KB_DIR / "Knowledge" / "仓位管理" / "凯利公式与ATR动态止损实战指南.md",
        ("仓位", "ATR止损"): KB_DIR / "Knowledge" / "仓位管理" / "凯利公式与ATR动态止损实战指南.md",
        ("缠论", "分型识别"): KB_DIR / "Knowledge" / "缠论" / "基础理论" / "缠论基础理论.md",
        ("缠论", "笔与线段"): KB_DIR / "Knowledge" / "缠论" / "基础理论" / "缠论基础理论.md",
        ("缠论", "中枢与背驰"): KB_DIR / "Knowledge" / "缠论" / "基础理论" / "缠论基础理论.md",
        ("威科夫", "吸筹阶段"): KB_DIR / "Knowledge" / "威科夫量价分析" / "基础理论" / "威科夫基础理论.md",
        ("威科夫", "派发阶段"): KB_DIR / "Knowledge" / "威科夫量价分析" / "基础理论" / "威科夫基础理论.md",
        ("心理学", "损失厌恶"): KB_DIR / "Knowledge" / "交易心理学" / "损失厌恶与处置效应策略.md",
        ("心理学", "过度自信"): KB_DIR / "Knowledge" / "交易心理学" / "过度自信与过度交易策略.md",
        ("心理学", "锚定效应"): KB_DIR / "Knowledge" / "交易心理学" / "锚定效应与参考点依赖策略.md",
        ("心理学", "羊群FOMO"): KB_DIR / "Knowledge" / "交易心理学" / "羊群效应与FOMO策略.md",
        ("心理学", "确认偏差"): KB_DIR / "Knowledge" / "交易心理学" / "确认偏差与选择性关注策略.md",
        ("心理学", "近期偏差"): KB_DIR / "Knowledge" / "交易心理学" / "近期偏差与选择性记忆策略.md",
    }

    key = (category, topic)
    if key in kb_files and kb_files[key].exists():
        content = kb_files[key].read_text(encoding="utf-8")
        # 截取前2000字符
        return content[:2000]
    return ""


def generate_learning_note(category: str, topic: str, detail: str, kb_content: str) -> str:
    """生成完整的学习笔记"""

    # 从KB内容中提取关键段落
    key_insights = kb_content[:1500] if kb_content else f"今日学习: {category} - {topic}\n{detail}"

    note = f"""# 每日学习笔记 - {TODAY}

> 太子每日学习记录 | 时间段: 14:00 | 主题: {category}/{topic}

---

## 今日学习主题

- **类别**: {category}
- **主题**: {topic}
- **详细内容**: {detail}
- **学习来源**: 知识策略库 (Knowledge_Strategy_Base)

---

## 核心概念

### {topic} — 关键要点

{kb_content[:1200] if kb_content else '(从知识库提取)'}

---

## 实战应用

### 1. 理解要点

- [ ] 理解 {topic} 的核心定义
- [ ] 掌握 {topic} 的适用场景
- [ ] 识别 {topic} 在实盘中的表现形式

### 2. 应用步骤

```
Step 1: 理解概念 → {detail}
Step 2: 寻找案例 → 在当前行情中找对应形态
Step 3: 实践验证 → 用所学分析持仓或行情
Step 4: 复盘总结 → 记录分析对错
```

### 3. 注意事项

- {category}类知识需要持续实践
- 不要只看理论，要在实盘中使用
- 每次使用后复盘效果

---

## 纳入知识库

### 状态检查

| 项目 | 状态 |
|------|------|
| 知识库已有内容 | {'✅' if kb_content else '⚠️ 新增中'} |
| 实战案例补充 | ⏳ 待补充 |
| 策略形成 | ⏳ 待形成 |

### 下次改进

1. 在实盘中主动使用今天学的知识
2. 记录使用效果
3. 如有新理解，更新到知识库

---

## 知识库同步

- 笔记位置: `memory/learning/daily_learning_{TODAY}.md`
- 移动硬盘: `/Volumes/TianLu_Storage/Knowledge_Strategy_Base/`
- 同步时间: 22:00 (knowledge_base_update.py)

---

_学习时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_
"""

    return note


def main():
    print("=" * 60)
    print(f"📚 太子每日学习 ({TODAY} {datetime.now().strftime('%H:%M')})")
    print("=" * 60)

    # 检查移动硬盘
    if not KB_DIR.exists():
        print(f"⚠️ 移动硬盘未挂载: {KB_DIR}")
        sys.exit(1)

    # 获取今日主题
    category, topic, detail = get_today_topic()
    week = get_week_cycle()
    print(f"\n📅 当前: 第{week}周 | 主题: {category}/{topic}")
    print(f"📝 详情: {detail}")

    # 从知识库提取内容
    print("\n📖 从知识库提取内容...")
    kb_content = get_kb_content(category, topic)

    if kb_content:
        print(f"✅ 找到知识库内容 ({len(kb_content)}字符)")
    else:
        print(f"⚠️ 知识库未找到对应内容，将生成新内容")

    # 生成学习笔记
    note_content = generate_learning_note(category, topic, detail, kb_content)

    # 保存到本地
    LEARNING_DIR.mkdir(parents=True, exist_ok=True)
    note_file = LEARNING_DIR / f"daily_learning_{TODAY}.md"
    note_file.write_text(note_content, encoding="utf-8")

    print(f"\n✅ 学习笔记已生成:")
    print(f"   {note_file}")

    # 同步到移动硬盘正式知识库目录（按分类）
    category_map = {
        "缠论": "Knowledge/缠论",
        "威科夫": "Knowledge/威科夫量价分析",
        "技术分析": "Knowledge/技术分析",
        "心理学": "Knowledge/交易心理学",
        "仓位": "Knowledge/仓位管理",
        "回测": "Knowledge/量化回测",
    }
    kb_dest_dir = KB_DIR / category_map.get(category, "Knowledge")
    kb_dest_dir.mkdir(parents=True, exist_ok=True)
    kb_file = kb_dest_dir / f"太子自学_{TODAY}_{category}_{topic}.md"
    kb_file.write_text(note_content, encoding="utf-8")
    print(f"✅ 已同步到知识库:")
    print(f"   {kb_file}")

    # 更新README追踪
    readme = KB_DIR / "README_LEARNING_LOG.md"
    log_entry = f"\n| {TODAY} | {category} | {topic} | ✅ | {note_file.name} |"
    if readme.exists():
        existing = readme.read_text(encoding="utf-8")
        if log_entry.strip() not in existing:
            readme.write_text(existing + log_entry, encoding="utf-8")
    else:
        header = "# 太子每日学习记录\n\n| 日期 | 类别 | 主题 | 状态 | 笔记文件 |\n|------|------|------|------|----------|\n"
        readme.write_text(header + log_entry, encoding="utf-8")
    print(f"✅ 学习记录已更新: README_LEARNING_LOG.md")

    print("\n" + "=" * 60)
    print("📚 14:00 每日学习完成")
    print("💡 22:00 将执行知识库最终同步")
    print("=" * 60)


if __name__ == "__main__":
    main()
