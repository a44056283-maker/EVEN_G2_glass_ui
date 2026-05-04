# 交易心理学深化·认知偏差量化识别
> 学习日期：2026-04-09 | 所属周：第5周（交易心理学深化）| 时间：14:00-15:00

---

## 一、为什么需要"量化"认知偏差

**认知偏差的本质是heuristics（启发式思维）**
- 人脑处理信息时为节省认知资源，发展出"经验法则"
- 这些法则在大多数情况下有效，但在金融市场里恰恰容易被人反向利用
- **量化识别的目标**：把"我感觉不对劲"变成"这个指标超过阈值"

---

## 二、四种核心偏差的量化识别方法

### 1. 过度自信（Overconfidence）

**量化指标：**

| 指标 | 计算方式 | 预警阈值 |
|------|----------|----------|
| 交易频率 vs 胜率相关性 | 相关系数 r | r < 0 且频率高 → 过度交易 |
| 预测准确率自评 vs 实际 | (自评准确 - 实际准确) / 实际准确 | > 20% → 过度自信 |
| 持仓周期异常 | 平均持仓时间 vs 策略规定 | 持仓时间 < 规定的50% → 过度干预 |
| 仓位放大频率 | 亏损后加仓次数 / 总交易次数 | > 30% → 复仇交易倾向 |

**实战公式：**
```python
def overconfidence_score(trades_df):
    """
    过度自信综合评分（0-100）
    """
    # 交易频率
    trade_count = len(trades_df)
    avg_holding_hours = trades_df['holding_hours'].mean()
    
    # 预测偏差
    predicted_direction = trades_df['predicted_direction']
    actual_direction = trades_df['actual_direction']
    prediction_accuracy = (predicted_direction == actual_direction).mean()
    claimed_accuracy = trades_df['claimed_accuracy'].mean()
    prediction_deviation = claimed_accuracy - prediction_accuracy
    
    # 亏损后加仓
    loss_additions = trades_df[trades_df['pnl'] < 0]['added_position'].sum()
    loss_count = (trades_df['pnl'] < 0).sum()
    loss_addiction_ratio = loss_additions / loss_count if loss_count > 0 else 0
    
    # 综合评分
    score = 0
    if prediction_deviation > 0.1: score += 30
    if loss_addiction_ratio > 0.3: score += 30
    if avg_holding_hours < 4: score += 20  # 持仓极短
    if trade_count > 20: score += 20  # 月交易超过20笔
    
    return {
        '过度自信评分': score,
        '预测偏差': f'{prediction_deviation:.1%}',
        '亏损加仓率': f'{loss_addiction_ratio:.1%}',
        '平均持仓(小时)': round(avg_holding_hours, 1),
        '诊断': '危险' if score > 60 else '注意' if score > 30 else '正常'
    }
```

---

### 2. 损失厌恶（Loss Aversion）

**量化指标：**

| 指标 | 计算方式 | 预警阈值 |
|------|----------|----------|
| 止盈止损比 | 平均止盈金额 / 平均止损金额 | < 1.5 → 损失厌恶过强 |
| 止损执行率 | 已触发止损且执行 / 总止损触发次数 | < 80% → 撤销过多 |
| 持仓时间不对称 | 盈利持仓时间 vs 亏损持仓时间 | 亏损持仓 > 盈利持仓的2倍 → 明显倾向 |
| 提前平盈率 | 实际盈利但未达目标就平仓 / 总盈利交易 | > 50% → 急于落袋 |

**实战公式：**
```python
def loss_aversion_score(trades_df):
    """
    损失厌恶综合评分（0-100）
    """
    wins = trades_df[trades_df['pnl'] > 0]
    losses = trades_df[trades_df['pnl'] < 0]
    
    avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
    avg_loss = abs(losses['pnl'].mean()) if len(losses) > 0 else 0
    win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 999
    
    # 持仓时间不对称
    avg_win_holding = wins['holding_hours'].mean() if len(wins) > 0 else 0
    avg_loss_holding = losses['holding_hours'].mean() if len(losses) > 0 else 0
    holding_asymmetry = avg_loss_holding / avg_win_holding if avg_win_holding > 0 else 999
    
    # 止损撤销率
    stop_triggered = trades_df[trades_df['stop_loss_triggered'] == True]
    stop_executed = stop_triggered[stop_triggered['stop_loss_executed'] == True]
    stop_execution_rate = len(stop_executed) / len(stop_triggered) if len(stop_triggered) > 0 else 1.0
    
    # 综合评分
    score = 0
    if win_loss_ratio < 1.5: score += 35
    if holding_asymmetry > 2.0: score += 30
    if stop_execution_rate < 0.8: score += 35
    
    return {
        '损失厌恶评分': score,
        '盈亏比': round(win_loss_ratio, 2),
        '持仓时间不对称': round(holding_asymmetry, 1),
        '止损执行率': f'{stop_execution_rate:.1%}',
        '诊断': '危险' if score > 60 else '注意' if score > 30 else '正常'
    }
```

---

### 3. 锚定效应（Anchoring）

**量化指标：**

| 指标 | 计算方式 | 预警阈值 |
|------|----------|----------|
| 止损位集中度 | 所有止损位距入场价的比例分布 | 标准差 < 5% → 可能锚定入场价 |
| 回本卖比例 | 以入场价为中心的止盈交易 / 总止盈交易 | > 40% → 锚定回本 |
| 价格目标分散度 | 止盈目标价 / 入场价的比值分布 | 分散度低 → 锚定固定数值 |

