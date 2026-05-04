#!/usr/bin/env python3
"""
edict · 市场数据获取脚本
数据源：
  - A股 / 港股：腾讯行情 API (qt.gtimg.cn)
  - BTC/USD：CoinGecko 公开 API
支持格式：A股(600519.SS)、港股(0700.HK)、美股(AAPL)、BTC(BTC-USD)
输出：JSON格式 {symbol, price, change_pct, volume} 或 {error: ...}
依赖：python3, curl（系统自带）
"""
import subprocess
import json
import sys
import re
from datetime import datetime

PROXY = "http://127.0.0.1:5020"


def curl_get(url: str, timeout: int = 10, headers: dict = None, proxy: bool = False) -> str | None:
    """使用 curl GET，返回 str 或 None（urllib/requests 在本机网络异常）
    
    注意：腾讯行情 API 返回 GBK 编码，必须用二进制模式 + 手动解码
    """
    h_args = []
    if headers:
        for k, v in headers.items():
            h_args += ["-H", f"{k}: {v}"]
    h_args += ["-H", "Accept: application/json, text/xml, */*"]

    cmd = [
        "curl", "-s", "--max-time", str(timeout), "-A",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    ]
    if proxy:
        cmd += ["-x", PROXY]
    cmd += h_args + [url]

    try:
        # 用二进制模式避免 GBK/UTF-8 解码冲突，手动处理编码
        r = subprocess.run(cmd, capture_output=True, timeout=timeout + 3)
        if r.returncode == 0 and r.stdout:
            # 优先尝试 GBK（腾讯行情），回退 UTF-8
            try:
                return r.stdout.decode("gbk")
            except UnicodeDecodeError:
                return r.stdout.decode("utf-8", errors="replace")
        return None
    except Exception:
        return None


def curl_json(url: str, timeout: int = 10, proxy: bool = False) -> dict | None:
    """curl GET 并解析 JSON"""
    text = curl_get(url, timeout=timeout, proxy=proxy)
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


# ─── A股 / 港股解析 ───────────────────────────────────────────

def _parse_tencent_a_stock(raw: str) -> dict | None:
    """
    腾讯行情 A股格式 (sh600519):
    v_sh600519="1~股票名~代码~当前价~昨收~今开~成交量(手)~外盘~内盘~
                当前价~买一价~买一量(手)~...~时间戳~涨跌额~涨跌幅~
                最高~最低~成交额~..."
    索引:  0   1     2    3     4    5    6      7    8
           9   10    11   ...  30   31   32      33   34   35   36   37
    """
    try:
        # 去掉 v_xxxx="..." 包裹
        m = re.search(r'="([^"]+)"', raw)
        if not m:
            return None
        fields = m.group(1).split("~")
        if len(fields) < 38:
            return None

        price    = float(fields[3])   # 当前价
        prev_c   = float(fields[4])   # 昨收
        volume   = float(fields[6])   # 成交量（手）
        change   = float(fields[31])  # 涨跌额
        change_pct = float(fields[32])  # 涨跌幅%
        high     = float(fields[33])  # 最高
        low      = float(fields[34])  # 最低
        amount   = float(fields[37])  # 成交额（元）
        sym      = fields[2].strip()  # 600519

        return {
            "symbol":     f"{sym}.SS",
            "price":      round(price, 2),
            "prev_close": round(prev_c, 2),
            "open":       round(float(fields[5]), 2),
            "high":       round(high, 2),
            "low":        round(low, 2),
            "change":     round(change, 2),
            "change_pct": round(change_pct, 2),
            "volume":     int(volume * 100),   # 转为股
            "amount":     round(amount, 2),
            "market":     "A-share",
            "currency":   "CNY",
            "timestamp":  datetime.now().isoformat(),
        }
    except Exception as e:
        return None


