#!/usr/bin/env python3
"""
钦天监 · 社区情绪爬虫（防护版）
- 所有 HTTP 请求自动重试（指数退避）
- 各数据源独立超时，失败不影响其他数据源
- 快速失败，不卡整体调度
"""
import json, ssl, re, time
from datetime import datetime
import sys
sys.path.insert(0, "/Users/luxiangnan/edict/scripts/qintianjian")
from curl_http import curl_retry, curl_json

EDICT_DATA = "/Users/luxiangnan/edict/data"
POOL_FILE  = f"{EDICT_DATA}/sentiment_pool.json"
LOG_FILE   = f"{EDICT_DATA}/logs/qintianjian.log"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# ── 重试装饰器 ─────────────────────────────────────────
import random


def retry_get(max_retries=2, base_delay=1.0, timeout=6):
    """带重试的HTTP GET装饰器工厂"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            url = kwargs.get("url") or (args[0] if args else "")
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt >= max_retries:
                        return None
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                    time.sleep(delay)
            return None
        return wrapper
    return decorator


def safe_get(url, timeout=6, max_retries=2, base_delay=1.0) -> str | None:
    """安全的HTTP GET（使用curl），带重试和超时"""
    return curl_retry(url, max_retries=max_retries, base_delay=base_delay, timeout=timeout)


# ── Reddit RSS ────────────────────────────────────────
def fetch_reddit(subreddit, limit=8):
    url = f"https://www.reddit.com/r/{subreddit}/hot.rss?limit={limit}"
    # Reddit 通过代理访问（5秒超时）
    xml = curl_retry(url, timeout=5, max_retries=1, proxy=True)
    if not xml:
        return []
    items = re.findall(r'<entry>(.*?)</entry>', xml, re.DOTALL)
    results = []
    for block in items[:limit]:
        title = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', block, re.DOTALL)
        if not title:
            title = re.search(r'<title>(.*?)</title>', block, re.DOTALL)
        link = re.search(r'<link[^>]+href="(https://www\.reddit\.com/r/[^"]+)"', block)
        score = re.search(r'<reddit:score>(\d+)</reddit:score>', block)
        comments = re.search(r'<reddit:num_comments>(\d+)</reddit:num_comments>', block)
        title_text = title.group(1).strip() if title else ""
        link_text = link.group(1).strip() if link else ""
        if title_text:
            results.append({
                "platform": "Reddit",
                "subreddit": f"r/{subreddit}",
                "title": title_text,
                "url": link_text,
                "score": int(score.group(1)) if score else 0,
                "comments": int(comments.group(1)) if comments else 0,
            })
    return results


# ── Nitter 推特 RSS（多实例容错，任一可用即可）────
NITTER_INSTANCES = [
    "nitter.privacydev.net",
]


def fetch_nitter(username, limit=5):
    """尝试多个 Nitter 实例，任一成功即返回（快速失败）"""
    results = []
    for instance in NITTER_INSTANCES:
        url = f"https://{instance}/{username}/rss"
        # 无代理直连优先（3秒快速失败）
        for use_proxy in [False, True]:
            xml = curl_retry(url, timeout=3, max_retries=0, proxy=use_proxy)
            if xml:
                items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
                for block in items[:limit]:
                    title = re.search(r'<title>(.*?)</title>', block, re.DOTALL)
                    link = re.search(r'<link>(.*?)</link>', block, re.DOTALL)
                    ts = re.search(r'<pubDate>(.*?)</pubDate>', block, re.DOTALL)
                    results.append({
                        "platform": "X (Twitter)",
                        "account": f"@{username}",
                        "title": title.group(1).strip() if title else "",
                        "url": link.group(1).strip() if link else "",
                        "published": ts.group(1).strip()[:28] if ts else "",
                    })
                if results:
                    return results
                break
    return results[:limit]


# ── 情绪关键词打分 ────────────────────────────────────
POS_KW = ["bull", "bullish", "moon", "surge", "rally", "breakout", "ATH",
           "buy", "long", "up", "gain", "pump", "soar", "pumping"]
NEG_KW = ["bear", "bearish", "crash", "dump", "drop", "sell", "short",
           "hack", "scam", "ban", "regulation", "FUD", "liquidation",
           "down", "fall", "plunge", "capitulation", "crash", "panic"]


def keyword_sentiment(text):
    text = text.lower()
    pos = sum(1 for k in POS_KW if k in text)
    neg = sum(1 for k in NEG_KW if k in text)
    if pos > neg:
        return "positive", min(95, 50 + (pos - neg) * 20)
    elif neg > pos:
        return "negative", min(95, 50 + (neg - pos) * 20)
    return "neutral", 55


def compute_community_sentiment(reddit_posts, x_posts):
    all_posts = reddit_posts + x_posts
    if not all_posts:
        return {"sentiment": "unknown", "confidence": 0, "sample_size": 0}
    total_pos = total_neg = total_neu = 0
    weighted_score = 0
    for p in all_posts:
        sent, conf = keyword_sentiment(p["title"])
        weight = min(p.get("score", 1) / 100, 5) if "score" in p else 1
        if sent == "positive":
            total_pos += weight
            weighted_score += conf * weight
        elif sent == "negative":
            total_neg += weight
            weighted_score -= conf * weight
        else:
            total_neu += weight
    total = total_pos + total_neg + total_neu
    if total == 0:
        return {"sentiment": "neutral", "confidence": 55, "sample_size": len(all_posts)}
    sentiment = "positive" if weighted_score > 0 else ("negative" if weighted_score < 0 else "neutral")
    confidence = min(95, int(abs(weighted_score) / max(total, 1) * 2 + 55))
    return {
        "sentiment": sentiment,
        "confidence": confidence,
        "positive_weight": round(total_pos, 2),
        "negative_weight": round(total_neg, 2),
        "neutral_weight": round(total_neu, 2),
        "sample_size": len(all_posts),
        "reddit_threads_analyzed": len(reddit_posts),
        "x_posts_analyzed": len(x_posts),
    }


def update_pool(community_data):
    pool = {}
    try:
        with open(POOL_FILE) as f:
            pool = json.load(f)
    except Exception:
        pass
    pool["community"] = {**community_data, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    with open(POOL_FILE, "w") as f:
        json.dump(pool, f, ensure_ascii=False, indent=2)


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [社区情绪] {msg}"
    print(line)
    try:
        import os
        os.makedirs(f"{EDICT_DATA}/logs", exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    print("💬 钦天监·社区情绪爬虫启动")

    # Reddit RSS（通过代理，最多2个子版块）
    reddit_posts = []
    reddit_blocked = False
    for sub in ["cryptocurrency", "Bitcoin"]:
        try:
            posts = fetch_reddit(sub, limit=8)
            if posts:
                reddit_posts.extend(posts)
                print(f"  ✅ r/{sub}: {len(posts)}条")
            else:
                print(f"  ⚠️  r/{sub}: 无数据")
        except Exception as e:
            if not reddit_blocked:
                print(f"  ⚠️  Reddit RSS 不可用，跳过: {e}")
                reddit_blocked = True
            print(f"  ⏭  r/{sub}: 跳过（网络限制）")
        time.sleep(0.2)

    # Nitter X内容（Nitter实例全部下线，快速探测1个账号）
    x_posts = []
    for acc in ["crypto"]:
        try:
            posts = fetch_nitter(acc, limit=5)
            if posts:
                x_posts.extend(posts)
                print(f"  ✅ @{acc}: {len(posts)}条")
            else:
                print(f"  ⚠️  @{acc}: 无数据")
        except Exception as e:
            print(f"  ⏭  @{acc}: 跳过 - {e}")
        time.sleep(0.2)

    print(f"\n  汇总: Reddit {len(reddit_posts)}条 | X {len(x_posts)}条")

    # Fear&Greed（curl版，独立超时，不阻塞）
    fg_data = None
    fg_url = "https://api.alternative.me/fng/"
    try:
        d = curl_json(fg_url, timeout=8)
        if d and "data" in d:
            item = d["data"][0]
            fg_data = {"value": int(item["value"]), "label": item["value_classification"]}
            print(f"  ✅ Fear&Greed: {fg_data['value']} ({fg_data['label']})")
        else:
            print(f"  ⚠️  Fear&Greed: 获取失败")
    except Exception as e:
        print(f"  ⚠️  Fear&Greed: {e}")

    community_analysis = compute_community_sentiment(reddit_posts, x_posts)

    community_data = {
        "fear_greed": fg_data,
        "reddit_posts": reddit_posts[:15],
        "x_posts": x_posts[:10],
        "sentiment_analysis": community_analysis,
    }

    update_pool(community_data)

    sa = community_analysis
    log(f"完成 | 情绪:{sa['sentiment']}(置信{sa['confidence']}) | "
        f"样本:{sa['sample_size']} | Reddit:{len(reddit_posts)} X:{len(x_posts)}")
