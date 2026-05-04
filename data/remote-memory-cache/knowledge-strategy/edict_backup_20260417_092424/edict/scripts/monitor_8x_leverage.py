#!/usr/bin/env python3
"""
兵部 · 8x杠杆专项监控脚本
监控对象：Gate.io bot 9092 8x杠杆仓位
告警：保证金率/强平价/杠杆倍数
"""

import json
import time
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [8X-LEVERAGE] %(levelname)s %(message)s'
)
log = logging.getLogger('8x')

WORKSPACE = Path(__file__).parent.parent
DATA_DIR = WORKSPACE / 'data'
REPORT_DIR = DATA_DIR / 'reports' / 'daily'

# ---------- 8x杠杆专项阈值 ----------
# 保证金率安全线
MARGIN_RATIO_WARNING = 1.30   # 警告：保证金率<130%
MARGIN_RATIO_CRITICAL = 1.15  # 严重：保证金率<115%（接近强平）
MARGIN_RATIO_LIQUIDATION = 1.10  # 立即告警

# 浮亏率
UNREALIZED_LOSS_WARNING = 0.30  # 警告：浮亏>30% of margin
UNREALIZED_LOSS_CRITICAL = 0.50  # 严重：浮亏>50% of margin

# 持仓集中度
CONCENTRATION_WARNING = 0.40  # 单币种保证金占总保证金>40%

ALERT_LOG = DATA_DIR / 'logs' / '8x_alerts.jsonl'
ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)

# ── ATR 动态止损配置 ──────────────────────────────────
ATR_PERIOD = 14              # ATR 计算周期
ATR_STOP_MULTIPLIER = 2.5     # ATR 止损倍数
ATR_WARNING_MULTIPLIER = 1.5 # ATR 警告倍数
ATR_LOOKBACK = 20            # 获取历史K线数量


def calculate_stop_by_atr(entry_price: float, atr: float, side: str = "LONG", 
                          stop_mult: float = ATR_STOP_MULTIPLIER) -> dict:
    """
    基于 ATR 计算动态止损价格
    
    Args:
        entry_price: 开仓价格
        atr: 当前 ATR 值
        side: 持仓方向 (LONG/SHORT)
        stop_mult: ATR 倍数
    
    Returns:
        dict: {
            'stop_price': 止损价格,
            'distance_pct': 距离开仓价的百分比,
            'atr_value': 使用的ATR值,
            'risk_reward': 风险收益比 (如果可计算)
        }
    """
    if atr <= 0 or entry_price <= 0:
        return {'stop_price': 0.0, 'distance_pct': 0.0, 'atr_value': atr, 'risk_reward': 0.0}
    
    if side == "LONG":
        # 多头止损：低于入场价
        stop_price = entry_price - (atr * stop_mult)
        distance_pct = ((entry_price - stop_price) / entry_price) * 100
    else:
        # 空头止损：高于入场价
        stop_price = entry_price + (atr * stop_mult)
        distance_pct = ((stop_price - entry_price) / entry_price) * 100
    
    return {
        'stop_price': round(stop_price, 4),
        'distance_pct': round(distance_pct, 2),
        'atr_value': round(atr, 4),
        'risk_reward': 0.0  # 需要 TP 价格才能计算
    }


def get_atr_from_price_history(symbol: str, period: int = ATR_PERIOD, 
                               lookback: int = ATR_LOOKBACK) -> float:
    """
    从价格历史计算 ATR
    简化版：基于波动率估算
    
    实际应该：
    1. 调用交易所 API 获取历史K线
    2. 计算 True Range
    3. 计算 ATR 均值
    """
    # 这里返回估算值，实际应从 API 获取真实数据
    # 简化估算：使用 1% 作为日均波动率基准
    try:
        # 尝试从 Gate.io API 获取
        import urllib.request
        url = f"https://api.gateio.ws/api/v4/futures/usdt/positions/{symbol}"
        # 实际项目中应该用历史K线计算ATR，这里返回估算
        return 0.0  # 需要真实数据源
    except:
        return 0.0


