#!/usr/bin/env python3
"""
知识库每日更新脚本 - 主动整合版
太子每天22:00执行，把当天所有学习（太子+子代理）整理进知识库

学习→知识库→策略库的完整闭环
"""

import json
import shutil
from pathlib import Path
from datetime import datetime

HOME = Path.home()
WORKSPACE_ROOT = HOME / ".openclaw" / "workspace-tianlu"
KB_DIR = Path("/Volumes/TianLu_Storage/Knowledge_Strategy_Base")

TODAY = datetime.now().strftime("%Y-%m-%d")

# 子代理 → 知识库对应目录映射
AGENT_KB_MAP = {
    "hubu": "Knowledge/交易心理学",        # 行为金融学
    "bingbu": "Knowledge/交易心理学",        # 过度自信/风控
    "gongbu": "Knowledge/技术架构",         # Freqtrade架构/锚定效应
    "qintianjian": "Knowledge/交易心理学",  # 羊群效应
    "zhongshu": "Knowledge/交易心理学",     # 确认偏差
    "shangshu": "Knowledge/交易心理学",     # 近期偏差
    "tianlu": "Knowledge",                  # 太子自学
}


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def check_kb_mounted():
    """检查移动硬盘是否挂载"""
    if not KB_DIR.exists():
        log(f"❌ 移动硬盘未挂载: {KB_DIR}")
        return False
    kb_readme = KB_DIR / "README.md"
    if not kb_readme.exists():
        log(f"❌ 移动硬盘未正确挂载（无README）")
        return False
    return True


def get_kb_file_count():
    """获取知识库文件数"""
    return len(list(KB_DIR.glob("**/*.md")))


def find_new_learning_files():
    """查找所有子代理的新学习文件"""
    new_files = []
    
    agents = list(AGENT_KB_MAP.keys())
    for agent in agents:
        agent_workspace = HOME / f".openclaw" / f"workspace-{agent}" / "memory" / "learning"
        if not agent_workspace.exists():
            continue
        
        # 获取该代理的所有学习文件
        for f in agent_workspace.glob("*.md"):
            # 跳过非学习文件
            if f.name.startswith("README") or f.name.startswith("github_"):
                continue
            
            # 检查知识库是否已有此文件（精确匹配）
            kb_dest = KB_DIR / AGENT_KB_MAP[agent] / f.name
            if not kb_dest.exists():
                new_files.append({
                    "agent": agent,
                    "source": f,
                    "dest_dir": AGENT_KB_MAP[agent],
                    "dest": kb_dest,
                    "name": f.name,
                })
    
    return new_files


def integrate_into_kb(new_files):
    """将新学习文件整合到知识库"""
    integrated = []
    failed = []
    
    for item in new_files:
        try:
            dest_dir = KB_DIR / item["dest_dir"]
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item["source"], item["dest"])
            integrated.append(item)
            log(f"  ✅ {item['agent']}: {item['name']} → {item['dest_dir']}/")
        except Exception as e:
            failed.append({**item, "error": str(e)})
            log(f"  ❌ {item['agent']}: {item['name']} 失败: {e}")
    
    return integrated, failed


def check_kb_integrity():
    """检查知识库完整性"""
    required_dirs = [
        "Knowledge/缠论/基础理论",
        "Knowledge/威科夫量价分析/基础理论",
        "Knowledge/交易心理学",
        "Knowledge/仓位管理",
        "Strategy",
        "AgentBooks",
    ]
    
    missing = []
    for d in required_dirs:
        if not (KB_DIR / d).exists():
            missing.append(d)
    
    return missing


def update_kb_readme(integrated_count, kb_file_count):
    """更新知识库README"""
    readme = KB_DIR / "README.md"
    if not readme.exists():
        return
    
    content = readme.read_text(encoding="utf-8")
    
    # 检查是否有今日更新记录
    today_marker = f"今日更新: {TODAY}"
    if today_marker not in content:
        # 在更新日志添加今日记录
        today_entry = f"| {TODAY} | vNEW | 整合{integrated_count}个新文件 | 太子定时任务 |\n"
        
        # 找到更新日志表格，插入新行
        lines = content.split("\n")
        insert_idx = None
        for i, line in enumerate(lines):
            if "| 日期" in line and "版本" in line:
                insert_idx = i + 1
                break
        
        if insert_idx:
            lines.insert(insert_idx, today_entry)
            content = "\n".join(lines)
            readme.write_text(content, encoding="utf-8")
            log(f"  📝 README已更新")
    
    # 更新文件计数
    if f"共{kb_file_count}个文件" in content:
        content = content.replace(
            f"共{kb_file_count - integrated_count}个文件",
            f"共{kb_file_count}个文件"
        )


def main():
    print("=" * 60)
    log(f"📚 知识库每日更新 ({TODAY})")
    print("=" * 60)
    
    # 1. 检查移动硬盘
    log("🔍 检查移动硬盘...")
    if not check_kb_mounted():
        print("❌ 退出")
        return
    log("  ✅ 移动硬盘正常")
    
    # 2. 统计当前状态
    kb_before = get_kb_file_count()
    log(f"📊 知识库现有: {kb_before}个文件")
    
    # 3. 查找新学习文件
    log("🔍 扫描子代理学习目录...")
    new_files = find_new_learning_files()
    if new_files:
        log(f"  ⚠️ 发现 {len(new_files)} 个待整合文件:")
        for item in new_files:
            log(f"     - {item['agent']}: {item['name']}")
    else:
        log(f"  ✅ 无待整合文件")
    
    # 4. 整合到知识库
    if new_files:
        log("📋 整合到知识库...")
        integrated, failed = integrate_into_kb(new_files)
        log(f"  ✅ 成功: {len(integrated)}个")
        if failed:
            log(f"  ❌ 失败: {len(failed)}个")
    
    # 5. 检查知识库完整性
    log("🔍 检查知识库完整性...")
    missing = check_kb_integrity()
    if missing:
        log(f"  ⚠️ 缺少目录: {', '.join(missing)}")
    else:
        log(f"  ✅ 目录结构完整")
    
    # 6. 统计更新后状态
    kb_after = get_kb_file_count()
    log(f"📊 知识库更新后: {kb_after}个文件 (+{kb_after - kb_before})")
    
    # 7. 更新README
    log("📝 更新README...")
    update_kb_readme(len(new_files), kb_after)
    
    # 8. 总结
    print("=" * 60)
    log(f"📚 22:00 知识库更新完成")
    log(f"   今日整合: {len(new_files)}个文件")
    log(f"   知识库总计: {kb_after}个文件")
    print("=" * 60)


if __name__ == "__main__":
    main()
