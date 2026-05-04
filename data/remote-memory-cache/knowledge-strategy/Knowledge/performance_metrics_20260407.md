# 夏普比率·索提诺比率·绩效归因

> 学习日期：2026-04-07 | 所属周：第4周（回测与绩效评估）| 天气：晴

---

## 一、夏普比率（Sharpe Ratio）深度理解

### 公式
```
SR = (Rp - Rf) / σp

其中：
- Rp = 投资组合平均收益率（年化）
- Rf = 无风险利率（年化，如USDT借贷利率或国债）
- σp = 收益率标准差（年化）
```

### 计算步骤（Python示例）
```python
import numpy as np

def sharpe_ratio(returns, risk_free_rate=0.0, periods_per_year=365):
    """计算年化夏普比率"""
    excess_returns = np.array(returns) - risk_free_rate / periods_per_year
    mean_excess = np.mean(excess_returns)
    std_excess = np.std(excess_returns, ddof=1)
    
    if std_excess == 0:
        return 0.0
    
    # 年化
    annualized_sr = (mean_excess / std_excess) * np.sqrt(periods_per_year)
    return annualized_sr
```

### 关键细节
- **日频数据**：periods_per_year = 365（数字货币）或 252（股票）
- **收益率计算**：用对数收益率 ln(Pt/Pt-1) 比简单收益率更准确
- **无风险利率**：币圈可参考USDT借贷利率（约5%~10%年化）
- **基准对比**：SR > 1 算及格，SR > 2 算优秀，SR < 0.5 需改进

### 常见误区
- 用**简单平均**而非**年化**比较不同频率数据
- 忽略**标准差的时间缩放**：σ_annual = σ_daily × √252
- 用**算术平均**而非**几何平均**计算真实年化收益

---

## 二、索提诺比率（Sortino Ratio）

### 公式
```
Sortino = (Rp - Rf) / σ_downside

其中 σ_downside = 下行标准差（只统计负收益）
```

### 为什么比夏普更好
- 夏普把上行波动也当风险 penalize
- 索提诺只 penalize 下行波动
- 对于趋势跟踪策略，上行波动是盈利，索提诺更公平

### 下行标准差计算
```python
def downside_std(returns, target_return=0.0):
    """计算下行标准差（只统计低于目标收益率的收益）"""
    excess = np.array(returns) - target_return
    # 取负收益部分
    downside_returns = excess[excess < 0]
    
    if len(downside_returns) == 0:
        return 0.0
    
    return np.sqrt(np.mean(downside_returns ** 2))

def sortino_ratio(returns, risk_free_rate=0.0, periods_per_year=365, target=0.0):
    excess = np.mean(returns) - risk_free_rate / periods_per_year
    downside = downside_std(returns, target / periods_per_year)
    
    if downside == 0:
        return 0.0
    
    return (excess / downside) * np.sqrt(periods_per_year)
```

### 目标收益率（MAR）
- 常用选项：0（零收益基准）、无风险利率、某个绝对收益目标
- 币圈建议用 **USDT借贷利率 / 365** 作为日频目标

---

## 三、最大回撤（Maximum Drawdown）

### 定义
从历史最高点到最低点的最大跌幅

### 计算
```python
def max_drawdown(returns):
    """计算最大回撤和回撤期"""
    wealth = (1 + np.array(returns)).cumprod()
    peak = np.maximum.accumulate(wealth)
    drawdown = (wealth - peak) / peak
    
    mdd = np.min(drawdown)  # 最大回撤（负数）
    duration = None  # 回撤持续时间需另行计算
    
    return mdd

def drawdown_duration(returns):
    """计算最长回撤持续天数"""
    wealth = (1 + np.array(returns)).cumprod()
    peak = np.maximum.accumulate(wealth)
    in_drawdown = wealth < peak
    
    # 找最长连续回撤期
    max_dd = 0
    current_dd = 0
    for is_dd in in_drawdown:
        if is_dd:
            current_dd += 1
            max_dd = max(max_dd, current_dd)
        else:
            current_dd = 0
    
    return max_dd
```

### 回撤与回本难度对照
| 回撤 | 回本需要涨幅 |
|------|-------------|
| 5% | 5.3% |
| 10% | 11.1% |
| 20% | 25.0% |
| 33% | 50.0% |
| 50% | 100.0% |
| 70% | 233.3% |

**核心洞察**：回撤越大，回本难度指数级增长。20%回撤需要25%涨幅，不是20%。

---

## 四、绩效归因分析

### 目的
分解收益来源，理解策略的**真实Alpha**（非市场Beta带来的收益）

### 分解框架
```
总收益 = Beta收益 + Alpha收益
       = 市场敞口 + 选股贡献 + 择时贡献 + 其他
```

