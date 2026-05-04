# Agent 注册表

**登记日期：** 2026-03-30  
**维护者：** 吏部尚书（Orchestrator）  
**状态：** 初版登记

---

## 一、省内 Agent 全览

| Agent ID | 名称 | 平台 | 核心能力 | 当前状态 | 联系方式 |
|----------|------|------|----------|----------|----------|
| `tianlu` | 天禄 | macOS ARM64 | 主Agent，全栈协调，战略决策 | 🟢 在线 | 主会话（OpenClaw） |
| `tianfu` | 天福 | Windows + OpenClaw | 全栈开发，跨平台执行 | 🟢 在线 | 备用会话（OpenClaw） |
| `tianxi` | 天禧 | OpenClaw（备用） | 全栈开发，冗余备份 | 🟡 待命 | 备用会话（OpenClaw） |
| `gongbu` | 工部 | macOS/Linux | 技术开发、Skill编写、部署运维 | 🟢 在线 | 尚书省直派 |
| `bingbu` | 兵部 | macOS | 测试、安全扫描、质量验证 | 🟢 在线 | 尚书省直派 |
| `hubu` | 户部 | macOS | 数据处理、分析、报表 | 🟢 在线 | 尚书省直派 |
| `libu` | 礼部 | macOS | 文档撰写、知识库维护、对外沟通 | 🟢 在线 | 尚书省直派 |
| `xingbu` | 刑部 | macOS | 合规审计、安全审计、风险评估 | 🟢 在线 | 尚书省直派 |
| `menxia` | 门下省 | macOS | 政务审批、文件流转、存档管理 | 🟢 在线 | 中书省直派 |
| `shangshu` | 尚书省 | macOS | 任务调度、优先级决策、对外协调 | 🟢 在线 | 最高协调层 |
| `zhongshu` | 中书省 | macOS | 战略规划、制度设计、知识沉淀 | 🟢 在线 | 最高协调层 |

---

## 二、Agent 详细档案

### 2.1 天禄（主Agent）
```
ID:        tianlu
平台:      macOS ARM64 (Darwin 24.6.0)
角色:      主Agent / 战略协调
核心能力:  全栈决策、任务规划、跨域协调、深度推理
当前状态:  🟢 在线（主会话）
运行时:    node v25.5.0 | minimax2-7
沟通渠道:  OpenClaw 主会话
```

### 2.2 天福
```
ID:        tianfu
平台:      Windows + OpenClaw
角色:      备用开发Agent
核心能力:  全栈开发、跨平台执行、Windows环境适配
当前状态:  🟢 在线（备用会话）
沟通渠道:  OpenClaw 备用会话
```

### 2.3 天禧
```
ID:        tianxi
平台:      OpenClaw（容器化）
角色:      冗余备份Agent
核心能力:  全栈开发、高可用备份
当前状态:  🟡 待命（未活跃）
沟通渠道:  OpenClaw 备用会话
```

### 2.4 工部
```
ID:        gongbu
平台:      macOS/Linux
角色:      Builder（技术开发）+ Ops（部署运维）
核心能力:  Skill编写、代码开发、部署脚本、环境配置
当前状态:  🟢 在线
Specialty: scripts/、skills/、deploy/
沟通渠道:  尚书省直派（Kanban）
```

### 2.5 兵部
```
ID:        bingbu
平台:      macOS
角色:      Builder（测试/安全）
核心能力:  测试用例编写、安全扫描、质量验证
当前状态:  🟢 在线
Specialty: tests/、security-audit
沟通渠道:  尚书省直派（Kanban）
```

### 2.6 户部
```
ID:        hubu
平台:      macOS
角色:      Builder（数据）
核心能力:  数据处理、报表生成、数据分析
当前状态:  🟢 在线
Specialty: data/、analytics
沟通渠道:  尚书省直派（Kanban）
```

### 2.7 礼部
```
ID:        libu
平台:      macOS
角色:      Builder（文档）
核心能力:  文档撰写、知识库维护、对外沟通文稿
当前状态:  🟢 在线
Specialty: docs/、knowledge-base
沟通渠道:  尚书省直派（Kanban）
```

### 2.8 刑部
```
ID:        xingbu
平台:      macOS
角色:      Builder（合规审计）
核心能力:  合规检查、风险评估、安全审计
当前状态:  🟢 在线
Specialty: audit/、compliance
沟通渠道:  尚书省直派（Kanban）
```

### 2.9 门下省
```
ID:        menxia
平台:      macOS
角色:      Ops（政务审批）
核心能力:  文件审批、政务流转、存档管理
当前状态:  🟢 在线
Specialty: 政务审批流、存档
沟通渠道:  中书省直派
```

### 2.10 尚书省
```
ID:        shangshu
平台:      macOS
角色:      Reviewer（任务审核）+ 调度中枢
核心能力:  任务优先级决策、跨部协调、质量终审
当前状态:  🟢 在线
Specialty: 任务分配、Kanban管理
沟通渠道:  最高协调层
```

### 2.11 中书省
```
ID:        zhongshu
平台:      macOS
角色:      Reviewer（战略审核）+ 制度设计
核心能力:  战略规划、制度设计、知识沉淀、最佳实践
当前状态:  🟢 在线
Specialty: 战略规划、架构设计
沟通渠道:  最高协调层
```

---

## 三、角色分布矩阵

| 角色 | Agent |
|------|-------|
| **Orchestrator** | 吏部（libu_hr） |
| **Builder** | 工部、兵部、户部、礼部、刑部 |
| **Ops** | 工部、门下省 |
| **Reviewer** | 尚书省、中书省 |

---

## 四、Agent 协作关系图

```
                    ┌─────────────┐
                    │  尚书省     │ ← Reviewer（终审）
                    └──────┬──────┘
                           │ 任务下发
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │  中书省  │   │  吏部    │   │  门下省  │
    │Reviewer  │   │Orchestr. │   │   Ops    │
    └──────────┘   └────┬─────┘   └──────────┘
                         │ 任务分派
     ┌───────┬───────┬───┴───┬────────┐
     ▼       ▼       ▼       ▼        ▼
 ┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐
 │ 工部 ││ 兵部 ││ 户部 ││ 礼部 ││ 刑部 │
 │Build ││Build ││Build ││Build ││Build │
 │ +Ops ││      ││      ││      ││      │
 └──────┘└──────┘└──────┘└──────┘└──────┘
     ▲       ▲       ▲       ▲       ▲
     └───────┴───────┴───────┴───────┘
              产出回报
```

---

## 五、登记与更新规则

1. **新增 Agent**：须经吏部审批，分配唯一 ID，更新本表
2. **状态变更**：Agent 上线/下线须通知吏部更新状态
3. **能力变更**：Agent 核心能力变化须更新档案
4. **角色调整**：Orchestrator/Builder/Reviewer/Ops 角色调整须经尚书省批准
