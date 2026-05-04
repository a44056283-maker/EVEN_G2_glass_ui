# 凯利公式与ATR动态止损 — 实战指南
> 版本：v1.0 | 更新：2026-04-04 | 作者：天禄
> 来源：太子自学（户部交易部内训）
> 定位：开仓前必读的核心武器

---

## 一、凯利公式（Kelly Criterion）

### 1.1 标准公式

```
f* = (p × b - q) / b

其中：
f* = 最优仓位比例（0-1）
p = 胜率（盈利概率）
q = 1 - p（亏损概率）
b = 盈亏比（avg_win / avg_loss）
```

### 1.2 交易简化版

```
f* = (W - (1-W)/R) / R

其中：
W = 胜率（win rate）
R = 盈亏比（reward/risk ratio）
```

### 1.3 实战计算流程

```
Step 1: 确定你的历史数据
  - W = 近100笔交易的胜率
  - R = 近100笔交易的平均盈亏比

Step 2: 代入公式计算
  f* = (W - (1-W)/R) / R

Step 3: 取半凯利（实际执行上限）
  实际仓位上限 = f* × 50%

Step 4: 对比账户限制
  账户限制 = 单笔风险上限（如2%账户）
```

### 1.4 Python实现

```python
def kelly_position(win_rate: float, reward_risk: float, capital: float, risk_pct: float = 0.02) -> dict:
    """
    凯利公式 + ATR 仓位计算

    Args:
        win_rate: 胜率 (0-1)
        reward_risk: 盈亏比 (R)
        capital: 总账户资金
        risk_pct: 单笔风险比例 (默认2%)

    Returns:
        完整仓位建议
    """
    W = win_rate
    R = reward_risk
    q = 1 - W

    # 全凯利
    kelly_full = (W * R - q) / R

    # 半凯利（实盘推荐）
    kelly_half = max(0, kelly_full) / 2

    # 风险预算限制
    max_risk_amount = capital * risk_pct

    # 账户限制的仓位上限
    capital_limit = 0.10  # 最大10%账户

    # 取最小值
    recommended_pct = min(kelly_half, capital_limit)

    result = {
        "win_rate": W,
        "reward_risk": R,
        "kelly_full": f"{max(0, kelly_full)*100:.1f}%",
        "kelly_half": f"{kelly_half*100:.1f}%",
        "recommended_pct": f"{recommended_pct*100:.1f}%",
        "recommended_amount": f"${capital * recommended_pct:.2f}",
        "max_risk_amount": f"${max_risk_amount:.2f}",
        "signal": "开仓" if kelly_half > 0 else "观望",
        "confidence": "高" if kelly_half > 0.05 else ("中" if kelly_half > 0 else "低")
    }
    return result

# 示例：户部当前数据（胜率61.3%，假设盈亏比1.5）
result = kelly_position(win_rate=0.613, reward_risk=1.5, capital=10000)
print(result)
# kelly_full = (0.613*1.5 - 0.387) / 1.5 = 38.2%
# kelly_half = 19.1%
# recommended = 10% (capital limit)
```

### 1.5 快速对照表

| 胜率 W | 盈亏比 R | 全凯利 | 半凯利 | 实盘建议 |
|--------|---------|--------|--------|---------|
| 0.35 | 2.0 | 17.5% | 8.8% | 8% |
| 0.40 | 2.0 | 25.0% | 12.5% | 10% |
| 0.45 | 1.5 | 23.3% | 11.7% | 10% |
| 0.50 | 1.5 | 33.3% | 16.7% | 15% |
| 0.55 | 1.5 | 43.3% | 21.7% | 15% |
| 0.60 | 1.5 | 53.3% | 26.7% | 15% |
| 0.613 | 1.5 | 56.3% | 28.2% | 15% |

> ⚠️ **高波动币圈建议用1/4凯利或更低**，全凯利在币圈容易爆仓

---

## 二、ATR动态止损

### 2.1 ATR定义

ATR（Averaged True Range）= N日真实波幅的移动平均

**True Range (TR)**：
```
TR = max(H-L, |H-PC|, |L-PC|)

其中：
H = 当日最高价
L = 当日最低价
PC = 前一日收盘价
```

### 2.2 ATR止损公式

```
做多止损 = 入场价 - (N × ATR)
做空止损 = 入场价 + (N × ATR)

做多止盈 = 入场价 + (M × ATR)  [M通常=2N，给2:1盈亏比]
做空止盈 = 入场价 - (M × ATR)
```

**N的经验值：**
| 策略类型 | ATR倍数 | 适用场景 |
|---------|---------|---------|
| 短线（日内） | 1.5-2×ATR | 高频/剥头皮 |
| 中线（1-3天） | 2-3×ATR | 趋势/波段 |
| 长线（1周+） | 3-5×ATR | 趋势/仓位 |

### 2.3 Python实现

