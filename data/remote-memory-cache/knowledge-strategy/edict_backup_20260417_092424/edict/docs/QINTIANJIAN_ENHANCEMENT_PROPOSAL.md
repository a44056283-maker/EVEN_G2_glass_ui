# 乾天监量化增强提案

> 版本: v2.0  
> 日期: 2026-03-30  
> 太子（天禄）正式下令，兵部编制  

---

## 一、背景与目标

当前乾天监系统 (`monitor_sentiment.py`) 依赖关键词+规则判断市场情绪，存在三大缺陷：

1. **信号主观性强** — 无统一量化框架，同一市场状态不同模块判定不一致
2. **无法历史验证** — 缺乏回测机制，策略效果无法量化评估
3. **干预决策无依据** — 黑天鹅判断阈值缺乏数据支撑，往往事后响应

本提案引入**威科夫量化体系**，为目标。

---

## 二、威科夫量化指标方案

### 2.1 核心理论框架

威科夫方法论（Wyckoff Method）三大核心：

| 概念 | 定义 | 量化指标 |
|------|------|---------|
| **供求关系** | 价格涨跌由供需主导 | Supply/Demand Index |
| **价格与成交量关系** | 底部放量是吸筹信号 | Volume-Price Divergence |
| **因果定律** | 横盘整理（A-D阶段）决定方向 | Range Compression Score |

### 2.2 量化指标体系

#### 指标1：综合吸筹指数（Accumulation Score, AS）

```
AS = Σ(w_i × indicator_i)

指标权重：
  - 价格戳破前期低点时成交量放大率: w1=0.30
  - 低价横盘期间成交量异常放大: w2=0.25
  - 期货基差由负转正速率: w3=0.20
  - 多空持仓比下降速率: w4=0.15
  - 恐惧指数阶段性低点: w5=0.10
```

**读数解释：**
- AS > 0.7 → 机构吸筹中，长线布局信号
- AS 0.4-0.7 → 区间震荡，跟踪等待
- AS < 0.4 → 派发阶段，减仓信号

#### 指标2：横盘压缩评分（Range Compression Score, RCS）

识别威科夫A-B-C-D横盘整理结构：

```
RCS = 1 - (current_ATR / historical_ATR_20)
```

- RCS > 0.8 → 极度压缩，突破在即（高盈亏比入场点）
- RCS 0.5-0.8 → 正常压缩，趋势延续
- RCS < 0.5 → 波动放大，趋势加速尾声

#### 指标3：订单流失衡度（Order Flow Imbalance, OFI）

```
OFI = (bid_qty_exec - ask_qty_exec) / (bid_qty_exec + ask_qty_exec)

> 0.1  → 买方主导，潜在上涨
< -0.1 → 卖方主导，潜在下跌
[-0.1, 0.1] → 均衡，等待方向
```

**数据源：** Binance WebSocket `depth@100ms` 逐档成交数据

#### 指标4：期货基差动量（Futures Basis Momentum, FBM）

```
FBM = (basis_t - basis_{t-4h}) / ATR(basis, 20)

basis = futures_price - spot_price

FBM > 1.5  → 多头加仓意愿强（机构看多）
FBM < -1.5 → 空头加仓意愿强（机构看空）
```

#### 指标5：威科夫综合评分（Wyckoff Composite Score, WCS）

```
WCS = (AS × 0.35) + (RCS × 0.25) + (FBM_normalized × 0.25) + (OFI × 0.15)

WCS > 0.65  → 上涨趋势确立
WCS 0.35-0.65 → 中性，等待确认
WCS < 0.35  → 下跌趋势确立
```

### 2.3 与现有舆情系统对接

```
现有 sentiment_pool.json → 新增字段:
{
  "wyckoff_metrics": {
    "accumulation_score": 0.72,
    "range_compression_score": 0.85,
    "futures_basis_momentum": 1.2,
    "order_flow_imbalance": 0.08,
    "wyckoff_composite_score": 0.68,
    "signal": "ACCUMULATION",
    "confidence": 78,
    "timestamp": "2026-03-30T09:30:00+08:00"
  },
  "sentiment_direction": "LONG",    # ← 由 WCS 决定（替代原有关键词逻辑）
  "sentiment_confidence": 78,        # ← 由 AS 置信度替代
  "black_swan_alert": false,
  "black_swan_categories": []
}
```

---

## 三、monitor_sentiment.py 增强建议

### 3.1 双重信号引擎（新增）

**当前问题：** 仅靠关键词打分，假信号多，方向判定滞后

**方案：** 关键词引擎 + 威科夫引擎并行，以威科夫为主

