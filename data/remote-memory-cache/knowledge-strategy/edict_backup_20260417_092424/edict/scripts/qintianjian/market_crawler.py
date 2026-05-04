#!/usr/bin/env python3
"""
钦天监 · 市场数据爬虫（curl 版）
数据源：
  - Fear & Greed：alternative.me
  - 交易所资金费率：Binance / Gate.io（公开API）
  - BTC主导地位：CoinGecko
  - 合约清算：Coinglass
输出：edict/data/sentiment_pool.json（market节）
"""
import json
import sys
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 统一使用 curl HTTP 客户端（urllib/requests 在本机网络异常）
sys.path.insert(0, "/Users/luxiangnan/edict/scripts/qintianjian")
from curl_http import curl_json, curl_retry

EDICT_DATA = "/Users/luxiangnan/edict/data"
POOL_FILE  = f"{EDICT_DATA}/sentiment_pool.json"
LOG_FILE   = f"{EDICT_DATA}/logs/qintianjian.log"


def get_fear_greed():
    """Fear & Greed Index（重试2次）"""
    data = curl_retry("https://api.alternative.me/fng/", max_retries=2, timeout=8)
    if data:
        try:
            d = json.loads(data)
            item = d["data"][0]
            val = int(item["value"])
            label = item["value_classification"]
            ts = datetime.fromtimestamp(int(item["timestamp"])).strftime("%Y-%m-%d %H:%M")
            return {"value": val, "label": label, "timestamp": ts, "update_interval_hours": 8}
        except Exception:
            pass
    return None


def get_binance_funding():
    """Binance 永续合约资金费率 - 通过代理访问 fapi.binance.com"""
    data = curl_json("https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT", timeout=8, proxy=True)
    if data and isinstance(data, list) and len(data) > 0:
        try:
            item = data[0]
            rate = float(item.get("fundingRate", 0)) * 100
            return {"exchange": "Binance", "pair": "BTC/USDT", "funding_rate_pct": round(rate, 6)}
        except Exception:
            pass
    # 备用：获取前5合约费率
    data = curl_json("https://fapi.binance.com/fapi/v1/premiumIndex", timeout=8, proxy=True)
    if data and isinstance(data, list):
        try:
            results = []
            for item in data[:5]:
                sym = item.get("symbol", "")
                if sym.endswith("USDT"):
                    rate = float(item.get("lastFundingRate", 0)) * 100
                    pair = sym.replace("USDT", "/USDT")
                    results.append({"exchange": "Binance", "pair": pair, "funding_rate_pct": round(rate, 6)})
            return results if results else None
        except Exception:
            pass
    return None


def get_gateio_funding():
    """Gate.io 永续合约资金费率 - 通过tickers公开端点"""
    data = curl_json("https://api.gateio.ws/api/v4/futures/usdt/tickers", timeout=6)
    if data and isinstance(data, list):
        try:
            # 在tickers中找BTCUSDT合约
            for item in data:
                if item.get("contract") == "BTC_USDT":
                    rate = float(item.get("funding_rate", 0)) * 100
                    return {"exchange": "Gate.io", "pair": "BTC/USDT", "funding_rate_pct": round(rate, 6)}
            # 找不到BTC，找前5大合约的资金费率
            top_pairs = ["BTC_USDT", "ETH_USDT", "SOL_USDT"]
            results = []
            for item in data:
                c = item.get("contract", "")
                if c in top_pairs:
                    rate = float(item.get("funding_rate", 0)) * 100
                    pair = c.replace("_", "/")
                    results.append({"exchange": "Gate.io", "pair": pair, "funding_rate_pct": round(rate, 6)})
            return results if results else None
        except Exception:
            pass
    return None


def get_btc_dominance():
    """BTC市场主导地位 - CoinGecko（代理），备用Gate.io"""
    # 优先CoinGecko（通过代理）
    data = curl_json("https://api.coingecko.com/api/v3/global", timeout=8, proxy=True)
    if data and "data" in data:
        try:
            d = data["data"]
            return {
                "source": "CoinGecko",
                "btc_dominance_pct": d.get("market_cap_percentage", {}).get("btc", 0),
                "total_mcap": d.get("total_market_cap", {}).get("usd", 0),
                "total_24h_vol": d.get("total_volume", {}).get("usd", 0),
                "active_cryptos": d.get("active_cryptocurrencies", 0),
                "market_status": d.get("market_status", "open"),
            }
        except Exception:
            pass
    
    # 备用：通过Gate.io获取BTC价格和市值估算
    data = curl_json("https://api.gateio.ws/api/v4/spot/tickers?currency_pair=BTC_USDT", timeout=6)
    if data and isinstance(data, list) and len(data) > 0:
        try:
            btc_data = data[0]
            btc_price = float(btc_data.get("last", 0))
            btc_vol_24h = float(btc_data.get("volume", 0)) * btc_price
            # BTC市值 ≈ BTC价格 × 1980万流通量（估算）
            btc_mcap = btc_price * 19800000
            # 总市值估算（简化估算：BTC占比约50-60%）
            # 如果没有其他数据，用BTC数据估算
            if btc_mcap > 0:
                # 估算总市值 = BTC市值 / 估算占比
                est_total = btc_mcap / 0.55
                return {
                    "source": "Gate.io(估算)",
                    "btc_dominance_pct": round(btc_mcap / est_total * 100, 2) if est_total > 0 else 55,
                    "btc_price": btc_price,
                    "total_mcap": est_total,
                    "total_24h_vol": btc_vol_24h,
                }
        except Exception:
            pass
    return None


