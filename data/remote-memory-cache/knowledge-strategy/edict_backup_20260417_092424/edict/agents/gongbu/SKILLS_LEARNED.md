# 工部 · 开发与数据技能库

## 🛠️ arc-skill-gitops (技能部署与版本管理)

**来源**: trypto1019/arc-skill-gitops  
**用途**: OpenClaw技能的自动化部署、回滚、版本管理

### 核心功能

- 技能版本管理
- 自动部署到指定环境
- 回滚到上一稳定版本
- 部署状态验证

### 工部使用场景

1. **技能自动化发布** - 当尚书省派发新技能时，快速部署到各环境
2. **版本回滚** - 技能出问题快速回退
3. **多环境同步** - Dev/Staging/Production环境一致

---

## 🔧 arc-trust-verifier (技能安全审计)

**来源**: trypto1019/arc-trust-verifier  
**用途**: 验证ClawHub技能的安全性和可信度

### 核心功能

- 技能来源验证
- 权限范围检查
- 安全扫描(VirusTotal)
- 信任分数计算

### 工部使用场景

1. **安装前审计** - 安装新技能前进行安全检查
2. **定期巡检** - 扫描现有技能是否有异常
3. **合规报告** - 生成技能安全审计报告

---

## 📊 yahooquery / yfinance (数据获取)

**安装**: `pip install yahooquery`  
**无需API Key**

### 工部整合方式

```python
from yahooquery import Ticker
import pandas as pd

# 获取数据
btc = Ticker('BTC-USD')
df = btc.history(period='1mo', interval='1d')

# 输出CSV供其他系统使用
df.to_csv('btc_daily.csv')
```

### 工部使用场景

1. **数据管道** - 为回测系统提供历史价格数据
2. **因子计算** - 计算技术指标(MACD, RSI等)
3. **批量下载** - 支持多个标的并行获取

---

## ⚡ 工部执行清单

- [x] yahooquery: ✅ **已安装可用** (pip3 install --break-system-packages yahooquery)
- [x] arc-skill-gitops: ✅ **已从GitHub安装** (~/.openclaw/skills/arc-skill-gitops/)
  - 依赖: python3, git
  - 功能: 技能版本快照/回滚/部署
- [x] arc-trust-verifier: ✅ **已从GitHub安装** (~/.openclaw/skills/arc-trust-verifier/)
  - 依赖: python3
  - 功能: 技能安全审计、信任评分
- [ ] 将 yahooquery 集成到数据管道
- [ ] 用 arc-skill-gitops 建立技能版本管理文档
- [ ] 用 arc-trust-verifier 对已安装技能做安全审计

---
*最后更新: 2026-03-30 by 天禄 | 状态: arc-skill-gitops+arc-trust-verifier已安装*