def calculate_position_atr_stop(position: dict) -> dict:
    """
    为单个仓位计算 ATR 止损建议
    
    Returns:
        dict: 止损建议或空 dict（无建议）
    """
    entry = position.get('entryPrice', 0)
    current = position.get('currentPrice', 0)
    side = position.get('direction', 'LONG')
    symbol = position.get('symbol', '')
    
    if entry <= 0 or current <= 0:
        return {}
    
    # 估算 ATR（简化版，实际应获取真实K线数据）
    # 这里基于价格波动估算
    volatility = abs(current - entry) / entry
    atr_estimate = volatility * entry * 0.3  # 简化为价格变化的30%
    
    if atr_estimate <= 0:
        return {}
    
    # 计算标准止损 (2.5x ATR)
    stop_info = calculate_stop_by_atr(entry, atr_estimate, side, ATR_STOP_MULTIPLIER)
    
    # 检查是否应该触发止损
    if side == "LONG" and current < stop_info['stop_price']:
        return {
            'type': 'ATR止损触发',
            'symbol': symbol,
            'stop_price': stop_info['stop_price'],
            'distance_pct': stop_info['distance_pct'],
            'atr_value': atr_estimate,
            'message': f"📉 [{symbol}] ATR止损触发！建议价格 {stop_info['stop_price']} (ATR {atr_estimate:.4f}×{ATR_STOP_MULTIPLIER})",
            'action': '建议触及ATR止损线，考虑平仓'
        }
    elif side == "SHORT" and current > stop_info['stop_price']:
        return {
            'type': 'ATR止损触发',
            'symbol': symbol,
            'stop_price': stop_info['stop_price'],
            'distance_pct': stop_info['distance_pct'],
            'atr_value': atr_estimate,
            'message': f"📈 [{symbol}] ATR止损触发！建议价格 {stop_info['stop_price']} (ATR {atr_estimate:.4f}×{ATR_STOP_MULTIPLIER})",
            'action': '建议触及ATR止损线，考虑平仓'
        }
    
    # 返回止损建议（未触发）
    return {
        'type': 'ATR止损建议',
        'symbol': symbol,
        'entry_price': entry,
        'stop_price': stop_info['stop_price'],
        'distance_pct': stop_info['distance_pct'],
        'atr_value': atr_estimate,
        'message': f"📊 [{symbol}] ATR止损建议: {stop_info['stop_price']} (距开仓 {stop_info['distance_pct']:.1f}%)",
        'action': f'波动率ATR止损线，建议设置 {stop_info["stop_price"]}'
    }


