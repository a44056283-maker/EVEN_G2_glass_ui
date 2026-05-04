#!/usr/bin/env python3
"""
GitHub技能搜索 + 自动纳入知识库 v1.0
1. 搜索GitHub上的交易技能
2. 把有价值的仓库整理进知识库
3. 把技能转化成策略
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime

HOME = Path.home()
WORKSPACE_ROOT = HOME / ".openclaw" / "workspace-tianlu"
KB_DIR = Path("/Volumes/TianLu_Storage/Knowledge_Strategy_Base")
SKILLS_DIR = KB_DIR / "Skills"  # 外部技能
PROXY = "http://127.0.0.1:5020"

def curl_github_api(url):
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "15", "-x", PROXY,
             "-H", "Accept: application/vnd.github.v3+json",
             "-H", "User-Agent: Mozilla/5.0", url],
            capture_output=True, timeout=20
        )
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
    except:
        pass
    return None

def search_repos(query, per_page=5):
    import urllib.parse
    encoded = urllib.parse.quote(query)
    url = f"https://api.github.com/search/repositories?q={encoded}&sort=stars&per_page={per_page}"
    return curl_github_api(url)

def analyze_repo(repo):
    name = repo.get("full_name", "")
    desc = repo.get("description", "")
    stars = repo.get("stargazers_count", 0)
    lang = repo.get("language", "")
    url = repo.get("html_url", "")
    updated = repo.get("updated_at", "")[:10]
    
    keywords = ["trading", "crypto", "quantitative", "backtest", "technical-analysis",
               "trading-bot", "algorithmic", "signals", "strategy",
               "risk-management", "portfolio", "finance"]
    
    score = sum(1 for kw in keywords if kw in f"{name} {desc}".lower())
    
    return {
        "name": name, "desc": desc, "stars": stars, "language": lang,
        "url": url, "updated": updated, "score": score,
        "worthy": score >= 2 and stars > 50
    }

def create_skill_doc(repo):
    """把仓库转化成技能文档"""
    name = repo["name"]
    url = repo["url"]
    desc = repo["desc"]
    stars = repo["stars"]
    lang = repo["language"]
    updated = repo["updated"]
    score = repo["score"]
    
    # 判断技能类型
    category = "通用技能"
    if any(kw in f"{name} {desc}".lower() for kw in ["backtest", "回测"]):
        category = "回测技能"
    elif any(kw in f"{name} {desc}".lower() for kw in ["risk", "风控", "portfolio", "组合"]):
        category = "风控技能"
    elif any(kw in f"{name} {desc}".lower() for kw in ["trading-bot", "bot", "交易机器人"]):
        category = "交易机器人"
    elif any(kw in f"{name} {desc}".lower() for kw in ["technical", "技术分析", "signals", "信号"]):
        category = "技术分析"
    elif any(kw in f"{name} {desc}".lower() for kw in ["sentiment", "情绪", "情绪分析"]):
        category = "情绪分析"
    
    filename = name.replace("/", "_") + ".md"
    
    content = f"""# {name}

> 来源: GitHub | ⭐ {stars} stars | 语言: {lang or 'N/A'} | 更新: {updated}
> URL: {url}
> 分类: {category} | 评分: {score}/10

---

## 描述

{desc or '无描述'}

---

## 核心功能

[根据描述推断]

### 优点

- [待分析]

### 缺点

- [待分析]

### 适用场景

- [待填写]

---

## 如何整合到现有系统

### 整合步骤

1. [ ] 研究文档
2. [ ] 评估是否适合我们的策略
3. [ ] 如果适合，集成到 freqtrade
4. [ ] 回测验证
5. [ ] 实盘测试

### 整合难度

- [ ] 简单：直接可用
- [ ] 中等：需要适配
- [ ] 复杂：需要重写

---

## 与现有知识库的关系

- 缠论: [关系]
- 威科夫: [关系]
- 现有策略: [关系]

---

## 决策

- [ ] 纳入知识库
- [ ] 需要进一步研究
- [ ] 不适合我们的系统

### 理由

[待填写]

---