### Brinson模型（选股+择时）
```python
def brinson_attribution(pfolio_returns, benchmark_returns, sectors_pfolio, sectors_bench):
    """
    Brinson归因：拆解为配置效应、选股效应和交互效应
    """
    # 配置效应：偏离基准行业权重带来的收益
    # 选股效应：行业内选股带来的超额收益
    # 交互效应：配置×选股的交叉影响
    pass
```

### 简化版归因（币圈适用）
```python
def simple_attribution(strategy_returns, market_returns):
    """
    币圈简化归因：
    - Beta = 市场相关度 × 市场收益
    - Alpha = 总收益 - Beta
    - Sharpe_ratio调整后Alpha = Alpha / 跟踪误差
    """
    import numpy as np
    
    # 计算Beta（市场敏感度）
    cov = np.cov(strategy_returns, market_returns)[0][1]
    market_var = np.var(market_returns)
    beta = cov / market_var if market_var != 0 else 0
    
    # Beta收益
    beta_return = beta * np.mean(market_returns)
    
    # Alpha（超额收益）
    alpha_return = np.mean(strategy_returns) - beta_return
    
    # 信息比率（Alpha / 跟踪误差）
    tracking_error = np.std(np.array(strategy_returns) - np.array(market_returns))
    info_ratio = alpha_return / tracking_error if tracking_error != 0 else 0
    
    return {
        'beta': beta,
        'beta_return': beta_return,
        'alpha': alpha_return,
        'tracking_error': tracking_error,
        'info_ratio': info_ratio
    }
```

### 归因结果解读
| 指标 | 含义 |
|------|------|
| 高Beta（>1）| 策略放大市场波动，顺势时赚更多，下跌时也亏更多 |
| 高Alpha | 策略有真实超额收益，与市场无关 |
| 高信息比率 | Alpha稳定，质量高 |

---

## 五、综合绩效评估模板

```python
def performance_report(returns, market_returns=None, risk_free=0.0, periods=365):
    """生成完整绩效报告"""
    
    total_return = np.prod(1 + np.array(returns)) - 1
    annual_return = (1 + total_return) ** (periods / len(returns)) - 1
    annual_vol = np.std(returns) * np.sqrt(periods)
    
    sharpe = (annual_return - risk_free) / annual_vol if annual_vol != 0 else 0
    sortino = # 见上文
    mdd = max_drawdown(returns)
    
    result = {
        '总收益率': f'{total_return:.2%}',
        '年化收益率': f'{annual_return:.2%}',
        '年化波动率': f'{annual_vol:.2%}',
        '夏普比率': f'{sharpe:.2f}',
        '索提诺比率': f'{sortino:.2f}',
        '最大回撤': f'{mdd:.2%}',
        '盈利天数': sum(r > 0 for r in returns),
        '亏损天数': sum(r < 0 for r in returns),
        '胜率': sum(r > 0 for r in returns) / len(returns)
    }
    
    if market_returns is not None:
        attr = simple_attribution(returns, market_returns)
        result['Beta'] = f'{attr["beta"]:.2f}'
        result['Alpha'] = f'{attr["alpha"]:.2%}'
        result['信息比率'] = f'{attr["info_ratio"]:.2f}'
    
    return result
```

---

## 六、第4周学习总结

### 已完成
- ✅ 回测三大陷阱（过拟合/前视偏差/生存者偏差）— 2026-04-06
- ✅ 夏普比率、索提诺比率、最大回撤计算 — 2026-04-07
- ⬜ 绩效归因分析方法

### 核心要点（今日3个）

1. **夏普 vs 索提诺**：两者都年化收益除以风险指标，但分母不同——夏普用总标准差，索提诺只用下行标准差。索提诺对趋势策略更公平，因为它不 penalize 上行波动。

2. **最大回撤的复利陷阱**：回撤20%需要25%涨幅回本，不是20%。回撤越大指数级越难回本，这直接解释了为什么**5%硬止损**比10%好——不是为了少亏，而是为了保护复利引擎不被破坏。

3. **绩效归因的Beta-Alpha分解**：总收益 ≠ Alpha，必须剥离市场Beta才知道策略的真实贡献。高Beta策略在牛市中看起来很强，但下跌时同样脆弱。信息比率（Alpha/跟踪误差）才是衡量真实超额能力的指标。

---

## 明日计划

- **收尾第4周**：完成绩效归因分析学习（凯勒纳-尼 kinship模型在币圈的具体应用）
- **下周启动**：第1周复盘 + 第2周启动（交易心理学深化）
- **实际操作**：用现有交易数据跑一遍 `performance_report()`，验证所学

---

*本笔记基于天禄自我进化系统 v2.0 第4周学习产出*
