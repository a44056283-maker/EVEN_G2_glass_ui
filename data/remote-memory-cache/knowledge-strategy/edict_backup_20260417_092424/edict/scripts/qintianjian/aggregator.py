#!/usr/bin/env python3
"""
钦天监 · 统一舆情聚合调度器
- 并发执行所有子爬虫（互不阻塞）
- 各模块独立超时，失败不影响整体
- 重试机制（社区模块最容易超时）
"""
import subprocess
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = "/Users/luxiangnan/edict/scripts/qintianjian"
POOL_FILE = "/Users/luxiangnan/edict/data/sentiment_pool.json"
LOG_FILE = "/Users/luxiangnan/edict/data/logs/qintianjian.log"

# 各模块超时时间（秒）
CRAWLER_TIMEOUT = {
    "news": 40,     # 新闻源多，可能需要较长时间
    "market": 25,    # 市场数据已优化，快速
    "community": 20,  # Reddit/Nitter被屏蔽，快速失败
}

# 各模块重试次数
CRAWLER_RETRIES = {
    "news": 0,       # news已有内置重试
    "market": 0,     # market已并发
    "community": 0,  # Reddit/Nitter 已有内置退避
}

CRAWLERS = {
    "news": f"{SCRIPT_DIR}/news_crawler.py",
    "market": f"{SCRIPT_DIR}/market_crawler.py",
    "community": f"{SCRIPT_DIR}/community_crawler.py",
}

# 全局日志记录器
logger = logging.getLogger("aggregator")