def load_positions_9092() -> list:
    """
    从兵部API (7891端口) 获取真实高杠杆(>=5x)仓位数据
    替换原有硬编码模拟数据
    """
    try:
        import urllib.request
        url = "http://127.0.0.1:7891/api/bingbu/positions"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
        
        positions = []
        for p in data.get('positions', []):
            lev = p.get('leverage', 0)
            if lev >= 5:  # 只取5x及以上的高杠杆仓位
                # 计算保证金率（如果有liquidation_price和current_price）
                liq_price = p.get('liquidation_price', 0)
                current_price = p.get('current_price', 0)
                entry_price = p.get('entry_price', 0)
                amount = p.get('amount', 0)
                side = p.get('side', 'UNKNOWN')
                unrealized = p.get('unrealized_pnl', 0)
                
                # 估算保证金 = 仓位价值 / 杠杆
                if entry_price and amount and lev:
                    position_value = entry_price * amount
                    estimated_margin = position_value / lev
                else:
                    estimated_margin = 0
                
                # 计算保证金率
                if estimated_margin > 0 and unrealized != 0:
                    margin_ratio = (estimated_margin + unrealized) / estimated_margin
                elif estimated_margin > 0:
                    margin_ratio = 1.0 + (unrealized / estimated_margin)
                else:
                    margin_ratio = 1.5  # 默认安全值
                
                # 计算距强平距离
                if liq_price > 0 and current_price > 0:
                    if side == 'LONG':
                        distance_pct = (liq_price / current_price - 1) if current_price > 0 else 0
                    else:  # SHORT
                        distance_pct = (1 - liq_price / current_price) if current_price > 0 else 0
                else:
                    distance_pct = 0.15  # 默认15%
                
                positions.append({
                    'bot': str(p.get('port', '?')),
                    'exchange': p.get('exchange', 'Unknown'),
                    'symbol': p.get('pair', '?').replace(':USDT', ''),
                    'direction': side,
                    'leverage': float(lev),
                    'volume': amount,
                    'entryPrice': entry_price,
                    'currentPrice': current_price,
                    'margin': estimated_margin,
                    'unrealizedPnl': unrealized,
                    'marginRatio': margin_ratio,
                    'liquidationPrice': liq_price,
                    'distanceToLiq': abs(distance_pct),
                    'ts': int(time.time())
                })
        
        if positions:
            log.info(f"从兵部API获取到 {len(positions)} 个高杠杆仓位")
        else:
            log.info("从兵部API获取到 0 个高杠杆仓位(>=5x)")
        return positions
        
    except Exception as e:
        log.error(f"从兵部API获取仓位失败: {e}，返回空列表")
        return []


def check_margin_ratio(position: dict) -> list:
    """检查保证金率"""
    alerts = []
    ratio = position['marginRatio']
    symbol = position['symbol']
    margin = position['margin']
    unrealized = position['unrealizedPnl']

    if ratio < MARGIN_RATIO_LIQUIDATION:
        alerts.append({
            'level': 'P0', 'type': '强平风险',
            'symbol': symbol, 'marginRatio': ratio,
            'message': f'🚨🚨🚨 [{symbol}] 保证金率 {ratio:.2%} 极低！接近强平价 {position["liquidationPrice"]}！立即处理！',
            'action': '建议立即减仓或追加保证金'
        })
    elif ratio < MARGIN_RATIO_CRITICAL:
        alerts.append({
            'level': 'P1', 'type': '保证金不足',
            'symbol': symbol, 'marginRatio': ratio,
            'message': f'🚨 [{symbol}] 保证金率 {ratio:.2%} 低于安全线({MARGIN_RATIO_CRITICAL:.2%})！浮亏${unrealized:.2f}',
            'action': '建议关注，准备追加保证金'
        })
    elif ratio < MARGIN_RATIO_WARNING:
        alerts.append({
            'level': 'P2', 'type': '保证金偏低',
            'symbol': symbol, 'marginRatio': ratio,
            'message': f'🟠 [{symbol}] 保证金率 {ratio:.2%} 偏低，注意浮亏累积',
            'action': '持续监控'
        })
    return alerts


def check_unrealized_loss(position: dict) -> list:
    """检查浮亏率"""
    alerts = []
    unrealized = position['unrealizedPnl']
    margin = position['margin']

    if unrealized < 0:
        loss_ratio = abs(unrealized) / margin
        if loss_ratio > UNREALIZED_LOSS_CRITICAL:
            return [{
                'level': 'P1', 'type': '浮亏过大',
                'symbol': position['symbol'],
                'message': f'🚨 [{position["symbol"]}] 浮亏 {loss_ratio:.1%} of 保证金，亏损${abs(unrealized):.2f}',
                'action': '建议减仓控制风险'
            }]
        elif loss_ratio > UNREALIZED_LOSS_WARNING:
            return [{
                'level': 'P2', 'type': '浮亏累积',
                'symbol': position['symbol'],
                'message': f'🟠 [{position["symbol"]}] 浮亏 {loss_ratio:.1%} of 保证金，注意盯盘',
                'action': '持续监控'
            }]
    return []


