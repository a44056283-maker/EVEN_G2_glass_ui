# 天禄V6.5 × TradingAgents 辩论架构 升级方案

> 基于 TradingAgents 多Agent辩论框架，为天禄V6.5构建机构级AI决策体系
> 参考项目：TauricResearch/TradingAgents ⭐51,294

---

## 一、TradingAgents 辩论架构核心要素

### 1.1 标准框架拓扑

```
┌─────────────────────────────────────────────────────────────┐
│                     TradingAgents 框架                       │
│                                                             │
│  ┌──────────────┐     ┌──────────────┐                     │
│  │  Technical    │     │ Fundamentals │                     │
│  │  Analyst     │     │  Analyst     │                     │
│  └──────┬───────┘     └──────┬───────┘                     │
│  ┌──────┴───────┐     ┌──────┴───────┐                     │
│  │   Sentiment  │     │  News        │                     │
│  │   Analyst   │     │  Analyst     │                     │
│  └──────┬───────┘     └──────┬───────┘                     │
│         └─────────┬─────────┘                               │
│              ┌────▼────┐                                   │
│              │ Researchers│ ←── Bull/Bear 多空辩论          │
│              │ (研究员)  │                                 │
│              └────┬────┘                                   │
│              ┌────▼────┐                                   │
│              │  Trader  │ ←── 交易员：合成报告，提议方案    │
│              └────┬────┘                                   │
│              ┌────▼────┐                                   │
│              │  Risk    │ ←── 风控：评估保证金/止损/杠杆    │
│              │  Mgmt    │                                 │
│              └────┬────┘                                   │
│              ┌────▼────┐                                   │
│              │ Portfolio│ ←── 投资组合经理：最终裁定        │
│              │  Manager │                                 │
│              └────┬────┘                                   │
│              ┌────▼────┐                                   │
│              │ Reflect  │ ←── 自我反思：记忆错误，迭代改进  │
│              └──────────┘                                   │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 评级体系（5档）

| 评级 | 含义 | 对应天禄动作 |
|------|------|-------------|
| **Buy** | 强烈信念入场或加仓 | accept / full_close后的反向开仓 |
| **Overweight** | 乐观，逐步加仓 | dca_l1 / dca_l2 |
| **Hold** | 维持当前持仓 | hold |
| **Underweight** | 减仓，收取部分利润 | half_close |
| **Sell** | 清仓离场 | full_close |

---

## 二、天禄V6.5 辩论架构设计

### 2.1 架构拓扑

```
┌────────────────────────────────────────────────────────────────┐
│                   天禄V6.5 AI辩论决策体系                        │
│                     (本地LLM · MiniMax M2.7)                    │
│                                                                │
│  ┌─────────────────┐        ┌─────────────────────────┐        │
│  │  🧠 技术分析师   │        │  🛡️ 风控分析师         │        │
│  │ TechAnalyst    │        │  RiskAnalyst           │        │
│  │  Agent          │        │  Agent                 │        │
│  └────────┬────────┘        └───────────┬────────────┘        │
│           │                               │                     │
│  L1量比判断    L3信号评分        R2健康度           │
│  L4 S/R位置    12场景判定        强平距离           │
│           │                               │                     │
│           └─────────┬─────────────────────┘                     │
│                ┌────▼────┐                                     │
│                │  🗡️ 辩论员  │ ←── Bull(做多) vs Bear(做空)  │
│                │ DebateAgent│   模拟TradingAgents研究员角色     │
│                │           │   辩论1-2轮后收敛                 │
│                └────┬────┘                                     │
│                ┌────▼────┐                                     │
│                │  ⚖️ 裁判   │ ←── 综合双方论点，输出最终裁定   │
│                │ JudgeAgent│   5档评级 + 执行动作              │
│                └────┬────┘                                     │
│                ┌────▼────┐                                     │
│                │  📚 记忆库 │ ←── FinancialSituationMemory    │
│                │ Memory    │   历史决策 + 反思日志             │
│                └───────────┘                                    │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 三大分析师 Agent 角色定义

---

#### Agent 1：🧠 技术分析师（TechAnalyst）

**职责**：评估技术面信号强度，输出L1-L4各层评分

