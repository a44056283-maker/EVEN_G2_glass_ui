# 天眼AI自动驾驶 - 数据对接与场景话术整合

> **更新时间**: 2026-04-25
> **参数来源**: 机器人配置文件 `runtime_params_v61_{mode}.json`

---

## 一、天眼自动驾驶数据架构

```
┌─────────────────────────────────────────────────────────────┐
│                     天眼自动驾驶 (_entry_scan_once)           │
│                     入场信号捕捉 + 持仓质量监控                 │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
┌───────────┐  ┌───────────┐  ┌───────────┐
│   M1数据   │  │   M2数据   │  │   M3数据   │
│  资金流    │  │  S/R支撑   │  │ 巨量K线   │
└─────┬─────┘  └─────┬─────┘  └─────┬─────┘
      │              │              │
      ▼              ▼              ▼
 calc_fund_flow  get_latest_triple  GiantCandleDetector
      │              │              │
      ▼              ▼              ▼
┌───────────┐  ┌───────────┐  ┌───────────┐
│ Gate/OKX  │  │Gate/OKX/ │  │ Gate/OKX  │
│ /Binance  │  │ Binance   │  │ /Binance  │
└───────────┘  └───────────┘  └───────────┘
```

---

## 二、M1资金流数据对接

### 2.1 M1核心字段

| 字段 | 类型 | 说明 | 配置阈值 |
|------|------|------|---------|
| `ratio` | float | 量比（当前量/基线） | `vol_signal_mult=5.0x` |
| `netflow` | float | 净流向 [-1, +1] | `long_netflow=1.0` |
| `whale_ratio` | float | 大户买卖比 | >0.6大户买入 |
| `score` | int | 综合评分 | — |
| `signal` | str | 信号 LONG/SHORT/NEUTRAL | — |
| `oi_change_pct` | float | OI变化百分比 | — |
| `funding_rate` | float | 资金费率 | — |

### 2.2 M1数据获取

**函数**: `calc_fund_flow_for_pair()` / `_get_mtf_cache()`

**采集方式**:
- 三交易所: Gate + OKX + Binance
- 时线: 15m, 1h, 4h
- 间隔: 60秒 + 烛线关闭触发
- 缓存: L1 SSD → L2 HDD → API实时

### 2.3 M1场景规则

| 场景 | 量比 | 净流向 | Verdict | 置信度 |
|------|------|--------|---------|--------|
| M1-A | ≥2.5x | >0.3 | EXECUTE_LONG | 90% |
| M1-B | ≥2.5x | <-0.3 | EXECUTE_SHORT | 90% |
| M1-C | ≥2.0x | >0.1 | EXECUTE_LONG | 75% |
| M1-D | ≥2.0x | <-0.1 | EXECUTE_SHORT | 75% |
| M1-E | <0.7x | <-0.2 | FORBIDDEN | — |
| M1-F | <0.7x | >0.2 | FORBIDDEN | — |

### 2.4 M1对接状态

| 字段 | 状态 | 来源 |
|------|------|------|
| ratio | ✅ 已对接 | calc_fund_flow |
| netflow | ✅ 已对接 | calc_fund_flow |
| whale_ratio | ✅ 已对接 | _calc_from_ohlcv |
| score | ✅ 已对接 | aggregated |
| signal | ✅ 已对接 | LONG/SHORT/NEUTRAL |
| oi_change_pct | ✅ 已对接 | fund_flow_scanner |
| funding_rate | ✅ 已对接 | fund_flow_scanner |

---

## 三、M2 S/R支撑压力数据对接

### 3.1 M2核心字段

| 字段 | 类型 | 说明 | 配置阈值 |
|------|------|------|---------|
| `nearest_support` | float | 最近支撑位 | — |
| `nearest_resistance` | float | 最近阻力位 | — |
| `dist_to_support_pct` | float | 距支撑% | `sr_entry_range=1.0%` |
| `dist_to_resistance_pct` | float | 距阻力% | `sr_entry_range=1.0%` |
| `dual_validated_count` | int | 双验数量 | ≥2 |
| `triple_validated_count` | int | 三验数量 | ≥3 |
| `strong_levels` | list | 强S/R位 | — |

