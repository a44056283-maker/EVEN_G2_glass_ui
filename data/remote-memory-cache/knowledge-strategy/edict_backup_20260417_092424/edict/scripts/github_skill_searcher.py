#!/usr/bin/env python3
"""
GitHub技能搜索脚本 v1.0
每天在GitHub上搜索：
1. 交易系统优化相关的技能/插件
2. 高级分析师/专业交易相关的知识和技能
"""

import json
import subprocess
import urllib.parse
from pathlib import Path
from datetime import datetime

HOME = Path.home()
WORKSPACE_ROOT = HOME / ".openclaw" / "workspace-tianlu"
KB_DIR = Path("/Volumes/TianLu_Storage/Knowledge_Strategy_Base")
OUTPUT_DIR = WORKSPACE_ROOT / "memory" / "github_skills"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROXY = "http://127.0.0.1:5020"

def curl_github_api(url):
    """通过代理调用GitHub API"""
    try:
        cmd = [
            "curl", "-s", "--max-time", "15", "-x", PROXY,
            "-H", "Accept: application/vnd.github.v3+json",
            "-H", "User-Agent: Mozilla/5.0",
            url
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=20)
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
    except:
        pass
    return None

def search_repos(query, sort="stars", per_page=5):
    """搜索GitHub仓库"""
    encoded_query = urllib.parse.quote(query)
    url = f"https://api.github.com/search/repositories?q={encoded_query}&sort={sort}&per_page={per_page}"
    return curl_github_api(url)

def search_code(query, per_page=5):
    """搜索GitHub代码"""
    encoded_query = urllib.parse.quote(query)
    url = f"https://api.github.com/search/code?q={encoded_query}&per_page={per_page}"
    return curl_github_api(url)

def search_topics(query, per_page=10):
    """按主题搜索仓库"""
    encoded_query = urllib.parse.quote(query)
    url = f"https://api.github.com/search/repositories?q=topic:{encoded_query}&sort=stars&per_page={per_page}"
    return curl_github_api(url)

def analyze_repo(repo):
    """分析仓库是否有价值"""
    name = repo.get("full_name", "")
    desc = repo.get("description", "")
    stars = repo.get("stargazers_count", 0)
    lang = repo.get("language", "")
    url = repo.get("html_url", "")
    updated = repo.get("updated_at", "")[:10]
    
    # 检查是否值得关注
    score = 0
    keywords = ["trading", "crypto", "quantitative", "backtest", "technical-analysis",
               "trading-bot", "algorithmic-trading", "signals", "strategy",
               "risk-management", "portfolio", "finance", "investment"]
    
    text = f"{name} {desc}".lower()
    for kw in keywords:
        if kw in text:
            score += 1
    
    return {
        "name": name,
        "desc": desc,
        "stars": stars,
        "language": lang,
        "url": url,
        "updated": updated,
        "score": score,
        "worth_try": score >= 2 and stars > 50
    }

def search_trading_skills():
    """搜索交易相关技能"""
    queries = [
        ("trading bot github actions", "trading-bot"),
        ("quantitative trading python", "quant"),
        ("technical analysis library", "technical"),
        ("backtesting framework", "backtest"),
        ("crypto trading signals", "signals"),
        ("risk management portfolio", "risk"),
        ("algorithmic trading strategies", "strategy"),
    ]
    
    results = []
    
    for query, category in queries:
        print(f"  🔍 搜索: {query}")
        data = search_repos(query, per_page=5)
        if data and "items" in data:
            for repo in data["items"][:3]:
                analyzed = analyze_repo(repo)
                analyzed["category"] = category
                results.append(analyzed)
    
    return results

def search_analyst_skills():
    """搜索分析师相关技能"""
    queries = [
        ("financial analysis jupyter", "analysis"),
        ("data visualization trading", "visualization"),
        ("market data API", "market-data"),
        ("sentiment analysis crypto", "sentiment"),
        ("machine learning trading", "ml"),
    ]
    
    results = []
    
    for query, category in queries:
        print(f"  🔍 搜索: {query}")
        data = search_repos(query, per_page=5)
        if data and "items" in data:
            for repo in data["items"][:3]:
                analyzed = analyze_repo(repo)
                analyzed["category"] = category
                results.append(analyzed)
    
    return results

def filter_worthy(results):
    """过滤出值得关注的仓库"""
    worthy = [r for r in results if r.get("worth_try", False)]
    # 按分数排序
    worthy.sort(key=lambda x: x["score"] * 1000 + x["stars"], reverse=True)
    return worthy