**Prompt 模板**：
```
你是一位加密货币合约技术分析师，基于V6.5量化系统评估以下持仓的技术信号。

## 持仓信息
- 交易对: {pair}
- 方向: {direction}（long=做多，short=做空）
- 入场价: {entry}
- 当前价: {current}
- 持仓时间: {hold_min:.0f}分钟
- 当前浮盈/亏: {pnl:.2f}%

## 技术指标（需从数据源获取）
- 15m/30m/1h/4h 量比（当前 / 基线）
- RSI（14周期）
- 布林轨道位置（当前价 / 上轨 / 下轨）
- S/R 支撑/压力位（30m+1h+4h多周期）
- 触底/触顶次数

## V6.5 技术评分标准
| 层级 | 指标 | 满分 | 天禄规则 |
|------|------|------|---------|
| L1 | 量比 >= 2.5x | 30分 | 峰值量过滤 |
| L3 | RSI < 25(做多) / RSI > 75(做空) | 20分 | 超卖超买 |
| L4 | S/R ±1.5% 内 + 触底/触顶 >= 2次 | 25分 | 支撑压力 |

## 你的任务
1. 评估L1量比是否满足（>2.5x=通过，<2.5x=噪音过滤）
2. 评估L3 RSI是否在超卖/超买区间
3. 评估L4 S/R位置是否在支撑/压力位±1.5%内
4. 综合输出技术面评分（0-100）

## 输出格式（严格JSON）
{
  "agent": "TechAnalyst",
  "l1_vol_score": "X分/30分 - 量比X.Xx",
  "l3_rsi_score": "X分/20分 - RSI=X",
  "l4_sr_score": "X分/25分 - S/R类型=support/resistance",
  "tech_total_score": X,
  "tech_verdict": "强信号/中信号/弱信号/噪音过滤",
  "reason": "具体技术分析理由"
}
```

---

#### Agent 2：🛡️ 风控分析师（RiskAnalyst）

**职责**：评估持仓健康度和风控阈值，输出R2评分和强平距离

**Prompt 模板**：
```
你是一位加密货币合约风控专家，基于V6.5风控规则评估以下持仓风险。

## 持仓信息
- 交易对: {pair}
- 方向: {direction}
- 入场价: {entry}
- 当前价: {current}
- 杠杆: ×{lev:.0f}
- 浮盈/亏: {pnl:.2f}%
- 持仓时间: {hold_min:.0f}分钟（{hold_hours:.1f}小时）
- 强平价: {liq}

## R2健康度计算
基础分 = 50
盈亏贡献 = min(30, max(-30, pnl% × 杠杆 × 5))
时间惩罚 = 0（浮盈）| max(-20, -(持时分钟/60 × 2))（浮亏）
R2 = 50 + 盈亏贡献 + 时间惩罚

## R2健康度解读
| R2范围 | 健康度 | 建议动作 |
|--------|--------|---------|
| R2 >= 80 | 🟢 极佳 | 持有，让利润奔跑 |
| R2 60-79 | 🟡 健康 | 持有，观察 |
| R2 40-59 | 🟠 注意 | 考虑半仓或调整止损 |
| R2 20-39 | 🔴 危险 | 考虑全平或DCA |
| R2 < 20 | ⚫ 濒死 | 立即全平止损 |

## 动态止盈档位（{lev:.0f}x杠杆）
| 档位 | 基准触发 | 实际触发 | 建议卖出% |
|------|---------|---------|---------|
| P1   | 基准15% | {p1_t}%  | 50% |
| P2   | 基准25% | {p2_t}%  | {p2_s}% |
| P3   | 基准35% | {p3_t}%  | 100% |

## 强平保护阈值
- 10x: 本金亏损 >= 80% → 强平
- 7x:  本金亏损 >= 60% → 强平
- 5x:  本金亏损 >= 40% → 强平

## 距强平计算
做多: (入场价 - 强平价) / 入场价 × 100%
做空: (强平价 - 入场价) / 入场价 × 100%

## 你的任务
1. 计算R2健康度评分
2. 计算距强平距离百分比
3. 评估动态止盈触发状态（P1/P2/P3/未触发）
4. 给出风控维度的动作建议

## 输出格式（严格JSON）
{
  "agent": "RiskAnalyst",
  "r2_score": X,
  "r2_component": {"base":50, "pnl_contrib":"X", "time_penalty":"X"},
  "dist_to_liquidation_pct": "X%",
  "liquidation_risk": "安全/警戒/危险/极度危险",
  "profit_tier": "P1/P2/P3/未触发",
  "tier_trigger_pct": "X%",
  "tier_sell_pct": "X%",
  "risk_verdict": "安全持仓/注意持仓/危险持仓/濒死持仓",
  "recommended_action": "hold/half_close/full_close/dca_l1/dca_l2",
  "reason": "具体风控分析理由"
}
```