### 3.2 M2数据获取

**函数**: `get_latest_triple()` / `get_sr_for_tianyan()`

**采集方式**:
- 三交易所: Gate + OKX + Binance
- 四时线: 15m + 30m + 1h + 4h
- 交叉验证: ≥2交易所确认 = 高可信度
- 缓存: L1 SSD(2h TTL) + L2 HDD

### 3.3 M2场景规则

| 场景ID | 描述 | 规则 |
|--------|------|------|
| S01 | 三验强支撑带量突破 | triple_validated≥2 + 放量 |
| S02 | 双验支撑紧贴入场 | dual_validated≥2 + dist<1% |
| S03 | 三验强阻力无量突破 | triple_validated≥2 + 无量 |
| S04-S14 | 其他场景 | 见规则库 |

### 3.4 M2对接状态

| 字段 | 状态 | 来源 |
|------|------|------|
| nearest_support | ✅ 已对接 | get_latest_triple |
| nearest_resistance | ✅ 已对接 | get_latest_triple |
| dist_to_support_pct | ✅ 已对接 | get_sr_for_tianyan |
| dist_to_resistance_pct | ✅ 已对接 | get_sr_for_tianyan |
| dual_validated_count | ✅ 已对接 | get_latest_triple |
| triple_validated_count | ✅ 已对接 | get_latest_triple |
| strong_levels | ✅ 已对接 | get_sr_for_tianyan |

---

## 四、M3巨量K线数据对接

### 4.1 M3核心字段

| 字段 | 类型 | 说明 | 配置阈值 |
|------|------|------|---------|
| `giant_bull` | int | GIANT阳线数 | `long_giant_vol=3.0x` |
| `giant_bear` | int | GIANT阴线数 | `short_giant_vol=3.0x` |
| `squeeze_bull/bear` | int | SQUEEZE阴阳 | 3.0x≤量比<5.0x |
| `high_count` | int | HIGH可信度数 | — |
| `has_liquidation` | bool | 是否有爆仓流出 | — |
| `net_inflow/outflow` | str | 净流入/流出 | — |
| `max_vol_ratio` | float | 最大量比 | `peak_vol_min=7.0x` |
| `reversal_hunt` | bool | 反转猎杀信号 | — |

### 4.2 M3数据获取

**函数**: `GiantCandleDetector.detect_multi_tf()`

**采集方式**:
- 多时线: 15m + 30m + 1h + 4h
- 多交易所: Gate + OKX
- 合并规则: 2+时线 = HIGH可信度

### 4.3 M3场景规则

| 场景ID | 描述 | Verdict |
|--------|------|---------|
| M3-01 | GIANT阳 + INFLOW + HIGH | EXECUTE_LONG |
| M3-02 | GIANT阳 + OUTFLOW | FORBIDDEN |
| M3-03 | GIANT阴 + OUTFLOW + HIGH | EXECUTE_SHORT |
| M3-09 | OUTFLOW_LIQUIDATION + HIGH | HUNT_REVERSE |
| M3-15 | 其他 | FORBIDDEN |

### 4.4 M3对接状态

| 字段 | 状态 | 来源 |
|------|------|------|
| giant_candles | ✅ 已对接 | GiantCandleDetector |
| giant_bull/bear | ✅ 已对接 | m3_giant_all |
| squeeze_bull/bear | ✅ 已对接 | m3_giant_all |
| high_count | ✅ 已对接 | m3_giant_all |
| has_liquidation | ✅ 已对接 | m3_giant_all |
| net_inflow/outflow | ✅ 已对接 | m3_giant_all |

---

## 五、天眼自动驾驶场景话术

### 5.1 入场扫描循环

| 话术 | 触发条件 | 参数 |
|------|---------|------|
| `[天眼-入场] 入场扫描循环启动,每2分钟检查所有交易对` | 扫描启动 | — |
| `[天眼-入场] 轮扫第N轮开始` | 轮次开始 | N=轮数 |
| `[天眼-入场] MTF缓存空/过期，触发一次性实时M1多时线扫描...` | 缓存失效 | — |
| `[天眼-入场] 实时M1多时线扫描完成: {n}个交易对×3时线` | 扫描完成 | n=对数 |
| `[天眼-入场] 数据就绪 M2={m2} M3={m3} M1源:direct_calc/cache` | 数据就绪 | m2/m3=数量 |