```python
def calculate_atr(klines: list, period: int = 14) -> float:
    """计算ATR"""
    tr_list = []
    for i in range(1, len(klines)):
        high = float(klines[i]['high'])
        low = float(klines[i]['low'])
        prev_close = float(klines[i-1]['close'])

        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)

    if len(tr_list) < period:
        return None
    return sum(tr_list[-period:]) / period


def atr_stop_loss(entry_price: float, atr: float, atr_mult: float = 2.0, direction: str = 'long') -> dict:
    """
    ATR动态止损止盈计算

    Args:
        entry_price: 开仓价格
        atr: ATR值
        atr_mult: ATR倍数（止损用）
        direction: long 或 short

    Returns:
        止损/止盈价格和距离
    """
    if direction == 'long':
        stop_loss = entry_price - atr_mult * atr
        take_profit = entry_price + (atr_mult * 2) * atr  # 2:1 盈亏比
    else:
        stop_loss = entry_price + atr_mult * atr
        take_profit = entry_price - (atr_mult * 2) * atr

    risk_distance = atr_mult * atr
    reward_distance = atr_mult * 2 * atr
    rr_ratio = (atr_mult * 2) / atr_mult  # 固定2:1

    return {
        "direction": direction,
        "entry_price": entry_price,
        "atr": atr,
        "atr_mult": atr_mult,
        "stop_loss": round(stop_loss, 2),
        "take_profit": round(take_profit, 2),
        "risk_distance": round(risk_distance, 2),
        "reward_distance": round(reward_distance, 2),
        "rr_ratio": f"1:{rr_ratio:.1f}",
        "risk_pct": f"{(risk_distance / entry_price) * 100:.2f}%",
        "reward_pct": f"{(reward_distance / entry_price) * 100:.2f}%"
    }


# 示例
klines_sample = [
    {'high': 67000, 'low': 66500, 'close': 66700},
    {'high': 67200, 'low': 66400, 'close': 66800},
    # ... 14+条数据
]
atr = calculate_atr(klines_sample, period=14)
result = atr_stop_loss(entry_price=67000, atr=1500, atr_mult=2.0, direction='long')
# 止损 = 67000 - 3000 = 64000
# 止盈 = 67000 + 6000 = 73000
# 风险 = 4.48%
# 盈亏比 = 1:2
```

---

## 三、综合开仓流程（必读）

```
┌─────────────────────────────────────────┐
│           开仓前检查清单                  │
├─────────────────────────────────────────┤
│ 1. 形态确认：是否满足入场条件？            │
│ 2. 凯利公式：f* 计算结果 > 0？           │
│ 3. 账户仓位上限：不超过账户10%            │
│ 4. 单笔风险上限：不超过账户2%             │
│ 5. ATR止损：止损距离 × 数量 ≤ 风险预算    │
│ 6. 盈亏比：是否 ≥ 1.5:1？               │
│ 7. 杠杆检查：是否 ≤ 10x？                │
│ 8. 保证金率：开仓后是否 ≥ 150%？          │
└─────────────────────────────────────────┘
```

### 3.1 完整示例

```
账户：$10,000
标的：BTC/USDT
当前价格：$95,000
ATR(14)：$1,500
历史胜率：55%（W=0.55）
历史盈亏比：1.5（R=1.5）

Step 1: 凯利计算
  f* = (0.55 - 0.45/1.5) / 1.5 = 23.3%
  半凯利 = 11.7%
  实盘建议 = min(11.7%, 10%) = 10%

Step 2: 账户限制
  最大仓位 = $10,000 × 10% = $1,000

Step 3: ATR止损
  止损 = $95,000 - (2 × $1,500) = $92,000
  止损距离 = $3,000
  止损% = 3.16%

Step 4: 风险验证
  可开数量 = $1,000 ÷ $3,000 = 0.333 BTC
  开仓价值 = 0.333 × $95,000 = $31,667（超过$1,000限制）
  
  修正：$1,000 ÷ $95,000 = 0.0105 BTC
  实际仓位 = $1,000 = 账户10%

Step 5: 盈亏比验证
  止盈 = $95,000 + (4 × $1,500) = $101,000
  潜在盈利 = $6,000
  潜在亏损 = $3,000
  盈亏比 = 2:1 ✅

结论：开0.0105 BTC（$1,000），止损$92,000，止盈$101,000
```

---

## 四、实战注意事项

### 4.1 凯利公式的局限性

| 局限 | 应对 |
|------|------|
| 假设p和b精确已知 | 用历史数据估计保守值 |
| 高波动市场放大损失 | 币圈用1/4凯利 |
| 不考虑流动性风险 | 加流动性检查 |
| 不考虑相关性和极端事件 | 配合VaR使用 |

### 4.2 ATR的局限性

| 局限 | 应对 |
|------|------|
| 滞后性（14周期） | 结合形态确认，不单独使用 |
| 波动率突变时失效 | 重大新闻前不用ATR |
| 不同标的ATR不可比 | 标准化为ATR%比较 |

### 4.3 ATR% 标准化公式

```
ATR% = (ATR / 当前价格) × 100

BTC: ATR=$1,500, 价格=$95,000 → ATR%=1.58%
ETH: ATR=$50, 价格=$2,500 → ATR%=2.0%

比较：ETH波动率比BTC高25%
```

---

## 五、纳入知识库记录

| 项目 | 内容 |
|------|------|
| 文件 | `Knowledge/仓位管理/凯利公式与ATR动态止损实战指南.md` |
| 版本 | v1.0 |
| 更新日期 | 2026-04-04 |
| 来源 | 太子自学 |
| 状态 | ✅ 已纳入策略库 |

---

## 六、相关文件索引

| 文件 | 说明 |
|------|------|
| `Strategy/仓位管理/仓位管理与风控策略.md` | 综合风控框架 |
| `Strategy/策略总览.md` | 五大类策略总览 |
| `Knowledge/仓位管理/凯利公式/` | 凯利公式子目录 |
| `pattern_matcher.py` | 形态识别+信号输出 |

---

_本文件由太子（天禄）于2026-04-04整理纳入移动硬盘策略库_