---

#### Agent 3：🗡️ 辩论员（DebateAgent）

**职责**：模拟多空双方立场，辩论1-2轮后收敛

**Prompt 模板**（第一轮 - 各自陈述）：
```
你是一场加密货币合约交易辩论的主持人。

## 背景持仓
{pair} · {direction} · 浮{pnl}% · R2={r2} · {hold_min:.0f}分钟持仓

## 正方论点（TechAnalyst技术面）
立场：{tech_verdict}（信号强度：{tech_score}分）
理由：{tech_reason}

## 反方论点（RiskAnalyst风控面）
立场：{risk_verdict}（R2={r2_score}，强平距离={dist_liq}%）
理由：{risk_reason}

## 辩论规则
1. 正方（Bull）从技术面角度论证持有/加仓的合理性
2. 反方（Bear）从风控角度论证减仓/离场的必要性
3. 双方各提出最强论点
4. 辩论1-2轮后，输出综合裁定

## 第一轮：各自陈述（不超过3句话）
Bull: [正方最强论点，限50字]
Bear: [反方最强论点，限50字]

## 第二轮：反驳与收敛
Bull反驳: [正方回应反方最强论点，限30字]
Bear反驳: [反方回应正方最强论点，限30字]

## 最终裁定（由主持人在双方论点基础上裁定）
最终评级: Buy / Overweight / Hold / Underweight / Sell
核心依据: [最关键的2个论点]
风险提示: [最重要的1个风险]
```

---

#### Agent 4：⚖️ 裁判（JudgeAgent）

**职责**：综合TechAnalyst + RiskAnalyst + DebateAgent三方意见，输出最终裁定

**Prompt 模板**：
```
你是天禄V6.5量化系统的最终裁定官。

## 三方意见汇总

### 🧠 技术分析师（TechAnalyst）
技术评分: {tech_score}分 / 100分
技术判定: {tech_verdict}
关键理由: {tech_reason}

### 🛡️ 风控分析师（RiskAnalyst）
R2健康度: {r2_score}分
强平距离: {dist_liq}%（{liq_risk}）
止盈档位: {profit_tier}
风控动作: {risk_action}

### 🗡️ 辩论裁定
辩论评级: {debate_rating}
辩论理由: {debate_reason}

## 12种场景（天禄V6.5场景分类）
| 场景 | R2范围 | 标签 | 动作 |
|------|---------|------|------|
| 场景1 | R2>=80 | 🏆 S级 | hold |
| 场景2 | R2 60-79 | ✅ A级 | hold |
| 场景3 | R2 40-59 | ⚠️ B级 | hold/half_close |
| 场景4 | R2 20-39 | 🔶 C级 | half_close |
| 场景5 | R2 < 20 | ❌ D级 | full_close |
| 场景6 | 持<3h且R2>=60 | 🆕 新开 | hold |
| 场景7 | 持>24h | ⏰ 长周期 | hold+移动止损 |
| 场景8 | 浮亏>5% | 🔴 止损决策 | full_close |
| 场景9 | Autopilot入场 | 🤖 加强监控 | hold+严格止损 |
| 场景10 | 距强平<20% | 🚨 强平警戒 | full_close |
| 场景11 | 多周期共振 | 🌊 共振 | hold |
| 场景12 | 资金费率>0.01% | 💸 费率套利 | hold分析 |

## 置信度门槛（必须满足才执行）
- full_close: 置信度 >= 70% 才执行
- half_close: 置信度 >= 60% 才执行
- dca_l1/dca_l2: 置信度 >= 55% 才执行
- 不足时自动降级为 hold

## 你的任务
综合三方意见，根据12种场景框架，输出最终裁定。

## 输出格式（严格JSON，不允许额外文字）
{
  "agent": "Judge",
  "scene": "场景1-12",
  "scene_label": "🏆 S级顶级信号",
  "rating": "Buy/Overweight/Hold/Underweight/Sell",
  "action": "hold/full_close/half_close/dca_l1/dca_l2",
  "confidence": 0-100,
  "urgency": "critical/high/medium/low",
  "reason": "综合三方论点的裁定理由（50字内）",
  "r2_score": {r2_score},
  "tier": "P1/P2/P3/未触发",
  "tier_detail": {
    "trigger_pct": "X%",
    "sell_pct": "X%",
    "next_tier_pct": "X%"
  },
  "three_agents_summary": {
    "tech": "{tech_verdict} ({tech_score}分)",
    "risk": "{risk_verdict} (R2={r2_score})",
    "debate": "{debate_rating}"
  },
  "block_reason": "如有拦截原因填此处，否则空",
  "decision_log": "你的完整推理过程"
}
```

