# 威科夫量价分析 + 回测框架学习笔记

## 日期：2025-07-08
## 学习主题：威科夫吸筹/派发识别 + 量化指标设计 + 回测框架搭建思路

---

## 一、威科夫量价分析核心概念

### 1.1 基本原理
威科夫方法（Wyckoff Method）由Richard Wyckoff创立，核心思想：
- **价格由"供需关系"决定**
- **主力（Smart Money）通过订单簿操作市场价格**
- 通过成交量识别主力行为

### 1.2 吸筹（Accumulation）- 主力在低位收集筹码

| 阶段 | 特征 |
|------|------|
| 铺垫（Preliminary Support） | 初次支撑，价格在低点出现反弹 |
| 吸筹（Accumulation） | 主力持续买入，成交量放大但价格区间震荡 |
| 测试（Test） | 主力测试上方抛压，缩量回调不破支撑 |
| 拉升（Mark-up） | 突破区间上沿，成交量明显放大 |

### 1.3 派发（Distribution）- 主力在高位派发筹码

| 阶段 | 特征 |
|------|------|
| 横盘（Trading Range） | 价格在高位区间震荡 |
| 派发（Distribution） | 主力持续卖出，成交量放大 |
| 测试（Test） | 反弹缩量，无法突破前高 |
| 下跌（Mark-down） | 跌破区间下沿，成交量放大 |

---

## 二、量化指标设计

### 2.1 量价关系指标（Volume-Price Ratio, VPR）

```python
def calculate_vpr(close_prices, volumes, lookback=20):
    """
    计算量价关系指标
    VPR = (价格变化率 * 成交量变化率) 的移动平均
    
    说明：
    - VPR > 0: 价涨量增或价跌量减，顺势
    - VPR < 0: 价涨量跌或价跌量增，背离
    """
    price_change = (close_prices - close_prices.shift(1)) / close_prices.shift(1)
    volume_change = (volumes - volumes.shift(1)) / volumes.shift(1)
    
    vpr = price_change * volume_change
    vpr_ma = vpr.rolling(window=lookback).mean()
    
    return vpr_ma
```

### 2.2 OBV（能量潮）指标

```python
def calculate_obv(close_prices, volumes):
    """
    OBV = 累计值(如果收盘上涨则+成交量，否则-成交量)
    
    用途：
    - 验证价格趋势的可靠性
    - 底背离可能预示反弹（价格新低但OBV未新低）
    - 顶背离可能预示下跌（价格新高但OBV未新高）
    """
    obv = pd.Series(index=close_prices.index, dtype=float)
    obv.iloc[0] = volumes.iloc[0]
    
    for i in range(1, len(close_prices)):
        if close_prices.iloc[i] > close_prices.iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] + volumes.iloc[i]
        elif close_prices.iloc[i] < close_prices.iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] - volumes.iloc[i]
        else:
            obv.iloc[i] = obv.iloc[i-1]
    
    return obv
```

---

## 三、回测框架搭建思路

### 3.1 基本流程

```
信号生成 → 交易执行 → 记录持仓 → 绩效计算
    ↑                                    ↓
    ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ←
```

### 3.2 伪代码框架

```python
class BacktestEngine:
    def __init__(self, initial_capital=100000):
        self.capital = initial_capital
        self.position = 0  # 持仓数量
        self.trades = []    # 交易记录
        self.equity_curve = []
    
    def on_bar(self, bar):
        """每根K线调用一次"""
        signal = self.generate_signal(bar)
        
        if signal == "BUY" and self.position == 0:
            self.execute_buy(bar)
        elif signal == "SELL" and self.position > 0:
            self.execute_sell(bar)
        
        self.record_equity(bar)
    
    def generate_signal(self, bar):
        """信号生成逻辑"""
        pass  # 由子类实现
    
    def execute_buy(self, bar):
        """买入执行"""
        self.position = self.capital / bar.close
        self.capital = 0
        self.trades.append({"type": "BUY", "price": bar.close, "time": bar.time})
    
    def execute_sell(self, bar):
        """卖出执行"""
        self.capital = self.position * bar.close
        self.position = 0
        self.trades.append({"type": "SELL", "price": bar.close, "time": bar.time})
    
    def calculate_performance(self):
        """绩效计算"""
        total_return = (self.capital - 100000) / 100000
        return {
            "total_return": total_return,
            "num_trades": len(self.trades),
            "win_rate": self.calculate_win_rate()
        }
```

### 3.3 三大回测陷阱

| 陷阱 | 说明 | 规避方法 |
|------|------|----------|
| **过拟合** | 策略参数在历史数据上过度优化，实际失效 | 使用样本外测试、Walk-Forward分析 |
| **前视偏差** | 使用了未来数据（如收盘后才知道的信息） | 严格使用前一时刻可获得的数据 |
| **生存者偏差** | 只用当前存在的标的测试，剔除退市/破产的 | 使用历史全样本数据（包括已退市标的） |

---

## 四、关键心得

1. **威科夫方法的核心是识别主力行为**：通过量价配合判断主力是在吸筹还是派发
2. **量化指标是辅助工具**：OBV、VPR等指标帮助客观化识别形态，但需结合市场背景
3. **回测是验证而非预测**：好的回测框架能发现策略缺陷，但不能保证未来盈利
4. **风险管理优先于收益率**：任何策略都要考虑最大回撤和仓位管理
