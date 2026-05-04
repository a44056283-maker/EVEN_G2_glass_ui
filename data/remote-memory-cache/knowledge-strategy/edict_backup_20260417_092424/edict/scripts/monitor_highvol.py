#!/usr/bin/env python3
"""
兵部 · 高波动币种监控脚本
监控对象：DOGE等高波动币种
数据源：OKX(bot 9093)/Binance(bot 9090)
"""

import json
import time
import logging
import sqlite3
from datetime import datetime, date
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [HIGHVOL] %(levelname)s %(message)s'
)
log = logging.getLogger('highvol')

WORKSPACE = Path(__file__).parent.parent
DATA_DIR = WORKSPACE / 'data'
DB_PATH = DATA_DIR / 'highvol.db'

# ---------- 波动率阈值 ----------
VOLATILITY_THRESHOLDS = {
    'DOGE': {'price_change_1h_pct': 3.0, 'price_change_24h_pct': 10.0, 'volume_spike': 3.0},
    'SOL':  {'price_change_1h_pct': 2.0, 'price_change_24h_pct': 8.0,  'volume_spike': 2.5},
    'BTC':  {'price_change_1h_pct': 1.0, 'price_change_24h_pct': 5.0,  'volume_spike': 2.0},
    'ETH':  {'price_change_1h_pct': 1.5, 'price_change_24h_pct': 7.0,  'volume_spike': 2.0},
}

HIGH_VOL_COINS = ['DOGE', 'SOL', 'PEPE', 'SHIB', 'XRP']  # 可扩展

ALERT_LOG = DATA_DIR / 'logs' / 'highvol_alerts.jsonl'
ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)


