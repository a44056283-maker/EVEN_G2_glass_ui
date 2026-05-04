# 门下省 · 舆情监测技能库

## 🔍 trending-news-aggregator (热点新闻聚合)

**用途**: 多平台热点新闻聚合，智能分类，热度评分  
**无需API Key**

### 核心功能

1. **多平台热点聚合** - 微博、知乎、百度、微信等
2. **智能分类** - 科技/财经/社会/国际/娱乐
3. **热度评分** - 基于排名×频次×时效加权
4. **增量检测** - 标记新增热点
5. **AI趋势分析** - 一句话总结热点趋势

### 使用方法

**手动触发**:
```
获取今日热点新闻
```

**详细指令**:
```
【综合热点聚合】
1) 使用web_search搜索各平台热点新闻
2) 关键词智能分类：科技/财经/社会/国际/娱乐
3) 热度计算：按排名+频次+时效加权
4) 增量检测：标记新增热点
5) AI趋势分析
6) 输出：总新闻：X条 | 新增：X条
```

**定时任务** (建议每天9:00、12:00、18:00、22:00):
```yaml
cron:
  schedule: "0 9,12,18,22 * * *"
  payload:
    kind: "agentTurn"
    message: "执行综合热点聚合，输出分类热点+热度评分+趋势分析"
```

---

## 📰 crypto-watcher (加密钱包监控)

**用途**: 监控加密钱包余额、DeFi仓位、Gas价格、鲸鱼转账  
**无需API Key**

### 核心功能

```bash
# 查看所有仓位
crypto-watcher status

# 查看指定钱包
crypto-watcher status main

# 实时Gas
crypto-watcher gas

# DeFi仓位 (via DefiLlama)
crypto-watcher defi 0x1234...abcd
```

### 配置文件 (~/.config/crypto-watcher/config.json)

```json
{
  "wallets": [
    { "address": "0x...", "name": "main", "chains": ["eth", "arb", "base"] }
  ],
  "alerts": {
    "gasThreshold": 20,
    "balanceChangePercent": 5,
    "healthFactorMin": 1.5
  }
}
```

### 门下省使用场景

1. **舆情辅助** - 监控大户地址异动判断市场情绪
2. **Gas监控** - Gas<15gwei时是L1最佳操作窗口
3. **DeFi健康度** - 监控仓位健康因子，避免清算

---

## 🔬 agent-deep-research (深度研究)

**用途**: Gemini驱动的深度研究，适合宏观分析、项目研究  
**需要**: GOOGLE_API_KEY + uv

### 核心功能

```bash
# 启动深度研究
uv run {baseDir}/scripts/research.py start "问题"

# 预估成本
uv run {baseDir}/scripts/research.py start "问题" --dry-run

# RAG基于本地文档研究
uv run {baseDir}/scripts/research.py start "问题" --context ./文档目录

# 输出报告
uv run {baseDir}/scripts/research.py start "问题" --output report.md
```

### 门下省使用场景

1. **宏观研究** - 美联储政策、全球宏观经济分析
2. **项目研究** - 深度研究某个DeFi协议或项目
3. **竞品分析** - 对比多个交易平台的服务

---

## 📊 门下省执行清单

- [ ] trending-news-aggregator: ⚠️ 需要Node.js依赖，需clawhub安装 (npm/node已安装)
- [ ] crypto-watcher: ⚠️ 需要Node.js CLI工具，需clawhub安装
- [ ] agent-deep-research: ❌ 需要GOOGLE_API_KEY，当前未配置
- [ ] 设置每日四次热点聚合定时任务（可手动实现，不依赖技能）

---
*最后更新: 2026-03-30 by 天禄 | 状态: 依赖GOOGLE_API_KEY，需配置后使用*