def check_concentration(positions: list) -> list:
    """检查持仓集中度"""
    alerts = []
    total_margin = sum(abs(p['margin']) for p in positions)
    if total_margin == 0:
        return alerts

    symbol_margins = {}
    for p in positions:
        sym = p['symbol']
        symbol_margins[sym] = symbol_margins.get(sym, 0) + abs(p['margin'])

    for sym, sym_margin in symbol_margins.items():
        ratio = sym_margin / total_margin
        if ratio > CONCENTRATION_WARNING:
            alerts.append({
                'level': 'P2', 'type': '持仓集中',
                'symbol': sym,
                'message': f'🟠 [{sym}] 保证金占比 {ratio:.1%}，超过{CONCENTRATION_WARNING:.0%}阈值',
                'action': '注意风险分散'
            })
    return alerts


def check_liquidation_distance(position: dict) -> list:
    """检查距强平价距离"""
    alerts = []
    current = position['currentPrice']
    liq = position['liquidationPrice']
    entry = position['entryPrice']
    direction = position['direction']

    if direction == 'LONG':
        distance_pct = (liq / current - 1) if current > 0 else 0
    else:
        distance_pct = (1 - liq / current) if current > 0 else 0

    if distance_pct < 0.05:  # 距离<5%
        alerts.append({
            'level': 'P0', 'type': '强平距离过近',
            'symbol': position['symbol'],
            'message': f'🚨 [{position["symbol"]}] 距强平仅 {distance_pct:.2%}！当前{current}，强平价{liq}',
            'action': '立即追加保证金或减仓！'
        })
    elif distance_pct < 0.10:  # 距离<10%
        alerts.append({
            'level': 'P1', 'type': '强平距离偏近',
            'symbol': position['symbol'],
            'message': f'🟠 [{position["symbol"]}] 距强平 {distance_pct:.2%}，注意风险',
            'action': '准备应对方案'
        })
    return alerts


def monitor_8x():
    """执行8x杠杆监控"""
    log.info("=== 8x杠杆监控开始 ===")
    positions = load_positions_9092()
    all_alerts = []

    log.info(f"当前8x仓位: {len(positions)}个")
    for p in positions:
        log.info(f"  {p['symbol']} {p['direction']} {p['leverage']}x margin={p['margin']:.2f} PnL={p['unrealizedPnl']:.2f} MR={p['marginRatio']:.2%}")

    for pos in positions:
        for check_fn in [check_margin_ratio, check_unrealized_loss, check_liquidation_distance]:
            alerts = check_fn(pos)
            for a in alerts:
                all_alerts.append({**a, 'bot': '9092', 'exchange': 'Gate.io'})
                log.warning(a['message'])

        # ATR 止损检查 (v2.0)
        atr_stop = calculate_position_atr_stop(pos)
        if atr_stop:
            all_alerts.append({**atr_stop, 'bot': '9092', 'exchange': 'Gate.io'})
            log.info(atr_stop['message'])

    # 集中度检查
    conc_alerts = check_concentration(positions)
    for a in conc_alerts:
        all_alerts.append({**a, 'bot': '9092', 'exchange': 'Gate.io'})
        log.warning(a['message'])

    # 保存告警
    if all_alerts:
        with open(ALERT_LOG, 'a') as f:
            for a in all_alerts:
                f.write(json.dumps({**a, 'ts': int(time.time())}, ensure_ascii=False) + '\n')

    log.info(f"=== 8x监控完成，告警{len(all_alerts)}条 ===")
    return all_alerts


def monitor_loop(interval: int = 60):
    """循环监控"""
    while True:
        monitor_8x()
        time.sleep(interval)


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'loop':
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 60
        log.info(f"启动8x杠杆循环监控，每{interval}秒")
        monitor_loop(interval)
    else:
        monitor_8x()