---

## 三、记忆系统（Memory & Reflection）

### 3.1 FinancialSituationMemory

参考 TradingAgents 的 `FinancialSituationMemory`，天禄的记忆库：

```python
class TianluSituationMemory:
    """天禄持仓情况记忆库"""

    def __init__(self):
        self.db_path = "data/tianlu_memory.sqlite"

    def add_decision(self, decision: dict):
        """记录每次AI决策"""
        # pair, direction, pnl, r2, action, confidence, scene, verdict

    def get_similar_situations(self, pair: str, direction: str, pnl_range: tuple) -> list:
        """查找历史上类似的持仓情况"""

    def get_mistakes(self, trade_id: int) -> list:
        """记录决策错误，反思改进"""

    def reflect(self, trade_id: int, final_pnl: float, action_taken: str):
        """事后反思：AI决策 vs 实际结果"""
        # 如果 full_close 后价格继续上涨 → AI误判，记录到记忆库
        # 如果 hold 后价格反转下跌 → 风控不足，记录教训
```

### 3.2 反思机制

```python
def reflect_and_remember(ta: TianluDebateGraph, trade_id: int):
    """每次平仓后触发反思"""
    # 1. 获取该持仓的完整决策链
    # 2. 对比实际结果（盈利/亏损）
    # 3. 分析：AI判断哪里对了/错了
    # 4. 更新记忆库，防止重复错误
```

---

## 四、集成方案（Phase 1 → Phase 2 → Phase 3）

### Phase 1：辩论架构接入（下周完成）
- 新增 `TianluDebateGraph` 类，封装4个Agent
- 复用 `local_llm.py`（MiniMax M2.7）
- 复用现有 `knowledge_loader.py`（V6.5规则）
- 接入 `bot_agent_generic.py` 的 `analyze_exit()`
- **仅改动出场决策，入场保持现有逻辑**

### Phase 2：记忆系统
- 新增 `tianlu_memory.py`
- 记录每次决策 + 实际结果对比
- 自动生成"AI决策反思报告"

### Phase 3：自我进化
- 每日自学习：分析昨日决策准确率
- 动态调整置信度门槛
- 根据历史表现自动优化Prompt

---

## 五、文件清单

```
freqtrade_console/bot_agents/
├── debate_graph.py              # 新增：辩论架构主类 TianluDebateGraph
├── agents/
│   ├── tech_analyst.py         # 新增：技术分析师Agent
│   ├── risk_analyst.py         # 新增：风控分析师Agent
│   ├── debate_agent.py          # 新增：辩论员Agent（多空博弈）
│   └── judge_agent.py           # 新增：裁判Agent（最终裁定）
├── memory/
│   ├── situation_memory.py      # 新增：持仓情况记忆库
│   └── reflection.py            # 新增：事后反思机制
└── bot_agent_generic.py         # 修改：analyze_exit() 接入辩论架构
```

---

## 六、关键差异对比

| 维度 | TradingAgents 原版 | 天禄升级版 |
|------|------------------|-----------|
| 市场 | 美股（日线） | 加密货币合约（15m/30m） |
| 分析师 | 4个（基本面/舆情/新闻/技术） | 2个（技术 + 风控） |
| 辩论轮次 | 1-3轮 | 1-2轮（分钟级需快速决策） |
| 数据源 | YFinance/Alpha Vantage | OKX/Gate实时API |
| 执行 | 模拟交易所 | OKX/Gate真实API |
| 记忆 | 长周期股票记忆 | 分钟级合约反思 |
| 评级 | Buy/Hold/Sell（5档） | full_close/half_close/hold（5动作） |

---

## 七、成功标准

升级完成后，AI决策应满足：

| 指标 | 目标 |
|------|------|
| 过早出场率 | < 10%（对比升级前） |
| 误判平仓率 | < 15%（hold后反转超过3%） |
| 置信度门槛拦截率 | > 5%（防止乱平仓） |
| 平均决策置信度 | >= 65% |
| 辩论过程可见性 | 决策时输出三方论点摘要 |

---

*本文档基于 TradingAgents（Apache 2.0 License）辩论框架设计，参考地址：https://github.com/TauricResearch/TradingAgents*