**识别方法：**
```python
def anchoring_check(trades_df):
    """
    锚定效应检测
    """
    # 检查止损是否锚定入场价（而非技术位）
    # 如果止损点都集中在入场价下方固定百分比，可能是锚定
    
    trades_df['stop_distance_pct'] = (trades_df['entry_price'] - trades_df['stop_loss_price']) / trades_df['entry_price']
    stop_distances = trades_df['stop_distance_pct'].dropna()
    
    # 集中度分析
    stop_std = stop_distances.std()
    stop_mean = stop_distances.mean()
    cv = stop_std / stop_mean if stop_mean > 0 else 0  # 变异系数
    
    # 回本卖检测
    target_at_entry = trades_df[
        (trades_df['take_profit_price'] >= trades_df['entry_price'] * 0.98) &
        (trades_df['take_profit_price'] <= trades_df['entry_price'] * 1.02)
    ]
    breakeven_ratio = len(target_at_entry) / len(trades_df) if len(trades_df) > 0 else 0
    
    return {
        '止损距离变异系数': round(cv, 3),  # < 0.3 表明高度集中
        '回本卖比例': f'{breakeven_ratio:.1%}',
        '诊断': '可能锚定入场价' if cv < 0.3 else '正常'
    }
```

---

### 4. 确认偏差（Confirmation Bias）

**量化指标：**

| 指标 | 计算方式 | 预警阈值 |
|------|----------|----------|
| 信息搜索偏向 | 持仓期间阅读利好/利空文章比例 | 利好 > 70% → 选择性关注 |
| 逆向论证缺失 | 决策日志中"反向理由"数量 | 连续5笔无逆向理由 → 确认偏差 |
| 持仓后观点变化 | 持仓后对币种观点与持仓前对比 | 观点趋同 > 80% → 过滤异议 |

**检测框架：**
```python
def confirmation_bias_check(trading_journal):
    """
    确认偏差检测
    """
    # 每笔交易必须有正反两个理由
    reasons_for = trading_journal['reasons_for']
    reasons_against = trading_journal['reasons_against']
    
    no_contrarian = (reasons_against.str.len() == 0).sum()
    no_contrarian_ratio = no_contrarian / len(trading_journal)
    
    # 持仓后观点变化追踪
    pre_position_sentiment = trading_journal['sentiment_before']  # -1 到 1
    post_position_sentiment = trading_journal['sentiment_after']
    sentiment_shift = (post_position_sentiment - pre_position_sentiment).abs().mean()
    
    return {
        '无逆向理由比例': f'{no_contrarian_ratio:.1%}',
        '持仓后情感漂移均值': round(sentiment_shift, 2),
        '诊断': '确认偏差风险' if no_contrarian_ratio > 0.5 else '正常'
    }
```

---

## 三、规则对抗本能：系统化规避框架

### 核心原则：用规则替代情绪决策

**三层防御体系：**

```
第一层：交易前（预防）
├── 每笔交易必须填写"逆向检查表"
│   ├── 如果不持有，现在会买入吗？
│   ├── 该币种近期有哪些利空？
│   └── 止损位是基于技术面还是成本？
├── 冷静期：信号出现后等待≥4小时再执行
└── 仓位上限：单币种不超过总仓位20%

第二层：交易中（监控）
├── 硬止损单提前挂好，不进终端操作
├── 保证金率预警：<150%立即通知
└── 持仓超时规则：未达目标，持仓不超过72小时

第三层：交易后（复盘）
├── 偏差自检：每周量化四项偏差评分
├── 决策日志审查：正反理由完整性
└── 错误不过夜：技术问题当日解决
```

---

## 四、认知偏差计分板（每周自检）

| 偏差 | 指标 | 正常 | 注意 | 危险 | 本周得分 |
|------|------|------|------|------|----------|
| 过度自信 | 预测偏差 + 交易频率 | <20 | 20-60 | >60 | 待评分 |
| 损失厌恶 | 盈亏比 + 持仓不对称 | <20 | 20-60 | >60 | 待评分 |
| 锚定效应 | 止损集中度 + 回本卖 | <20 | 20-60 | >60 | 待评分 |
| 确认偏差 | 无逆向理由比例 | <20 | 20-60 | >60 | 待评分 |

**总分 > 150 → 强制冷静期3天，暂停开新仓**

---

## 五、第5周学习进度

| 主题 | 状态 | 日期 | 核心产出 |
|------|------|------|----------|
| 认知偏差量化识别框架 | ✅ | 2026-04-09 | 四种偏差量化指标+Python公式 |
| 规则对抗本能体系 | 🔄 今日 | 2026-04-09 | 三层防御框架 |
| 交易日志偏差自检模板 | 📋 计划 | 2026-04-10 | 可填写模板 |

---

## 六、核心要点（3个）

1. **量化识别是打破认知偏差的第一步**：当"我感觉良好"变成具体的指标数字和阈值时，情绪干扰才有可能被客观量化。四种核心偏差（过度自信、损失厌恶、锚定、确认）都有可直接计算的预警指标。

2. **三层防御体系：用规则替代情绪**：交易前填逆向检查表+4小时冷静期，交易中硬止损提前挂好+保证金率监控，交易后每周偏差评分。任何一层的执行都能有效切断偏差→错误决策的链条。

3. **总分>150分强制暂停**：偏差有累积效应，单项指标危险不可怕，可怕的是多项同时超标。建立硬性暂停机制，让系统在"失控"前自动介入。

---

## 七、明日计划

- 完成交易日志偏差自检模板（可填写版）
- 学习主题：行为金融学在实盘中的应用（认知偏差与交易决策绑定）

---

*本笔记基于天禄自我进化系统 v2.0 第5周第1天学习产出*