def init_db():
    """初始化SQLite数据库存储价格历史"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS price_history (
        coin TEXT, ts INTEGER, price REAL, volume REAL,
        price_change_1h REAL, price_change_24h REAL,
        PRIMARY KEY (coin, ts)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS volatility_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts INTEGER, coin TEXT, alert_type TEXT,
        price REAL, change_pct REAL, volume_ratio REAL,
        resolved INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()


def get_db_connection():
    return sqlite3.connect(DB_PATH)


def fetch_price_binance(symbol: str) -> dict:
    """从Binance获取价格数据（备用）"""
    try:
        import urllib.request
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}USDT"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
            return {
                'price': float(data['lastPrice']),
                'volume': float(data['volume']),
                'priceChange1h': 0,  # 24hr ticker无1h数据
                'priceChange24h': float(data['priceChangePercent']),
                'source': 'binance'
            }
    except Exception as e:
        log.warning(f"Binance {symbol} 获取失败: {e}")
        return None


def fetch_price_okx(inst_id: str) -> dict:
    """从OKX获取价格数据（主数据源 bot 9093）"""
    try:
        import urllib.request
        url = f"https://www.okx.com/api/v5/market/ticker?instId={inst_id}"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
            items = data.get('data', [])
            if not items:
                return None
            d = items[0]
            return {
                'price': float(d.get('last', 0)),
                'volume': float(d.get('vol24h', 0)),
                'priceChange24h': float(d.get('sodUtc0', 0)),
                'source': 'okx'
            }
    except Exception as e:
        log.warning(f"OKX {inst_id} 获取失败: {e}")
        return None


def fetch_price_simulated(symbol: str) -> dict:
    """模拟价格数据（无API访问时使用demo数据）"""
    import random
    base_prices = {'DOGE': 0.15, 'SOL': 140, 'BTC': 65000, 'ETH': 3500, 'PEPE': 0.00001}
    base_price = base_prices.get(symbol, 100)
    price = base_price * (1 + random.uniform(-0.05, 0.05))
    return {
        'price': round(price, 6 if base_price < 1 else 2),
        'volume': random.uniform(1e6, 1e8),
        'priceChange1h': random.uniform(-5, 5),
        'priceChange24h': random.uniform(-15, 15),
        'source': 'simulated'
    }


def get_price_data(symbol: str) -> dict:
    """综合获取价格：OKX -> Binance -> Simulated"""
    inst_id_map = {'DOGE': 'DOGE-USDT', 'BTC': 'BTC-USDT', 'ETH': 'ETH-USDT',
                   'SOL': 'SOL-USDT', 'PEPE': 'PEPE-USDT', 'SHIB': 'SHIB-USDT'}
    inst_id = inst_id_map.get(symbol, f'{symbol}-USDT')

    data = fetch_price_okx(inst_id)
    if not data:
        data = fetch_price_binance(symbol)
    if not data:
        log.info(f"{symbol}: 使用模拟数据")
        data = fetch_price_simulated(symbol)
    else:
        log.info(f"{symbol}: {data['source']} price={data['price']}")

    data['symbol'] = symbol
    data['ts'] = int(time.time())
    return data


def check_volatility(coin: str, current: dict, conn) -> list:
    """检查波动率是否超过阈值，返回告警列表"""
    alerts = []
    thresholds = VOLATILITY_THRESHOLDS.get(coin, {'price_change_1h_pct': 3.0, 'price_change_24h_pct': 12.0, 'volume_spike': 3.0})

    change_1h = current.get('priceChange1h', 0)
    change_24h = current.get('priceChange24h', 0)

    # 存储历史用于成交量 spike 检测
    ts = current['ts']
    price = current['price']
    volume = current['volume']

    prev = conn.execute(
        "SELECT volume FROM price_history WHERE coin=? ORDER BY ts DESC LIMIT 1",
        (coin,)
    ).fetchone()
    volume_ratio = 1.0
    if prev:
        volume_ratio = volume / max(prev[0], 1)

    # 1h价格变化告警
    if abs(change_1h) > thresholds['price_change_1h_pct']:
        level = "P0" if abs(change_1h) > thresholds['price_change_1h_pct'] * 2 else "P1"
        alerts.append({
            'ts': ts, 'coin': coin, 'alert_type': f'1h波动率{level}',
            'price': price, 'change_pct': change_1h, 'volume_ratio': volume_ratio,
            'message': f'🚨 {coin} 1小时波动 {change_1h:+.2f}%（阈值±{thresholds["price_change_1h_pct"]}%）'
        })

    # 24h价格变化告警
    if abs(change_24h) > thresholds['price_change_24h_pct']:
        level = "P0" if abs(change_24h) > thresholds['price_change_24h_pct'] * 1.5 else "P1"
        alerts.append({
            'ts': ts, 'coin': coin, 'alert_type': f'24h波动率{level}',
            'price': price, 'change_pct': change_24h, 'volume_ratio': volume_ratio,
            'message': f'🚨 {coin} 24小时波动 {change_24h:+.2f}%（阈值±{thresholds["price_change_24h_pct"]}%）'
        })

    # 成交量暴涨
    if volume_ratio > thresholds['volume_spike']:
        alerts.append({
            'ts': ts, 'coin': coin, 'alert_type': '成交量暴涨',
            'price': price, 'change_pct': change_24h, 'volume_ratio': volume_ratio,
            'message': f'📊 {coin} 成交量突增 {volume_ratio:.1f}x（阈值{thresholds["volume_spike"]}x）'
        })

    return alerts


def save_alert(alert: dict, conn):
    """保存告警到数据库和文件"""
    conn.execute(
        "INSERT INTO volatility_alerts (ts, coin, alert_type, price, change_pct, volume_ratio) VALUES (?,?,?,?,?,?)",
        (alert['ts'], alert['coin'], alert['alert_type'], alert['price'], alert['change_pct'], alert['volume_ratio'])
    )
    conn.commit()
    # 追加到告警日志
    with open(ALERT_LOG, 'a') as f:
        f.write(json.dumps(alert, ensure_ascii=False) + '\n')


def monitor_cycle():
    """一次监控循环"""
    log.info(f"=== 高波动监控开始 ===")
    conn = get_db_connection()
    all_alerts = []

    for coin in HIGH_VOL_COINS:
        data = get_price_data(coin)
        conn.execute(
            "INSERT OR REPLACE INTO price_history (coin, ts, price, volume, price_change_1h, price_change_24h) VALUES (?,?,?,?,?,?)",
            (coin, data['ts'], data['price'], data['volume'],
             data.get('priceChange1h', 0), data.get('priceChange24h', 0))
        )
        conn.commit()

        alerts = check_volatility(coin, data, conn)
        for a in alerts:
            save_alert(a, conn)
            all_alerts.append(a)
            log.warning(a['message'])

    conn.close()
    log.info(f"=== 监控完成，告警{len(all_alerts)}条 ===")
    return all_alerts


def main():
    init_db()
    mode = __import__('sys').argv[1] if len(__import__('sys').argv) > 1 else 'once'

    if mode == 'loop':
        interval = int(__import__('sys').argv[2]) if len(__import__('sys').argv) > 2 else 60
        log.info(f"启动循环监控，每{interval}秒一次")
        while True:
            monitor_cycle()
            time.sleep(interval)
    else:
        monitor_cycle()


if __name__ == '__main__':
    main()
