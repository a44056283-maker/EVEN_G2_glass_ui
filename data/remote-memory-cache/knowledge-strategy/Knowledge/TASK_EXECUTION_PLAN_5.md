# 五大任务执行计划

> 创建时间: 2026-04-18 17:36
> 太子（天禄）执行

---

## 任务总览

| 优先级 | 任务 | 工作量 | 价值 | 状态 |
|--------|------|--------|------|------|
| P0 | 辩论架构接入 | 2周 | 补足决策机制最后缺口 | 🚧 规划中 |
| P1 | JSON知识缓存 | 1天 | AI决策提速5倍 | 🚧 规划中 |
| P1 | truth_registry反馈闭环 | 2天 | 知识有真假验证 | 🚧 规划中 |
| P2 | external_signals自动接入 | 1天 | 知识与市场实时同步 | 🚧 规划中 |
| P2 | Hubu知识归集索引 | 1天 | 知识有索引不遗漏 | 🚧 规划中 |

---

## 目录结构

```
~/.openclaw/workspace-tianlu/Knowledge/
├── debate/                    # 辩论架构
│   ├── TianluDebateGraph.json
│   ├── confidence_calibration.json
│   └── shadow_mode_log.json
├── cache/                    # JSON知识缓存
│   ├── knowledge_cache.json
│   └── cache_generator.py
├── truth_registry/           # 交易结果反馈闭环
│   ├── truth_registry.json
│   └── truth_updater.py
└── external_signals/         # 外部数据自动接入
    ├── external_signals.json
    └── signal_fetcher.py

~/.openclaw/workspace-hubu/memory/learning/
└── KNOWLEDGE_INDEX.md       # 户部知识归集索引
```

---

## Task 1: 辩论架构（P0）

### 目标
为六部架构增加辩论决策机制，四角色互相辩驳

### 四角色
- **TechAnalyst**: 技术面分析
- **RiskAnalyst**: 风险分析
- **DebateAgent**: 辩论发起者
- **JudgeAgent**: 最终裁决者

### 执行阶段
- Week 1: 实现 TianluDebateGraph（辩论架构）
- Week 2: Shadow Mode收集置信度真实数据
- Week 3: 根据真实数据校准阈值

### 参考
- 天眼AI_Agent工作流_天禄实现版.md
- AI子代理UI架构与系统接入方案.md

---

## Task 2: JSON知识缓存（P1）

### 目标
将.md知识库提炼为JSON缓存，AI检索速度提升5倍

### 格式
```json
{
  "rules": [
    {
      "id": "rule_001",
      "trigger": "VOL>=3x AND RSI<25",
      "action": "做多",
      "source": "daily_learning_2026-04-15",
      "confidence": 0.85,
      "validated": false,
      "validated_count": 0
    }
  ],
  "last_updated": "2026-04-18T17:00:00+08:00"
}
```

### 执行
- 子代理每周自动从.md生成JSON缓存
- 生成脚本: cache_generator.py

---

## Task 3: truth_registry反馈闭环（P1）

### 目标
知识库有真假验证，与真实交易结果挂钩

### 格式
```json
{
  "validated": [
    {
      "rule": "VOL>=3x AND RSI<25 → 做多",
      "from": "04-15交易",
      "result": "盈利+8U",
      "timestamp": "2026-04-15T22:00:00+08:00",
      "gain": 8.0
    }
  ],
  "invalidated": [
    {
      "rule": "VOL>=5x → 强信号",
      "from": "04-12交易",
      "result": "亏损-9U",
      "timestamp": "2026-04-12T22:00:00+08:00",
      "loss": -9.0
    }
  ]
}
```

### 执行
- 每日收盘后，子代理读取交易结果更新truth_registry
- 更新脚本: truth_updater.py

---

## Task 4: external_signals自动接入（P2）

### 目标
外部市场数据（资金费率/多空比）自动进入知识库

### 数据源
- 资金费率 > 0.01% → 触发场景12分析
- 多空比 > 1.5 → 过热预警
- 恐惧贪婪 < 25 → 极端恐慌机会

### 格式
```json
{
  "funding_rate": {
    "value": 0.0032,
    "exchange": "binance",
    "timestamp": "2026-04-18T17:35:00+08:00"
  },
  "long_short_ratio": {
    "value": 1.23,
    "exchange": "binance",
    "timestamp": "2026-04-18T17:35:00+08:00"
  },
  "fear_greed": {
    "value": 45,
    "timestamp": "2026-04-18T17:00:00+08:00"
  },
  "alerts": []
}
```

### 执行
- bot_agent_generic.py每轮扫描自动更新
- 每5分钟更新一次

---

## Task 5: Hubu知识归集索引（P2）

### 目标
为户部建立知识索引，快速检索不遗漏

### 索引内容
- 所有子代理的输出知识
- 所有daily_learning文件
- 所有strategy文件

### 格式
```markdown
# 户部知识归集索引

## 按类别索引
### 交易策略
- [file path] - 描述

### 风险控制
- [file path] - 描述

### 行为金融
- [file path] - 描述

## 按时间索引
- 2026-04: [files...]
- 2026-03: [files...]

## 最近更新
- 2026-04-18: daily_learning_2026-04-18.md
```

---

## Cron定时任务

| 时间 | 任务 | 说明 |
|------|------|------|
| 14:00 | 每日学习 | 读取知识库学习 |
| 14:05 | 同步到外挂硬盘 | 每日学习后立即同步 |
| 每5分钟 | external_signals更新 | 外部数据刷新 |
| 每日收盘后 | truth_registry更新 | 交易结果录入 |
| 每周一 | 知识缓存生成 | 从.md生成JSON缓存 |
| 每周一 | Hubu索引更新 | 户部知识归集 |

---

## 执行记录

### 2026-04-18
- [x] 创建目录结构
- [x] 创建初始JSON模板
- [x] 创建cache_generator.py (133条规则已提取)
- [x] 创建truth_updater.py
- [x] 创建signal_fetcher.py
- [x] 创建tianlu_debate_graph.py (辩论架构)
- [x] 创建knowledge_indexer.py (户部索引)
- [x] 设置Cron任务 (4个)