```python
# 新增模块：wyckoff_engine.py
"""
wyckoff_engine.py — 威科夫量化引擎
独立于 monitor_sentiment.py，不破坏现有逻辑
"""

class WyckoffEngine:
    def __init__(self, sentiment_pool_path: str):
        self.pool = self._load_sentiment_pool(sentiment_pool_path)

    def compute_wcs(self) -> dict:
        """计算威科夫综合评分"""
        ascore = self._accumulation_score()
        rcs    = self._range_compression_score()
        fbm    = self._futures_basis_momentum()
        ofi    = self._order_flow_imbalance()
        wcs    = (ascore*0.35) + (rcs*0.25) + (fbm*0.25) + (ofi*0.15)
        return {"AS": ascore, "RCS": rcs, "FBM": fbm, "OFI": ofi, "WCS": wcs}

    def decide_direction(self) -> tuple:
        """返回 (direction, confidence)"""
        wcs = self.compute_wcs()["WCS"]
        if wcs > 0.65:
            return "LONG", int(wcs * 100)
        elif wcs < 0.35:
            return "SHORT", int((1 - wcs) * 100)
        return "NEUTRAL", int((1 - abs(wcs - 0.5) * 2) * 100)
```

### 3.2 信号融合规则

```
最终信号 = (威科夫引擎 × 0.6) + (舆情引擎 × 0.4)

触发干预阈值：
  - LONG: WCS > 0.65 AND 舆情.confidence >= 60
  - SHORT: WCS < 0.35 AND 舆情.confidence >= 60
  - BLACK_SWAN: WCS < 0.25 OR (舆情.urgency >= 9)
```

### 3.3 数据层增强

| 增强项 | 当前状态 | 建议方案 |
|--------|----------|---------|
| 重复请求消除 | `extract_text()` 内重复 fetch | 增加 URL → 响应缓存（同轮次） |
| HTTP 连接复用 | 每次新建连接 | 使用 `requests.Session()` 复用 |
| Fear & Greed 中文解读 | `interpretation` 字段为空 | 补全 `FEAR_GREED_ZH` 映射表 |
| 数据新鲜度告警 | 无 | 新增 `data_freshness` 字段，超 8h 告警 |

### 3.4 X/Twitter 数据源恢复（高优）

**当前状态：** Nitter 5个实例全部失效，X数据全灭

**推荐方案（按优先级）：**

| 方案 | 数据源 | 优先级 | 说明 |
|------|--------|--------|------|
| 1 | `vxtwitter.com` API | P0 | 已有现成接口，待测试 |
| 2 | RSSHub 代理 | P1 | 需自建 RSSHub 实例 |
| 3 | Nitter 私有实例 | P2 | 搭建成本较高 |
| 4 | 第三方付费 API | P3 | CryptoQuant/X蝉等 |

**验证脚本（不修改原文件）：**

```python
# scripts/test_xtwitter_source.py
import requests

def test_vxtwitter(username: str, tweet_id: str) -> bool:
    """测试 vxtwitter API 可用性"""
    url = f"https://api.vxtwitter.com/Twitter/status/{tweet_id}"
    try:
        r = requests.get(url, timeout=8)
        return r.status_code == 200 and "user" in r.json()
    except:
        return False
```

---

## 四、回测框架方案

### 4.1 框架定位

乾天监回测框架不是完整量化平台，而是**信号有效性和干预时机**的验证工具。

**验证目标：**
1. 威科夫指标对历史趋势的预判准确率
2. 黑天鹅干预的时间效率（从信号到执行）
3. 不同干预阈值组合的夏普比率差异

### 4.2 技术选型

| 组件 | 推荐方案 | 说明 |
|------|----------|------|
| 回测引擎 | Backtrader | 成熟，轻量，支持数据回放 |
| 数据源 | CCXT（历史K线） | Binance/OKX通用 |
| 因子库 | 自建（威科夫指标） | 复用 wyckoff_engine.py |
| 结果存储 | SQLite + Pandas | 轻量，无依赖 |

### 4.3 回测数据集

```
edict/data/backtest/
├── btcusdt_1h_2024.db      # 2024年全年1H K线（自动下载）
├── btcusdt_1h_2025.db      # 2025年全年1H K线
├── sentiment_history/      # 历史舆情快照
│   └── fear_greed_2024.csv
└── black_swan_events.csv   # 已标注的黑天鹅事件时间戳
```

### 4.4 核心回测策略

#### 策略A：威科夫WCS趋势跟随

```python
class WyckoffTrendStrategy(bt.Strategy):
    params = (
        ("wcs_long_threshold", 0.65),
        ("wcs_short_threshold", 0.35),
        ("confidence_min", 60),
    )

    def __init__(self):
        self.wyckoff = WyckoffEngine()
        self.order = None

    def next(self):
        if self.order:
            return  # 避免重复下单

        wcs, conf = self.wyckoff.decide_direction_at(self.data.datetime.date(0))

        if wcs == "LONG" and conf >= self.p.confidence_min:
            self.order = self.buy()
        elif wcs == "SHORT" and conf >= self.p.confidence_min:
            self.order = self.sell()
        elif wcs == "NEUTRAL":
            self.close()
```