### 5.2 V6.5规则预过滤

| 话术 | 触发条件 | 参数 |
|------|---------|------|
| `[天眼-入场] 加载V6.5阈值: 量比噪音=5.0x 放量突破=7.0x` | 参数加载 | 阈值 |
| `[天眼-入场] 15m触发={tf15} 1h触发={tf1h} 4h触发={tf4h}` | 时线触发 | True/False |
| `[天眼-入场] 触发时线数={n} 触发时线={tfs}` | 触发统计 | n=数量 |

### 5.3 M1/M2/M3数据获取

| 话术 | 触发条件 | 参数 |
|------|---------|------|
| `[天眼-M1] {pair} 量比={ratio}x 净流向={netflow} 信号={signal}` | M1获取 | ratio/netflow/signal |
| `[天眼-M1] {pair} M1数据获取失败: {e}` | M1失败 | e=错误 |
| `[天眼-S/R] {pair} 主数据流:m2_triple_exchange 双验={dual} 三验={triple}` | M2获取 | dual/triple |
| `[天眼-S/R] {pair} 备数据流(本地OHLCV)` | M2备援 | — |
| `[天眼-S/R] ⚠️ M2主备数据流均不可用` | M2失败 | — |
| `[天眼-M3] {pair} 巨量数据获取成功: {n}个信号` | M3获取 | n=数量 |
| `[天眼-M3] {pair} 巨量数据获取失败: {e}` | M3失败 | e=错误 |

### 5.4 AI分析与决策

| 话术 | 触发条件 | 参数 |
|------|---------|------|
| `[天眼] {pair} AI分析异常: {e}` | AI异常 | e=错误 |
| `[天眼] {pair} AI响应为空，降级规则检测` | AI空响应 | — |
| `[天眼] {pair} AI响应非JSON: {raw}` | AI格式异常 | raw=原始响应 |
| `[天眼] {pair} 决策: verdict={verdict} score={score} rounds={r}/{required}` | 决策结果 | verdict/score/rounds |

### 5.5 执行入场

| 话术 | 触发条件 | 参数 |
|------|---------|------|
| `[天眼-入场] {pair} 轮次={r}/{required} verdict={verdict} 执行中...` | 执行开始 | r=当前轮次 |
| `[天眼-入场] {pair} verdict={verdict} → 执行入场` | 确认执行 | verdict |
| `[天眼-入场] {pair} 跳过:Bot已有持仓 {n}个 → 防止重复` | 防止重复 | n=持仓数 |
| `[天眼] ❌ 执行异常: {pair} {verdict} {e}` | 执行失败 | e=错误 |
| `[天眼] ✅ 执行成功: {pair} {verdict}` | 执行成功 | verdict |

### 5.6 持仓质量监控

| 话术 | 触发条件 | 参数 |
|------|---------|------|
| `[天眼] 后台扫描循环启动,每5分钟自动评估` | 监控启动 | — |
| `[天眼] 端口:{port} 获取到{len}个持仓` | 持仓获取 | port/len |
| `[天眼] 候选持仓{n}个,开始读取M1缓存...` | 候选统计 | n=数量 |
| `[天眼] OHLCV预取完成,开始构建持仓数据...` | 数据就绪 | — |
| `[天眼] 🔴临界立即执行: {pair} score={score} action={action}` | 临界信号 | score/action |

### 5.7 反手机会

| 话术 | 触发条件 | 参数 |
|------|---------|------|
| `[反手AI] {pair} can_reverse={bool} {reason}` | 反手检测 | bool/reason |
| `[反手AI] {pair} R1量比={r1}x✓ R2资金流做空确认✓ ...` | 反手条件 | 各条件 |
| `[出山AI·反手跳过] {pair} 不满足反手规则: [R3偏离S/R {dist}%✗]` | 反手跳过 | dist=偏离% |

### 5.8 完成统计

| 话术 | 触发条件 | 参数 |
|------|---------|------|
| `[天眼] 自动扫描完成` | 扫描完成 | — |
| `[天眼-入场] {datetime} 入场扫描完成` | 入场完成 | datetime |
| `[天眼] 本轮共{len}条决策` | 决策统计 | len=数量 |

