#!/usr/bin/env python3
"""
钦天监 · 新闻舆情爬虫
数据源：Bitcoinist / Cointelegraph / Decrypt / Cryptonews
（CoinDesk/CryptoSlate/吴说区块链 因网络封锁暂时替换）
输出：edict/data/sentiment_pool.json（news节）
"""
import json, ssl, html, re
from datetime import datetime
from html.parser import HTMLParser
import sys
sys.path.insert(0, "/Users/luxiangnan/edict/scripts/qintianjian")
from curl_http import curl_retry as _curl_retry

EDICT_DATA = "/Users/luxiangnan/edict/data"
POOL_FILE  = f"{EDICT_DATA}/sentiment_pool.json"
LOG_FILE   = f"{EDICT_DATA}/logs/qintianjian.log"

# ── SSL context ────────────────────────────────────────
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# ── 新闻RSS配置 ───────────────────────────────────────
# 注意：CoinDesk/CryptoSlate/吴说区块链 因网络封锁暂时替换为可用源
RSS_FEEDS = {
    "Bitcoinist": {
        "url": "https://bitcoinist.com/feed/",
        "lang": "en",
    },
    "Cointelegraph": {
        "url": "https://cointelegraph.com/rss",
        "lang": "en",
    },
    "Decrypt": {
        "url": "https://decrypt.co/feed",
        "lang": "en",
    },
    "Cryptonews": {
        "url": "https://cryptonews.com/feed/",
        "lang": "en",
    },
    "吴说区块链": {
        "url": "https://www.wu-talk.com/rss",
        "lang": "zh",
    },
}

# ── 简易HTML→正文提取 ─────────────────────────────────
class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.texts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            t = data.strip()
            if t:
                self.texts.append(t)

    def get_text(self, max_len=300):
        text = " ".join(self.texts)[:max_len]
        return text