## 最后更新

{datetime.now().strftime('%Y-%m-%d')} - 自动从GitHub同步
"""
    
    return filename, content

def create_strategy_doc(repo):
    """把仓库转化成策略文档"""
    name = repo["name"]
    url = repo["url"]
    desc = repo["desc"]
    stars = repo["stars"]
    lang = repo["language"]
    updated = repo["updated"]
    
    filename = "策略_" + name.replace("/", "_") + ".md"
    
    content = f"""# 策略笔记: {name}

> 来源: {url}
> ⭐ {stars} stars | 语言: {lang or 'N/A'}

---

## 策略概述

{desc or '无描述'}

---

## 策略原理

[根据仓库描述推断策略原理]

### 入场条件

- [ ] 条件1
- [ ] 条件2

### 出场条件

- [ ] 止损
- [ ] 止盈
- [ ] 跟踪止损

### 适用市场

- [ ] 趋势市场
- [ ] 震荡市场
- [ ] 两者皆可

---

## 如何验证

1. [ ] 阅读原仓库文档
2. [ ] 理解策略逻辑
3. [ ] 用我们的数据回测
4. [ ] 对比我们现有策略

---

## 整合建议

[待填写]

---

## 结论

- [ ] 纳入策略库
- [ ] 需要进一步研究
- [ ] 不适合

---

{datetime.now().strftime('%Y-%m-%d')} - 太子整理
"""
    
    return filename, content

def main():
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    
    print("=" * 60)
    print("🔍 GitHub技能搜索 + 纳入知识库")
    print("=" * 60)
    print()
    
    queries = [
        ("trading bot github", "交易机器人"),
        ("quantitative trading python", "量化交易"),
        ("backtesting framework", "回测框架"),
        ("technical analysis library", "技术分析"),
        ("risk management portfolio", "风控组合"),
        ("crypto trading signals", "交易信号"),
        ("algorithmic trading strategies", "算法策略"),
    ]
    
    all_repos = []
    
    print("📦 搜索交易技能...")
    for query, desc in queries:
        print(f"  🔍 {desc}: {query}")
        data = search_repos(query, per_page=5)
        if data and "items" in data:
            for repo in data["items"][:3]:
                analyzed = analyze_repo(repo)
                all_repos.append(analyzed)
    
    # 去重
    seen = set()
    unique_repos = []
    for r in all_repos:
        if r["name"] not in seen:
            seen.add(r["name"])
            unique_repos.append(r)
    
    worthy = [r for r in unique_repos if r["worthy"]]
    
    print()
    print(f"📊 搜索结果: {len(unique_repos)}个仓库，{len(worthy)}个值得关注")
    
    # 创建目录
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    STRATEGY_DIR = KB_DIR / "Strategy" / "外部策略"
    STRATEGY_DIR.mkdir(parents=True, exist_ok=True)
    
    # 纳入知识库
    added_skills = []
    added_strategies = []
    
    for repo in worthy[:5]:  # 最多5个
        fname, content = create_skill_doc(repo)
        skill_path = SKILLS_DIR / fname
        skill_path.write_text(content)
        added_skills.append(fname)
        
        # 同时生成策略
        fname2, content2 = create_strategy_doc(repo)
        strategy_path = STRATEGY_DIR / fname2
        strategy_path.write_text(content2)
        added_strategies.append(fname2)
    
    print()
    print("=" * 60)
    print("✅ 完成")
    print(f"   新增技能: {len(added_skills)}")
    for s in added_skills:
        print(f"     - {s}")
    print(f"   新增策略: {len(added_strategies)}")
    for s in added_strategies:
        print(f"     - {s}")
    print("=" * 60)
    
    # 保存搜索报告
    report = {
        "timestamp": now.isoformat(),
        "total_repos": len(unique_repos),
        "worthy_repos": len(worthy),
        "added_skills": added_skills,
        "added_strategies": added_strategies
    }
    
    report_file = WORKSPACE_ROOT / "memory" / "github_skills" / f"skills_integrated_{date_str}.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    
    return report

if __name__ == "__main__":
    main()