---

## 六、数据对接状态汇总

### 6.1 M1/M2/M3对接状态

| 数据层 | 字段数 | 已对接 | 缺失 | 状态 |
|--------|--------|--------|------|------|
| M1资金流 | 7 | 7 | 0 | ✅ 完整 |
| M2 S/R | 7 | 7 | 0 | ✅ 完整 |
| M3巨量K线 | 8 | 8 | 0 | ✅ 完整 |

### 6.2 缺失数据清单

| 数据项 | 描述 | 影响 | 优先级 |
|--------|------|------|--------|
| M1 OI绝对量 | 持仓OI vs 全网OI占比 | 机构意图判断 | P2 |
| M3 清算地图 | 各价格区间清算密度 | 反转猎杀精度 | P2 |
| M3 时间加权 | 巨量K线发生时间 | 短期vs长期信号 | P3 |
| M2 强度评分 | S/R位的具体强度值 | 入场质量精确评分 | P3 |

---

## 七、天眼AI决策矩阵

### 7.1 入场决策矩阵（M1×M2×M3）

| M1信号 | M2 S/R | M3巨量 | Verdict | 置信度 |
|--------|---------|--------|---------|--------|
| LONG≥2.5x | 支撑≤1% | GIANT阳 | EXECUTE_LONG | 95% |
| LONG≥2.5x | 支撑≤1% | 无信号 | EXECUTE_LONG | 85% |
| LONG≥2.5x | 支撑>1% | 无信号 | OBSERVE | 60% |
| LONG<2.5x | 支撑≤1% | GIANT阳 | EXECUTE_LONG | 75% |
| LONG<2.5x | 支撑>1% | 无信号 | FORBIDDEN | — |
| SHORT≥2.5x | 阻力≤1% | GIANT阴 | EXECUTE_SHORT | 95% |
| SHORT≥2.5x | 阻力≤1% | 无信号 | EXECUTE_SHORT | 85% |

### 7.2 天眼Verdict枚举

| Verdict | 说明 | 执行 | 置信度范围 |
|---------|------|------|-----------|
| EXECUTE_LONG | 授权做多 | ✅ 执行 | 75-99% |
| EXECUTE_SHORT | 授权做空 | ✅ 执行 | 75-99% |
| OBSERVE | 观望监控 | ❌ 不执行 | 50-74% |
| FORBIDDEN | 禁止操作 | ❌ 不执行 | — |
| HUNT_REVERSE | 反转猎杀 | ✅ 执行全平+反手 | 75-99% |

---

## 八、天眼自动驾驶配置参数

### 8.1 入场参数（配置文件值）

| 参数 | 配置值 | 说明 |
|------|--------|------|
| `vol_signal_mult` | **5.0x** | L1量比噪音阈值 |
| `long_vol_mult` | **5.0x** | 做多量比倍数 |
| `short_vol_mult` | **5.0x** | 做空量比倍数 |
| `breakout_mult` | **7.0x** | 放量突破阈值 |
| `long_netflow` | **1.0** | 做多净流入阈值 |
| `short_netflow` | **1.0** | 做空净流出阈值 |
| `sr_entry_range` | **1.0%** | S/R入场偏离容忍 |
| `sr_touch_min` | **1次** | S/R触碰最小次数 |
| `rsi_oversold` | **25** | RSI超卖阈值 |
| `rsi_overbought` | **75** | RSI超买阈值 |
| `long_giant_vol` | **3.0x** | 做多巨量阈值 |
| `short_giant_vol` | **3.0x** | 做空巨量阈值 |
| `peak_vol_min` | **7.0x** | 极端天量门槛 |

### 8.2 仓位杠杆参数

| 参数 | 配置值 | 说明 |
|------|--------|------|
| `max_positions` | **4** | 最大持仓数 |
| `leverage_strong` | **10x** | 强信号杠杆 |
| `leverage_medium` | **7x** | 中信号杠杆 |
| `leverage_weak` | **5x** | 弱信号杠杆 |
| `base_stake_pct` | **5%** | 基础仓位比例 |
