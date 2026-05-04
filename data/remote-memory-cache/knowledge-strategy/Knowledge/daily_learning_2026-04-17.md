# 天禄每日GitHub学习笔记 2026-04-17

## 今日搜索概况
- **搜索时间**: 2026-04-17 14:01 CST
- **搜索仓库总数**: 若干（来自 daily_learning_runner.py）
- **新增 Skills**: 5个
- **新增 Strategies**: 5个

## 今日新增 Skills（5个）

### 1. CryptoSignal / Crypto-Signal
| 属性 | 值 |
|------|-----|
| 仓库 | CryptoSignal/Crypto-Signal |
| ⭐ | 5516 |
| 语言 | Python |
| 分类 | 交易机器人 |
| 评分 | 2/10 |
| 描述 | Trading & Technical Analysis Bot |
| URL | https://github.com/CryptoSignal/Crypto-Signal |
| 状态 | 已存入外挂硬盘 Skills/ |

### 2. kernc / backtesting.py
| 属性 | 值 |
|------|-----|
| 仓库 | kernc/backtesting.py |
| ⭐ | 8205 |
| 语言 | Python |
| 分类 | 回测技能 |
| 评分 | 2/10 |
| 描述 | Backtest trading strategies in Python |
| URL | https://github.com/kernc/backtesting.py |
| 状态 | 已存入外挂硬盘 Skills/ |

### 3. ricequant / rqalpha
| 属性 | 值 |
|------|-----|
| 仓库 | ricequant/rqalpha |
| ⭐ | 6299 |
| 语言 | Python |
| 分类 | 回测技能 |
| 评分 | 3/10 |
| 描述 | Algorithmic backtest && trading framework supporting multiple securities |
| URL | https://github.com/ricequant/rqalpha |
| 状态 | 已存入外挂硬盘 Skills/ |

### 4. s-brez / trading-server
| 属性 | 值 |
|------|-----|
| 仓库 | s-brez/trading-server |
| ⭐ | 645 |
| 语言 | Python |
| 分类 | 回测技能 |
| 评分 | 4/10 |
| 描述 | Multi-asset, multi-strategy, event-driven trading platform with portfolio-based risk management |
| URL | https://github.com/s-brez/trading-server |
| 状态 | 已存入外挂硬盘 Skills/ |

### 5. chibui191 / bitcoin_volatility_forecasting
| 属性 | 值 |
|------|-----|
| 仓库 | chibui191/bitcoin_volatility_forecasting |
| ⭐ | 302 |
| 语言 | Jupyter Notebook |
| 分类 | 风控技能 |
| 评分 | 3/10 |
| 描述 | GARCH and Multivariate LSTM forecasting for Bitcoin realized volatility |
| URL | https://github.com/chibui191/bitcoin_volatility_forecasting |
| 状态 | 已存入外挂硬盘 Skills/ |

## 今日新增 Strategies（5个）
与 Skills 同名文件已存入 `Strategy/外部策略/` 目录：
- 策略_CryptoSignal_Crypto-Signal.md
- 策略_kernc_backtesting.py.md
- 策略_ricequant_rqalpha.md
- 策略_s-brez_trading-server.md
- 策略_chibui191_bitcoin_volatility_forecasting.md

## 关键认知提炼

### 值得关注的项目
1. **kernc/backtesting.py** (⭐8205) - Python回测框架，评分虽低但star数最高
2. **s-brez/trading-server** (⭐645, 评分4/10) - 事件驱动交易平台，支持多资产/多策略/组合风控，值得深入研究
3. **chibui191/bitcoin_volatility_forecasting** (⭐302) - 波动率预测结合GARCH和LSTM，可用于优化现有风控模块
4. **ricequant/rqalpha** (⭐6299) - A股量化回测框架，可借鉴其绩效评估方法

### 待分析项目
- CryptoSignal 评分低(2/10)，但star数高(5516)，需进一步评估实际可用性

## 存储记录
| 存储位置 | 数量 | 状态 |
|---------|------|------|
| 外挂硬盘 Skills/ | 5 | ✅ |
| 外挂硬盘 Strategy/外部策略/ | 5 | ✅ |
| mem0 永久记忆 | - | ⚠️ API 401失败 |

## mem0 存储失败说明
mem0 API 返回 401 Unauthorized，需要更新 API Key。当前手动记录关键认知：
- 日期：2026-04-17
- 新增5个量化相关Skills/Strategies
- 重点关注：s-brez/trading-server（事件驱动+组合风控）、波动率预测应用
