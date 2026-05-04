# 交易部学习笔记 — 仓位管理

> 学习日期：2026-03-30
> 岗位：账户经理
> 学习主题：技术分析（分型识别 + ATR止损）

---

## 📌 学习主题：技术分析

### 一、缠论分型识别

#### 核心要点1：顶分型与底分型的定义

**顶分型**（上升趋势转弱信号）：
```
第1根K线高点 < 第2根K线高点
第2根K线高点 > 第3根K线高点
```
- 中间K线高点最高，表示多方力量在此衰竭

**底分型**（下降趋势转强信号）：
```
第1根K线低点 > 第2根K线低点
第2根K线低点 < 第3根K线低点
```
- 中间K线低点最低，表示空方力量在此衰竭

#### 核心要点2：包含关系处理
两根相邻K线存在包含关系时（即一方的最高点/最低点在另一方范围内），需要取 extremas 的 extremas：
- 上升趋势中：取两根K线的高点最高、低点最高（向上合并）
- 下降趋势中：取两根K线的高点最低、低点最低（向下合并）

#### 核心要点3：Python实现分型识别

```python
def identify_fractals(klines):
    """
    识别K线序列中的分型
    klines: list of dict, 每根K线包含 high, low, open, close
    返回: list of {'type': 'top'|'bottom', 'index': int, 'price': float}
    """
    # 先处理包含关系
    processed = merge_inclusive_bars(klines)
    
    fractals = []
    for i in range(1, len(processed) - 1):
        prev = processed[i - 1]
        curr = processed[i]
        next_bar = processed[i + 1]
        
        # 顶分型：中间K线高点最高
        if curr['high'] > prev['high'] and curr['high'] > next_bar['high']:
            fractals.append({'type': 'top', 'index': i, 'price': curr['high']})
        
        # 底分型：中间K线低点最低
        if curr['low'] < prev['low'] and curr['low'] < next_bar['low']:
            fractals.append({'type': 'bottom', 'index': i, 'price': curr['low']})
    
    return fractals

def merge_inclusive_bars(klines):
    """处理K线的包含关系"""
    if len(klines) < 2:
        return klines
    
    merged = [klines[0]]
    for bar in klines[1:]:
        prev = merged[-1]
        
        # 判断是否存在包含关系
        if (prev['low'] <= bar['low'] <= prev['high'] and 
            prev['low'] <= bar['high'] <= prev['high']):
            # 向上合并：取高点最高、低点最高
            merged[-1] = {
                'high': max(prev['high'], bar['high']),
                'low': max(prev['low'], bar['low']),
                'open': prev['open'],
                'close': bar['close']
            }
        else:
            merged.append(bar)
    
    return merged
```

---

### 二、ATR动态止损

#### 核心要点1：ATR的定义与计算

ATR（Average True Range）= 一定周期内真实波幅的平均值

**True Range (TR) 的计算**：
```
TR = max(当日高点 - 当日低点, 
         |当日高点 - 前一日收盘|,
         |当日低点 - 前一日收盘|)
```

**ATR = TR的N日简单移动平均**（默认N=14）

#### 核心要点2：ATR的Python实现

```python
def calculate_atr(klines, period=14):
    """
    计算ATR指标
    klines: list of dict, 每根K线包含 high, low, close
    period: ATR计算周期，默认14
    """
    tr_list = []
    
    for i in range(1, len(klines)):
        high = klines[i]['high']
        low = klines[i]['low']
        prev_close = klines[i-1]['close']
        
        # True Range = max(H-L, |H-PC|, |L-PC|)
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        tr_list.append(tr)
    
    if len(tr_list) < period:
        return None
    
    # ATR = N日简单移动平均
    atr = sum(tr_list[-period:]) / period
    return atr

def calculate_atr_ema(klines, period=14):
    """使用EMA方式计算ATR（更灵敏）"""
    tr_list = []
    
    for i in range(1, len(klines)):
        high = klines[i]['high']
        low = klines[i]['low']
        prev_close = klines[i-1]['close']
        
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
    
    if len(tr_list) < period:
        return None
    
    # 使用EMA计算
    multiplier = 2 / (period + 1)
    atr = tr_list[0]
    
    for tr in tr_list[1:]:
        atr = (tr - atr) * multiplier + atr
    
    return atr
```

#### 核心要点3：基于ATR的动态止损

**止损公式**：
```
做多止损价 = 入场价 - N × ATR
做空止损价 = 入场价 + N × ATR
```

**N值选择建议**：
| 交易风格 | N值 | 适用场景 |
|---------|-----|---------|
| 短线交易 | 1.5~2 | 波动大的币种，追求灵敏 |
| 中线交易 | 2~3 | 通用设置，平衡盈亏比 |
| 长线交易 | 3~5 | 低波动或趋势行情 |

**动态调整**：
- 浮盈时可以将止损位上移至成本价附近（保本）
- 趋势强劲时，可将止损位调整为：入场价 ± 2ATR

```python
def calculate_stop_loss(entry_price, atr, direction='long', n=2):
    """
    根据ATR计算止损位
    entry_price: 入场价格
    atr: 当前ATR值
    direction: 'long' 做多, 'short' 做空
    n: ATR倍数，默认2
    """
    if direction == 'long':
        stop_loss = entry_price - n * atr
    else:
        stop_loss = entry_price + n * atr
    
    return stop_loss

def calculate_risk_reward(entry_price, atr, direction='long', n_loss=2, n_profit=3):
    """
    计算风险收益比
    n_loss: 止损ATR倍数
    n_profit: 止盈ATR倍数
    """
    if direction == 'long':
        stop_loss = entry_price - n_loss * atr
        take_profit = entry_price + n_profit * atr
    else:
        stop_loss = entry_price + n_loss * atr
        take_profit = entry_price - n_profit * atr
    
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)
    
    return {
        'stop_loss': stop_loss,
        'take_profit': take_profit,
        'risk': risk,
        'reward': reward,
        'ratio': reward / risk if risk > 0 else 0
    }
```

---

## 📊 今日核心要点总结

1. **缠论分型是转折点识别的基础**：顶分型预示上升可能结束，底分型预示下降可能结束；识别分型前需先处理K线的包含关系

2. **ATR是动态止损的核心指标**：计算TR时需考虑跳空因素（取H-L、H-PC、L-PC三者最大值）；ATR = N日平均TR

3. **ATR止损公式**：
   - 做多止损 = 入场价 - N×ATR（N常用2~3）
   - ATR止损能适应不同波动性的币种，避免被正常波动扫出

---

## 🔮 下次学习主题
- 支撑阻力位的识别与操作
- 趋势线与通道线的画法