def generate_report(trading_results, analyst_results):
    """生成搜索报告"""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    
    worthy_trading = filter_worthy(trading_results)
    worthy_analyst = filter_worthy(analyst_results)
    
    report = f"""# GitHub技能搜索报告 - {date_str}

> 搜索时间: {now.strftime('%H:%M')}
> 太子每日GitHub技能搜索

---

## 一、交易系统优化（{len(trading_results)}个仓库，{len(worthy_trading)}个值得看）

### 值得关注的仓库

"""
    
    if worthy_trading:
        for r in worthy_trading[:10]:
            report += f"""#### [{r['name']}]({r['url']})

- ⭐ {r['stars']} stars | {r['language'] or 'N/A'} | 更新: {r['updated']}
- 描述: {r['desc'] or '无'}
- 评分: {r['score']} | 分类: {r['category']}

"""
    else:
        report += "未找到评分>=2的仓库\n"

    report += f"""
---

## 二、分析师技能（{len(analyst_results)}个仓库，{len(worthy_analyst)}个值得看）

### 值得关注的仓库

"""
    
    if worthy_analyst:
        for r in worthy_analyst[:10]:
            report += f"""#### [{r['name']}]({r['url']})

- ⭐ {r['stars']} stars | {r['language'] or 'N/A'} | 更新: {r['updated']}
- 描述: {r['desc'] or '无'}
- 评分: {r['score']} | 分类: {r['category']}

"""
    else:
        report += "未找到评分>=2的仓库\n"

    report += f"""
---

## 三、总结

| 类别 | 搜索到 | 值得看 |
|------|--------|---------|
| 交易系统 | {len(trading_results)} | {len(worthy_trading)} |
| 分析师技能 | {len(analyst_results)} | {len(worthy_analyst)} |

"""
    
    if worthy_trading or worthy_analyst:
        report += "💡 有值得研究的仓库，建议花时间看看\n"
    else:
        report += "✅ 今天没有找到更好的技能，保持现有系统\n"

    report += """

---

## 四、待深入研究

"""
    
    all_worthy = worthy_trading[:5] + worthy_analyst[:5]
    if all_worthy:
        for i, r in enumerate(all_worthy, 1):
            report += f"{i}. [{r['name']}]({r['url']}) - ⭐{r['stars']}\n"
    else:
        report += "无\n"

    return report

def save_report(report, trading, analyst):
    """保存报告"""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%M")
    
    # Markdown报告
    md_file = OUTPUT_DIR / f"github_skills_{date_str}_{time_str}.md"
    md_file.write_text(report)
    
    # JSON数据
    json_file = OUTPUT_DIR / f"github_skills_{date_str}_{time_str}.json"
    json_data = {
        "timestamp": now.isoformat(),
        "trading_repos": trading,
        "analyst_repos": analyst,
        "worthy_trading": filter_worthy(trading),
        "worthy_analyst": filter_worthy(analyst)
    }
    json_file.write_text(json.dumps(json_data, ensure_ascii=False, indent=2))
    
    # 最新链接
    latest_link = OUTPUT_DIR / "latest.md"
    latest_link.write_text("# GitHub技能搜索 - " + date_str + "\n\n[查看完整报告](" + md_file.name + ")\n")
    
    return md_file, json_file

def main():
    print("=" * 60)
    print("🔍 GitHub技能搜索 - 太子每日任务")
    print("=" * 60)
    print()
    
    print("📦 搜索交易系统优化相关技能...")
    trading = search_trading_skills()
    print(f"   找到 {len(trading)} 个仓库")
    
    print()
    print("📊 搜索分析师技能相关知识...")
    analyst = search_analyst_skills()
    print(f"   找到 {len(analyst)} 个仓库")
    
    print()
    print("📝 生成报告...")
    report = generate_report(trading, analyst)
    md_file, json_file = save_report(report, trading, analyst)
    
    worthy = filter_worthy(trading + analyst)
    
    print()
    print("=" * 60)
    print(f"✅ 搜索完成")
    print(f"   报告: {md_file.name}")
    print(f"   数据: {json_file.name}")
    print(f"   值得看: {len(worthy)} 个")
    print("=" * 60)
    
    if worthy:
        print("\n💡 值得关注的仓库:")
        for r in worthy[:5]:
            print(f"   - {r['name']} ⭐{r['stars']}")
    else:
        print("\n✅ 今天没有找到更好的技能，保持现有系统")
    
    return md_file, json_file

if __name__ == "__main__":
    main()
