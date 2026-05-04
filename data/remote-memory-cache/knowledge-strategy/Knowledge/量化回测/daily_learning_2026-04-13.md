# 每日学习 2026-04-13

## 今日主题
GitHub 交易策略库深度学习 — 回测框架 & 量化策略

---

## 一、kernc/backtesting.py ⭐8189

### 核心认知
最值得集成的回测框架。安装简单 (`pip install backtesting`)，API 简洁，输出完整绩效指标。

### 关键优势
- **Kelly Criterion**：直接输出凯利公式建议的仓位比例
- **SQN (System Quality Number)**：量化策略质量评分
- **内置优化器**：自动找最优参数
- **任意指标库兼容**：不绑定 ta-lib 或 stockstats
- **交互式可视化**：图表直接看仓位移仓

### 核心用法
```python
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
from backtesting.test import SMA, GOOG

class SmaCross(Strategy):
    def init(self):
        self.ma1 = self.I(SMA, self.data.Close, 10)
        self.ma2 = self.I(SMA, self.data.Close, 20)
    def next(self):
        if crossover(self.ma1, self.ma2): self.buy()
        elif crossover(self.ma2, self.ma1): self.sell()

bt = Backtest(GOOG, SmaCross, commission=.002)
stats = bt.run()
bt.plot()
```

### 输出指标（SQN视角）
- SQN 1.78 = 良好（>1.5算合格）
- Sharpe Ratio 0.66 = 中等
- Win Rate 53.76%（配合 Profit Factor 2.13 = 期望为正）
- Calmar Ratio 0.77

### 对我们的价值
**高。** 可直接替代 freqtrade 的部分回测工作。  
建议：凯利公式仓位计算可以整合到我们现有风控模块。

---

## 二、je-suis-tm/quant-trading ⭐9648

### 策略库组成
| 类别 | 策略 |
|------|------|
| 技术指标 | MACD, Parabolic SAR, RSI形态识别, Bollinger Bands形态识别 |
| 突破策略 | London Breakout, Dual Thrust |
| 套利/统计 | Pair Trading(协整), Portfolio Optimization |
| 择时 | Heikin-Ashi, Shooting Star |
| 期权 | Options Straddle, VIX Calculator |
| 另类数据 | Monte Carlo, Oil Money, Wisdom of Crowd |

### Pair Trading 核心逻辑（重要）
1. 选两只币/股，跑 Engle-Granger 两步协整检验
2. 协整通过后，设定标准化残差的阈值（通常±1σ）
3. 残差突破阈值 → 信号：做多便宜的 + 做空贵的
4. 定期复查协整状态

### VIX Calculator
- 计算隐含波动率，用于判断市场恐慌程度
- 可作为我们舆情门控(L7)的量化补充

### London Breakout 逻辑
- 伦敦时段（08:00-09:00 UTC）突破前高/前低入场
- 经典日内剥头皮策略

### 对我们的价值
**中等。** Pair Trading 逻辑可以借鉴但加密货币币本位下需要调整。  
VIX 计算对合约风险管理有价值。

---

## 三、FMZ 量化平台

### 核心认知
主要是**策略商城+云托管平台**，不是代码库。策略用 JavaScript/Python/MyLanguage(麦语言)编写。

### 值得关注的方向
- **TradingView 信号执行机器人**：TV 信号 → 自动下单（我们 14:00 学习里已有类似思路）
- **资金费率监控**：监控多交易所资金费率（可辅助套利决策）
- **多交易所划转工具**：辅助仓位管理

### 对我们的价值
**低。** FMZ 是平台不是策略库。里面的策略在加密货币领域并不比我们的 V6.5 框架更优。

---

## 今日提炼

| 编号 | 规律/认知 | 优先级 |
|------|-----------|--------|
| 1 | backtesting.py 的 Kelly Criterion 输出可直接整合到我们的仓位管理中 | 高 |
| 2 | Pair Trading 协整思路可用于山寨币跨品种对冲 | 中 |
| 3 | VIX 隐含波动率可量化舆情恐慌程度，补充 L7 舆情门控 | 中 |
| 4 | SQN > 1.5 是策略及格线，我们应定期用 backtesting.py 验证现有策略 | 高 |

---

## 下一步行动
1. 将 backtesting.py 的 Kelly 公式整合到 freqtrade 仓位计算中
2. 尝试用 backtesting.py 对 V6.5 策略做基准回测（取得 SQN 基线）
3. 探索 Pair Trading 在币本位合约的可行性（需要 EUR、USD 稳定币对）