def fetch_url(url, timeout=8, max_retries=2, base_delay=1.0):
    """带重试的HTTP GET（使用curl），防止网络抖动导致失败"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
    # curl_retry 内部已经做了重试和超时处理
    result = _curl_retry(url, max_retries=max_retries, base_delay=base_delay, timeout=timeout)
    if result:
        # curl返回bytes，需要解码
        if isinstance(result, bytes):
            return result.decode("utf-8", errors="replace")
        return result
    return None


def extract_text(html, max_len=200):
    """从HTML提取正文片段"""
    try:
        p = TextExtractor()
        p.feed(html)
        return p.get_text(max_len)
    except:
        return ""


def parse_rss_items(xml_str, source_name):
    """解析RSS XML，返回items列表"""
    items = []
    # 提取所有<item>块
    item_blocks = re.findall(r'<item>(.*?)</item>', xml_str, re.DOTALL)
    for block in item_blocks[:8]:  # 最多取8条
        try:
            title = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', block, re.DOTALL)
            if not title:
                title = re.search(r'<title>(.*?)</title>', block, re.DOTALL)
            # 先尝试CDATA格式，再fallback普通格式
            cdata_link = re.search(r'<link><!\[CDATA\[(.*?)\]\]></link>', block, re.DOTALL)
            if cdata_link:
                raw = cdata_link.group(1).strip()
                link_text = html.unescape(raw)
            else:
                plain = re.search(r'<link>(https?://[^\s<]+)</link>', block, re.DOTALL)
                if not plain:
                    plain = re.search(r'<link>(.*?)</link>', block, re.DOTALL)
                link_text = plain.group(1).strip() if plain else ""
            pubdate = re.search(r'<pubDate>(.*?)</pubDate>', block, re.DOTALL)
            desc_raw = re.search(r'<description><!\[CDATA\[(.*?)\]\]></description>', block, re.DOTALL)
            if not desc_raw:
                desc_raw = re.search(r'<description>(.*?)</description>', block, re.DOTALL)

            title_text = title.group(1).strip() if title else ""
            pub_text   = pubdate.group(1).strip()[:28] if pubdate else ""
            desc_text  = extract_text(desc_raw.group(1) if desc_raw else "", 200)

            if title_text and link_text:
                items.append({
                    "source": source_name,
                    "title": title_text,
                    "url": link_text,
                    "published": pub_text,
                    "summary": desc_text,
                })
        except Exception:
            continue
    return items


def fetch_all_news():
    """抓取所有RSS源"""
    all_items = []
    sources_meta = []

    for name, cfg in RSS_FEEDS.items():
        xml = fetch_url(cfg["url"])
        if xml:
            items = parse_rss_items(xml, name)
            all_items.extend(items)
            sources_meta.append({
                "source": name,
                "status": "ok",
                "count": len(items),
                "url": cfg["url"],
                "lang": cfg["lang"],
            })
            print(f"  ✅ {name}: {len(items)}条")
        else:
            sources_meta.append({
                "source": name,
                "status": "error",
                "count": 0,
                "url": cfg["url"],
            })
            print(f"  ❌ {name}: 抓取失败")

    return all_items, sources_meta


def simple_sentiment(title_text, desc_text):
    """
    简易情绪判断（关键词打分）
    返回: positive/negative/neutral + confidence(0-100)
    """
    pos_kw = ["bullish", "surge", "rally", "soar", "gain", "up", "high",
              "上涨", "利好", "突破", "暴涨", "牛市", "做多", "看涨"]
    neg_kw = ["crash", "plunge", "fall", "drop", "bear", "sell", "hack",
              "fraud", "ban", "跌", "暴跌", "利空", "熊市", "做空",
              "监管", "SEC", "CFTC", "黑天鹅", "危机"]

    text = (title_text + " " + desc_text).lower()
    pos = sum(1 for k in pos_kw if k.lower() in text)
    neg = sum(1 for k in neg_kw if k.lower() in text)

    if pos > neg:
        conf = min(95, 50 + (pos - neg) * 20)
        return "positive", int(conf)
    elif neg > pos:
        conf = min(95, 50 + (neg - pos) * 20)
        return "negative", int(conf)
    else:
        return "neutral", 55


def update_pool(news_items, sources_meta):
    """更新sentiment_pool.json的news节"""
    pool = {}
    try:
        with open(POOL_FILE) as f:
            pool = json.load(f)
    except:
        pass

    # 为每条新闻打分
    enriched = []
    for item in news_items:
        sent, conf = simple_sentiment(item["title"], item.get("summary", ""))
        enriched.append({
            "source": item["source"],
            "title": item["title"],
            "url": item["url"],
            "published": item["published"],
            "summary": item["summary"],
            "sentiment": sent,
            "confidence": conf,
        })

    # 按published时间排序，取最新20条
    enriched.sort(key=lambda x: x["published"], reverse=True)
    enriched = enriched[:20]

    pool["news"] = {
        "items": enriched,
        "sources_meta": sources_meta,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(enriched),
    }

    # 全局情绪摘要
    if enriched:
        pos_n = sum(1 for x in enriched if x["sentiment"] == "positive")
        neg_n = sum(1 for x in enriched if x["sentiment"] == "negative")
        neutral_n = len(enriched) - pos_n - neg_n
        dominant = "positive" if pos_n > neg_n else "negative" if neg_n > pos_n else "neutral"
        pool["news"]["summary"] = {
            "dominant_sentiment": dominant,
            "positive_count": pos_n,
            "negative_count": neg_n,
            "neutral_count": neutral_n,
            "total": len(enriched),
        }

    with open(POOL_FILE, "w") as f:
        json.dump(pool, f, ensure_ascii=False, indent=2)

    print(f"  📰 已写入 {len(enriched)} 条新闻到 sentiment_pool.json")


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [新闻舆情] {msg}"
    print(line)
    try:
        import os
        os.makedirs(f"{EDICT_DATA}/logs", exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except:
        pass


if __name__ == "__main__":
    print("📰 钦天监·新闻舆情爬虫启动")
    news_items, sources_meta = fetch_all_news()
    if news_items:
        update_pool(news_items, sources_meta)
        log(f"完成: {len(news_items)}条 | 状态: {'/'.join([s['source'] for s in sources_meta if s['status']=='ok'])}")
    else:
        log("警告: 所有源均抓取失败")
