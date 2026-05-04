# 户部 · 行情与分析技能库

## 📊 yahooquery (Yahoo Finance)

**用途**: 股票、外汇、大宗商品、指数的实时行情和基本面数据  
**安装**: `pip install yahooquery`  
**无需API Key** (使用yfinance底层)

### 核心功能

```python
from yahooquery import Ticker

# 获取单个或多个标的
aapl = Ticker('AAPL')
btc = Ticker('BTC-USD')

# 实时价格
aapl.price  # 包含当前价、52周范围、市值

# 历史K线
aapl.history(period='1mo', interval='1d')  # 日线
btc.history(period='1y', interval='1wk')   # 周线

# 财务数据
aapl.income_statement()       # 利润表
aapl.balance_sheet()          # 资产负债表
aapl.cash_flow()              # 现金流量表
aapl.all_financial_data()     # 综合财务数据

# 估值指标
aapl.valuation_measures       # P/E, P/B, EV/EBITDA

# 分析师数据
aapl.earnings_trend           # 盈利预测
aapl.recommendation_trend     # 评级趋势 (买入/卖出/持有)
aapl.gradings                 # 最新评级变动

# 股票筛选器
from yahooquery import Screener
s = Screener()
data = s.get_screeners(['day_gainers', 'most_actives'], count=10)

# 期权链
aapl.option_chain
```

### 户部使用场景

1. **每日行情快照** - 开盘前检查A股、港股、美股主要指数
2. **标的基本面** - 财报发布后快速抓取关键指标
3. **分析师评级监控** - 追踪目标股的评级变动
4. **板块轮动分析** - 用screener找当日强势/弱势板块

---

## 📊 hyperliquid-analyzer (Hyperliquid DEX分析)

**用途**: Hyperliquid永续合约市场分析，无需API Key  
**安装**: 无需安装，直接用curl调用

### 核心功能

```bash
# 获取所有币种当前价格
curl -s https://api.hyperliquid.xyz/info -X POST \
  -H "Content-Type: application/json" \
  -d '{"type": "allMids"}' | jq '{BTC: .BTC, ETH: .ETH, SOL: .SOL}'

# 获取市场元数据+币种上下文
curl -s https://api.hyperliquid.xyz/info -X POST \
  -H "Content-Type: application/json" \
  -d '{"type": "metaAndAssetCtxs"}' | jq '.[0:4]'
```

### 户部使用场景

1. **合约市场扫描** - 快速检查各币种价格和波动
2. **链上流动性分析** - 分析Hyperliquid DEX深度
3. **期现价差监控** - Hyperliquid vs 现货交易所

---

## 📈 data-analyst (数据可视化报表)

**来源**: 1kalin/afrexai-data-analyst  
**用途**: 数据清洗、可视化、报表生成

### 核心功能

- CSV/JSON数据处理和转换
- 图表生成
- 趋势分析
- 报表导出

---

## 📋 户部执行清单

- [x] 安装 `yahooquery`: ✅ 已安装 (`pip3 install --break-system-packages yahooquery`)
- [x] 测试获取BTC行情: ✅ 可用
- [x] 测试获取A股: ✅ 可用 (贵州茅台: 600519.SS)
- [ ] 测试获取港股: `python3 -c "from yahooquery import Ticker; print(Ticker('0700.HK').price)"`
- [ ] 记录标的市场数据到 `~/freqtrade/data/reports/` 日报
- [ ] 监控分析师评级变动，异常则推送钦天监

---
*最后更新: 2026-03-30 by 天禄 | 状态: yahooquery已安装可用*