def log(msg, level="info"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [聚合调度] {msg}"
    getattr(logger, level)(line)
    print(line)


def run_crawler(name: str, path: str, timeout: int = 20, retries: int = 0) -> bool:
    """执行爬虫，带超时和重试"""
    last_err = None
    for attempt in range(retries + 1):
        try:
            r = subprocess.run(
                ["python3", path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if r.returncode == 0:
                ok = True
                status = "成功"
            else:
                ok = False
                status = f"失败({r.returncode})"
                last_err = r.stderr[:150] if r.stderr else ""
            icon = "✅" if ok else "❌"
            print(f"  {icon} {name}: {status}" + (f"\n     {last_err}" if last_err else ""))
            return ok
        except subprocess.TimeoutExpired:
            last_err = "超时"
            print(f"  ⏱️  {name}: 超时({timeout}s)" + (f" 重试({attempt+1}/{retries+1})" if attempt < retries else ""))
            if attempt < retries:
                import time
                time.sleep(2)  # 重试前等2秒
        except Exception as e:
            last_err = str(e)
            print(f"  ❌ {name}: {e}")
            return False
    print(f"  ❌ {name}: 最终失败 - {last_err}")
    return False


def run_all_crawlers_concurrent() -> dict:
    """并发执行所有爬虫，返回各模块结果"""
    results = {}

    def safe_run(name: str, path: str):
        timeout = CRAWLER_TIMEOUT.get(name, 20)
        retries = CRAWLER_RETRIES.get(name, 0)
        ok = run_crawler(name, path, timeout=timeout, retries=retries)
        return name, ok

    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {
            ex.submit(safe_run, name, path): name
            for name, path in CRAWLERS.items()
        }

        for future in as_completed(futures, timeout=60):
            try:
                name, ok = future.result(timeout=5)
                results[name] = ok
            except Exception as e:
                name = futures[future]
                print(f"  ❌ {name}: 并发执行异常 - {e}")
                results[name] = False

    return results


def aggregate():
    """综合三个数据源，生成干预决策信号"""
    try:
        with open(POOL_FILE) as f:
            pool = json.load(f)
    except Exception as e:
        print(f"  ⚠️  读取信号池失败: {e}")
        pool = {}

    news_items = pool.get("news", {}).get("items", [])
    market = pool.get("market", {})
    community = pool.get("community", {})
    fear_greed = market.get("fear_greed") or community.get("fear_greed") or {}

    # ── 综合打分 ─────────────────────────────────
    scores = []
    reasons = []

    # 1. Fear & Greed 权重
    fg_val = fear_greed.get("value", 50)
    if fg_val <= 20:
        scores.append(-30)
        reasons.append(f"Fear&Greed极低({fg_val})")
    elif fg_val <= 35:
        scores.append(-15)
        reasons.append(f"Fear&Greed低({fg_val})")
    elif fg_val >= 75:
        scores.append(20)
        reasons.append(f"Fear&Greed高({fg_val})")

    # 2. 市场情绪分析
    mkt_sent = market.get("sentiment_analysis", {})
    if mkt_sent:
        comp = mkt_sent.get("composite_score", 50)
        if comp < 30:
            scores.append(-20)
            reasons.append(f"综合市场情绪极弱({comp})")
        elif comp > 70:
            scores.append(15)
            reasons.append(f"综合市场情绪强({comp})")

    # 3. 新闻情绪
    news_summary = pool.get("news", {}).get("summary", {})
    neg_news = news_summary.get("negative_count", 0)
    pos_news = news_summary.get("positive_count", 0)
    if neg_news > pos_news + 3:
        scores.append(-15)
        reasons.append(f"利空新闻较多({neg_news} vs {pos_news})")
    elif pos_news > neg_news + 3:
        scores.append(10)
        reasons.append(f"利好新闻较多({pos_news} vs {neg_news})")

    # 4. 社区情绪（容错处理）
    try:
        comm_sent = community.get("sentiment_analysis", {})
        if comm_sent.get("sentiment") == "negative" and comm_sent.get("confidence", 0) > 70:
            scores.append(-10)
            reasons.append("社区情绪偏空")
        elif comm_sent.get("sentiment") == "positive" and comm_sent.get("confidence", 0) > 70:
            scores.append(8)
            reasons.append("社区情绪偏多")
    except Exception:
        pass

    # ── 技术面因子（融合资金流 + 支撑压力 + 持仓方向）───────────────
    tech_scores = []
    tech_reasons = []
    try:
        cache_file = "/Users/luxiangnan/edict/data/qintianjian_cache.json"
        cache = json.loads(open(cache_file).read()) if Path(cache_file).exists() else {}
    except Exception:
        cache = {}

    # 1. D指标（币安多空指标，>60偏多，<40偏空）
    d_val = cache.get("btc_d", 50)
    if d_val >= 65:
        tech_scores.append(25)
        tech_reasons.append(f"D指标强势({d_val:.1f})")
    elif d_val >= 55:
        tech_scores.append(10)
        tech_reasons.append(f"D指标偏多({d_val:.1f})")
    elif d_val <= 35:
        tech_scores.append(-25)
        tech_reasons.append(f"D指标弱势({d_val:.1f})")
    elif d_val <= 45:
        tech_scores.append(-10)
        tech_reasons.append(f"D指标偏空({d_val:.1f})")

    # 2. 持仓多空力量（来自当前账户真实持仓）
    positions = cache.get("all_positions", [])
    long_pnl = 0.0
    short_pnl = 0.0
    for p in positions:
        if p.get("is_short"):
            short_pnl += p.get("pnl_pct", 0)
        else:
            long_pnl += p.get("pnl_pct", 0)
    net_pnl = long_pnl - short_pnl
    if net_pnl >= 5:
        tech_scores.append(15)
        tech_reasons.append(f"多头强势(netovernight+{net_pnl:.1f}%)")
    elif net_pnl <= -5:
        tech_scores.append(-15)
        tech_reasons.append(f"空头强势(net{net_pnl:.1f}%)")

    # 3. 24h价格位置（当前价在高低点区间位置）
    btc_price_data = cache.get("btc_price") or {}
    price = btc_price_data.get("price", 0)
    high_24 = btc_price_data.get("high_24h", 0)
    low_24 = btc_price_data.get("low_24h", 0)
    if high_24 > low_24 > 0:
        pos_in_range = (price - low_24) / (high_24 - low_24) * 100  # 0%=接近低点，100%=接近高点
        if pos_in_range >= 70:
            tech_scores.append(8)
            tech_reasons.append(f"24h价格偏高位置({pos_in_range:.0f}%)")
        elif pos_in_range <= 30:
            tech_scores.append(-8)
            tech_reasons.append(f"24h价格偏低位置({pos_in_range:.0f}%)")

    # 4. 均线 + K线趋势（MA排列 + 最近20根K线方向）
    klines = cache.get("btc_klines", [])
    if len(klines) >= 20:
        closes = [k["c"] for k in klines[-20:] if k.get("c")]
        if len(closes) >= 20:
            ma5 = sum(closes[-5:]) / 5
            ma10 = sum(closes[-10:]) / 10
            ma20 = sum(closes[-20:]) / 20
            recent_trend = (closes[-1] - closes[0]) / closes[0] * 100  # 最近20根K线涨跌幅
            # 均线多头排列（价格 > MA5 > MA10 > MA20）= 上升趋势
            if price > ma5 > ma10 > ma20:
                tech_scores.append(15)
                tech_reasons.append("均线多头排列(强势上升)")
            elif price < ma5 < ma10 < ma20:
                tech_scores.append(-15)
                tech_reasons.append("均线空头排列(强势下降)")
            # 最近20根K线方向
            if recent_trend >= 3:
                tech_scores.append(8)
                tech_reasons.append(f"短线强势({recent_trend:+.2f}%)")
            elif recent_trend <= -3:
                tech_scores.append(-8)
                tech_reasons.append(f"短线弱势({recent_trend:+.2f}%)")

    # 技术面综合得分
    tech_total = sum(tech_scores)
    tech_reasons_str = " | ".join(tech_reasons) if tech_reasons else "无明显技术信号"

    # ── 综合最终信号 ─────────────────────────────────────────────────
    sentiment_score = sum(scores)
    total_score = sentiment_score + tech_total
    urgency = 0

    if fg_val <= 10:
        urgency = 10
    elif fg_val <= 20:
        urgency = 8
    elif fg_val <= 30:
        urgency = 6

    if total_score <= -40:
        direction = "SHORT"
        signal = "做空/极度恐慌"
        confidence = min(95, abs(total_score) + 20)
        action = "freeze"
        black_swan = fg_val <= 15
        black_swan_cats = ["市场恐慌"] if fg_val <= 15 else []
    elif total_score <= -20:
        direction = "SHORT"
        signal = "做空/恐慌"
        confidence = min(90, abs(total_score) + 30)
        action = "watch"
        black_swan = fg_val <= 20
        black_swan_cats = ["局部恐慌"] if fg_val <= 20 else []
    elif total_score >= 20:
        direction = "LONG"
        signal = "做多"
        confidence = min(90, total_score + 30)
        action = "long"
        black_swan = False
        black_swan_cats = []
    else:
        direction = "NEUTRAL"
        signal = "观望/缩量横盘"
        confidence = 50 + abs(total_score)
        action = "watch"
        black_swan = False
        black_swan_cats = []

    composite = {
        "direction": direction,
        "signal": signal,
        "confidence": confidence,
        "urgency": urgency,
        "action": action,
        "total_score": total_score,
        "sentiment_score": sentiment_score,
        "tech_score": tech_total,
        "reasons": reasons,
        "tech_reasons": tech_reasons,
        "black_swan_alert": black_swan,
        "black_swan_categories": black_swan_cats,
        "fear_greed_value": fg_val,
        "fear_greed_label": fear_greed.get("label", "Unknown"),
        "news_summary": news_summary,
        "market_sentiment": mkt_sent,
        "community_sentiment": comm_sent if 'comm_sent' in dir() else {},
        "top_news": [
            {"title": n["title"], "url": n["url"], "sentiment": n.get("sentiment")}
            for n in news_items[:5]
        ],
        "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 写入主信号文件
    out_file = "/Users/luxiangnan/.sentiment_latest.json"
    try:
        with open(out_file, "w") as f:
            json.dump(composite, f, ensure_ascii=False, indent=2)
        print(f"  ✅ 聚合信号已写入 {out_file}")
        print(f"     信号:{signal} | 方向:{direction} | 信心:{confidence} | 紧急度:{urgency}")
        print(f"     情绪分:{sentiment_score}({' '.join(reasons) if reasons else '无'})")
        print(f"     技术分:{tech_total}({tech_reasons_str})")
    except Exception as e:
        print(f"  ❌ 信号写入失败: {e}")

    return composite


if __name__ == "__main__":
    print(f"🔮 钦天监·统一聚合调度启动 ({datetime.now().strftime('%H:%M:%S')})")

    # 并发执行所有爬虫
    results = run_all_crawlers_concurrent()

    print(f"\n聚合结果: news={'✅' if results.get('news') else '❌'} "
          f"market={'✅' if results.get('market') else '❌'} "
          f"community={'✅' if results.get('community') else '❌'}")

    composite = aggregate()

    log(f"完成 | 信号:{composite['signal']} | 方向:{composite['direction']} | "
        f"黑天鹅:{composite['black_swan_alert']} | 理由:{', '.join(composite['reasons'])}")