def _parse_tencent_hk_stock(raw: str) -> dict | None:
    """
    腾讯行情 港股格式 (hk00700):
    v_hk00700="100~名称~代码~当前价~昨收~今开~成交量(股)~
               ...~涨跌额~涨跌幅~52周最高~52周最低~..."
    索引:  0   1     2    3     4    5    6      ...  31   32   33   34
    """
    try:
        m = re.search(r'="([^"]+)"', raw)
        if not m:
            return None
        fields = m.group(1).split("~")
        if len(fields) < 39:
            return None

        price      = float(fields[3])   # 当前价
        prev_c     = float(fields[4])   # 昨收
        open_p     = float(fields[5])   # 今开
        volume     = float(fields[6])   # 成交量（股）
        change     = float(fields[31])  # 涨跌额
        change_pct = float(fields[32])  # 涨跌幅%
        # fields[33]=52w_high, fields[34]=52w_low（非今日高低）
        # 港股腾讯行情不直接提供今日OHLC，标记为null
        sym        = fields[2].strip()  # 00700

        return {
            "symbol":     f"{sym}.HK",
            "price":      round(price, 2),
            "prev_close": round(prev_c, 2),
            "open":       round(open_p, 2),
            "high":       None,        # 港股腾讯行情不提供今日最高
            "low":        None,        # 港股腾讯行情不提供今日最低
            "change":     round(change, 2),
            "change_pct": round(change_pct, 2),
            "volume":     int(volume),
            "market":     "HK",
            "currency":   "HKD",
            "note":       "high/low由腾讯行情不提供，标注为null",
            "timestamp":  datetime.now().isoformat(),
        }
    except Exception as e:
        return None


# ─── CoinGecko BTC ─────────────────────────────────────────────

def _fetch_btc() -> dict:
    """通过 CoinGecko 获取 BTC-USD 行情（代理）"""
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true&include_24hr_vol=true"
    data = curl_json(url, timeout=10, proxy=True)
    if not data or "bitcoin" not in data:
        return {"error": "CoinGecko API unavailable"}

    btc = data["bitcoin"]
    price      = btc.get("usd", 0)
    change_pct = btc.get("usd_24h_change", 0)
    volume_24h = btc.get("usd_24h_vol", 0)

    return {
        "symbol":     "BTC-USD",
        "price":      round(price, 2),
        "change_pct": round(change_pct, 2),
        "volume_24h": round(volume_24h, 2),
        "market":     "Crypto",
        "currency":   "USD",
        "source":     "CoinGecko",
        "timestamp":  datetime.now().isoformat(),
    }


# ─── 主查询函数 ────────────────────────────────────────────────

def fetch_market_data(symbol: str) -> dict:
    """
    查询单个标的行情，返回标准化 dict。
    支持格式：
      600519.SS / 600519  → A股（腾讯行情 sh 前缀）
      0700.HK             → 港股（腾讯行情 hk 前缀）
      AAPL                → 美股（暂不支持，返回 error）
      BTC-USD             → BTC（CoinGecko）
    """
    symbol = symbol.strip().upper()

    # A股
    if symbol.endswith(".SS") or (symbol.isdigit() and len(symbol) == 6):
        code = symbol.replace(".SS", "")
        url = f"https://qt.gtimg.cn/q=sh{code}"
        raw = curl_get(url, timeout=10, headers={"Referer": "https://finance.qq.com"})
        if not raw:
            return {"symbol": symbol, "error": "网络请求失败（A股）"}
        result = _parse_tencent_a_stock(raw)
        if not result:
            return {"symbol": symbol, "error": "数据解析失败（A股）"}
        return result

    # 港股
    if symbol.endswith(".HK") or (symbol.startswith("0") and len(symbol) == 5):
        code = symbol.replace(".HK", "").lstrip("0") or "0"  # "0700" → "700"
        code = code.zfill(5)  # "700" → "00700"
        url = f"https://qt.gtimg.cn/q=hk{code}"
        raw = curl_get(url, timeout=10, headers={"Referer": "https://finance.qq.com"})
        if not raw:
            return {"symbol": symbol, "error": "网络请求失败（港股）"}
        result = _parse_tencent_hk_stock(raw)
        if not result:
            return {"symbol": symbol, "error": "数据解析失败（港股）"}
        return result

    # BTC
    if symbol == "BTC-USD" or symbol == "BTC":
        return _fetch_btc()

    # 暂不支持美股
    return {"symbol": symbol, "error": f"不支持的市场类型: {symbol}，仅支持 A股(.SS)、港股(.HK)、BTC-USD"}


def fetch_batch(symbols: list[str]) -> list[dict]:
    """批量查询，返回结果列表"""
    return [fetch_market_data(s) for s in symbols]


# ─── CLI 入口 ─────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        # 默认查询演示
        symbols = ["600519.SS", "0700.HK", "BTC-USD"]
    else:
        symbols = sys.argv[1:]

    results = fetch_batch(symbols)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