def get_coinglass_liquidations():
    """Coinglass 清算数据 - 通过代理访问"""
    data = curl_json("https://open-api.coinglass.com/public/v2/bitcoin_liquidation_zones", timeout=8, proxy=True)
    if data and "data" in data:
        try:
            zones = data["data"][:5]
            return {
                "status": "ok",
                "zones_count": len(zones),
                "top_zones": [{"price": z.get("price"), "side": z.get("side"), "total": z.get("total")} for z in zones],
            }
        except Exception:
            pass
    
    # 备用：通过Binance获取合约持仓量来估算
    # Binance永续合约持仓量（备用方案）
    return {"status": "unavailable", "note": "Coinglass API暂不可用"}


def sentiment_from_funding_and_fg(fg, funding_list):
    """综合资金费率和FG生成简易情绪"""
    fg_val = fg["value"] if fg else 50
    if fg_val <= 25:
        fg_sent = "极度恐慌"
    elif fg_val <= 45:
        fg_sent = "恐慌"
    elif fg_val <= 55:
        fg_sent = "中性"
    elif fg_val <= 75:
        fg_sent = "贪婪"
    else:
        fg_sent = "极度贪婪"

    score = fg_val
    for f in funding_list:
        rate = f.get("funding_rate_pct", 0)
        if rate > 0.1:
            score -= (rate - 0.05) * 30
        elif rate < -0.1:
            score += (-rate - 0.05) * 30

    score = max(0, min(100, int(score)))

    return {
        "composite_score": score,
        "fear_greed": fg_sent,
        "interpretation": "多头市场" if score > 60 else "空头市场" if score < 40 else "中性",
    }


def update_pool(market_data):
    pool = {}
    try:
        with open(POOL_FILE) as f:
            pool = json.load(f)
    except Exception:
        pass
    pool["market"] = {**market_data, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    with open(POOL_FILE, "w") as f:
        json.dump(pool, f, ensure_ascii=False, indent=2)
    print(f"  📊 已写入市场数据")


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [市场数据] {msg}"
    print(line)
    try:
        import os
        os.makedirs(f"{EDICT_DATA}/logs", exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    print("📊 钦天监·市场数据爬虫启动")

    # 并发抓取所有数据源（各自独立，互不阻塞）
    results = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {
            ex.submit(get_fear_greed): ("Fear&Greed", "fg"),
            ex.submit(get_binance_funding): ("Binance资金费率", "binance"),
            ex.submit(get_gateio_funding): ("Gate.io资金费率", "gateio"),
            ex.submit(get_btc_dominance): ("BTC主导", "btc_dom"),
            ex.submit(get_coinglass_liquidations): ("清算数据", "liq"),
        }
        for future in as_completed(futures, timeout=30):
            name, key = futures[future]
            try:
                results[key] = future.result(timeout=5)
                icon = "✅" if results[key] else "❌"
                print(f"  {icon} {name}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                results[key] = None

    fg = results.get("fg")
    funding_list = [f for f in [results.get("binance"), results.get("gateio")] if f]
    btc_dom = results.get("btc_dom")
    liq = results.get("liq")

    if fg:
        print(f"  FG值: {fg['value']} - {fg['label']}")
    if btc_dom:
        mcap_t = btc_dom.get("total_mcap", 0) / 1e12
        print(f"  BTC主导: {btc_dom.get('btc_dominance_pct', 0)}% | 总市值: ${mcap_t:.2f}T")

    market_sent = sentiment_from_funding_and_fg(fg, funding_list)

    market_data = {
        "fear_greed": fg,
        "funding_rates": funding_list,
        "btc_dominance": btc_dom,
        "liquidations": liq,
        "sentiment_analysis": market_sent,
    }

    update_pool(market_data)

    fund_str = ", ".join([f"{f['exchange']}:{f['funding_rate_pct']}%" for f in funding_list]) if funding_list else "N/A"
    log(f"完成 | FG={fg['value'] if fg else 'N/A'} | 费率={fund_str} | 情绪:{market_sent['interpretation']}({market_sent['composite_score']})")
