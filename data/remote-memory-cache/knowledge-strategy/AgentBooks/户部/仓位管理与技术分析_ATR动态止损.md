# 仓位管理与技术分析 — 户部 — 2026-03-30

---

## 一、缠论分型识别

### 核心要点1：顶分型与底分型的定义

**顶分型**（上升趋势转弱信号）：
- 第1根K线高点 < 第2根K线高点
- 第2根K线高点 > 第3根K线高点
- 中间K线高点最高，表示多方力量在此衰竭

**底分型**（下降趋势转强信号）：
- 第1根K线低点 > 第2根K线低点
- 第2根K线低点 < 第3根K线低点
- 中间K线低点最低，表示空方力量在此衰竭

### 核心要点2：包含关系处理

两根相邻K线存在包含关系时（即一方的最高点/最低点在另一方范围内），需要取 extremas 的 extremas：
- 上升趋势中：取两根K线的高点最高、低点最高（向上合并）
- 下降趋势中：取两根K线的高点最低、低点最低（向下合并）

### Python实现

```python
def identify_fractals(klines):
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
    if len(klines) < 2:
        return klines
    merged = [klines[0]]
    for bar in klines[1:]:
        prev = merged[-1]
        if (prev['low'] <= bar['low'] <= prev['high'] and 
            prev['low'] <= bar['high'] <= prev['high']):
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

## 二、ATR动态止损

### 核心要点1：ATR的定义与计算

ATR（Average True Range）= 一定周期内真实波幅的平均值

**True Range (TR) 的计算**：
```
TR = max(当日高点 - 当日低点, 
         |当日高点 - 前一日收盘|,
         |当日低点 - 前一日收盘|)
```

**ATR = TR的N日简单移动平均**（默认N=14）

### 核心要点2：Python实现

```python
def calculate_atr(klines, period=14):
    tr_list = []
    for i in range(1, len(klines)):
        high = klines[i]['high']
        low = klines[i]['low']
        prev_close = klines[i-1]['close']
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
    if len(tr_list) < period:
        return None
    atr = sum(tr_list[-period:]) / period
    return atr
```

### 核心要点3：基于ATR的动态止损

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

```python
def calculate_stop_loss(entry_price, atr, direction='long', n=2):
    if direction == 'long':
        stop_loss = entry_price - n * atr
    else:
        stop_loss = entry_price + n * atr
    return stop_loss

def calculate_risk_reward(entry_price, atr, direction='long', n_loss=2, n_profit=3):
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

## 三、核心要点总结

1. **缠论分型是转折点识别的基础**：顶分型预示上升可能结束，底分型预示下降可能结束；识别分型前需先处理K线的包含关系

2. **ATR是动态止损的核心指标**：计算TR时需考虑跳空因素（取H-L、H-PC、L-PC三者最大值）；ATR = N日平均TR

3. **ATR止损公式**：
   - 做多止损 = 入场价 - N×ATR（N常用2~3）
   - ATR止损能适应不同波动性的币种，避免被正常波动扫出