#### 策略B：黑天鹅冻结保护（vs无保护基准）

```python
class BlackSwanHedgeStrategy(bt.Strategy):
    """
    对比两种场景：
    - 场景1（保护）：FG<20时全平 + 冻结，下一周期自动解除
    - 场景2（无保护）：全程持仓
    输出：两种场景的收益率、夏普、最大回撤对比
    """
    params = (
        ("fg_threshold", 20),
        ("cooldown_hours", 6),
    )
    # ...
```

### 4.5 关键指标计算

| 指标 | 公式 | 用途 |
|------|------|------|
| 胜率 | 盈利交易数/总交易数 | 评估信号质量 |
| 盈亏比 | 平均盈利/平均亏损 | 评估风险收益 |
| 夏普比率 | (策略收益-无风险收益)/收益标准差 | 综合风险收益 |
| 最大回撤 | max(peak - trough)/peak | 极端风险 |
| 干预效率 | (干预前亏损 - 干预后亏损)/干预前亏损 | 评估干预效果 |

### 4.6 回测报告模板

```
═══════════════════════════════════════════════
  乾天监回测报告 · {date}
═══════════════════════════════════════════════

■ 策略: {strategy_name}
■ 数据: {symbol} {timeframe} {start} ~ {end}
■ 基准: Buy&Hold 收益率 {bm_return}%

■ 核心指标
  总收益率:     {total_return}%
  夏普比率:     {sharpe}
  最大回撤:     {max_dd}%
  胜率:         {win_rate}%
  盈亏比:       {profit_loss_ratio}
  交易次数:     {num_trades}

■ 黑天鹅干预效果（策略B vs 基准）
  干预次数:     {freeze_count}
  避免损失:     {avoided_loss} USDT
  干预效率:     {intervention_efficiency}%

■ 威科夫指标准确率（历史样本）
  WCS>0.65 → 实际上涨准确率: {wcs_long_accuracy}%
  WCS<0.35 → 实际下跌准确率: {wcs_short_accuracy}%
  AS>0.7  → 吸筹确认准确率:  {as_accuracy}%
```

### 4.7 实施计划

| 阶段 | 内容 | 产出 |
|------|------|------|
| Phase 1 | 搭建 Backtrader + CCXT 环境 | `backtest_engine.py` |
| Phase 2 | 接入历史K线数据（BTC 2024-2025） | `data/btcusdt_1h_*.db` |
| Phase 3 | 移植威科夫引擎到回测环境 | `wyckoff_backtest.py` |
| Phase 4 | 编写策略A（趋势跟随）+ 策略B（冻结保护） | `strategies/` |
| Phase 5 | 全量回测 + 生成报告 | `backtest_reports/` |
| Phase 6 | 调参优化（WCS阈值、置信度阈值） | 调参报告 |

---

## 五、优先级与工时估算

| 优先级 | 任务 | 模块 | 工时 |
|--------|------|------|------|
| P0 | 威科夫量化指标引擎开发 | 威科夫方案 | 8h |
| P0 | WCS信号与舆情信号融合 | monitor增强 | 4h |
| P1 | X/Twitter数据源恢复 | monitor增强 | 3h |
| P1 | 回测引擎环境搭建（Phase 1-2） | 回测框架 | 4h |
| P1 | Fear&Greed中文解读补全 | monitor增强 | 1h |
| P2 | 重复请求消除（URL缓存） | monitor增强 | 2h |
| P2 | 历史回测 + 报告生成（Phase 3-5） | 回测框架 | 10h |
| P2 | 数据新鲜度告警 | monitor增强 | 1h |
| P3 | Coinglass替代源 | monitor增强 | 2h |

---

## 六、不修改的文件清单

> ⚠️ **本提案仅生成文档，不修改任何 .py 文件。**
> 实施修改由工部（gongbu）执行。

以下文件在本次增强中**不受影响**：
- `monitor_sentiment.py`（dashboard 版本）
- `monitor_sentiment.py`（scripts 版本）
- `aggregator.py`
- `news_crawler.py`
- `market_crawler.py`
- `community_crawler.py`
- `curl_http.py`
- `retry_utils.py`
- `minimax_client.py`

---

## 七、预期效果

| 维度 | 增强前 | 增强后 |
|------|--------|--------|
| 信号判定依据 | 关键词+规则（主观） | 威科夫WCS量化（客观） |
| 趋势预判 | 滞后1-2个周期 | 同步或领先 |
| 回测能力 | 无 | 支持历史验证 |
| 干预效率 | 黑天鹅后被动响应 | WCS提前预警 |
| X/Twitter数据 | 全灭 | 恢复（vxtwitter） |

---

*本提案由兵部编制，经太子（天禄）审核后交工部执行。*
