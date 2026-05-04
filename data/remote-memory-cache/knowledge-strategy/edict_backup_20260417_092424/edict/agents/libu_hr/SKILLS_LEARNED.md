# 吏部 · Agent协作与组织技能库

## 🤖 agent-collaboration-network (多Agent协作网络)

**来源**: neiljo-gy/agent-collaboration-network  
**用途**: Agent注册、发现、消息路由、子网管理

### 核心功能

- Agent注册与发现
- Agent间消息路由
- 技能匹配与路由
- 多Agent群聊协作

### 吏部使用场景

1. **三兄弟协调** - 天禄(主)、天福(Windows)、天禧(备用) 的通信注册
2. **技能发现** - 各省部Agent能力注册与查询
3. **任务分发** - 吏部作为协调者向各Agent派发任务

---

## 👥 agent-team-orchestration (多团队编排)

**来源**: arminnaimi/agent-team-orchestration  
**用途**: 多Agent团队编排，定义角色、任务生命周期、交接协议

### 核心功能

- 多Agent团队角色定义
- 任务生命周期管理
- 交接协议(Handoff Protocols)
- 审核工作流

### 吏部使用场景

1. **团队初始化** - 为新省部Agent定义角色和职责
2. **任务流管理** - 定义任务的创建→执行→审核→完成流程
3. **交接规范** - 当任务需要跨省部时，规范交接格式

---

## 📋 吏部执行清单

- [x] agent-team-orchestration: ✅ **已验证，技能内容已获取** (可手动实现为吏部流程)
  - 核心价值: 定义了Orchestrator/Builder/Reviewer/Ops角色、任务生命周期、交接协议
  - 建议: 直接将吏部改造为符合此框架
- [x] agent-collaboration-network: ✅ **已从GitHub安装** (~/.openclaw/skills/agent-collaboration-network/)
  - ⚠️ 需要 ACN_API_KEY（从 acnlabs 平台申请）
  - 功能: Agent注册、发现、消息路由、子网管理
- [ ] 为钦天监、省内各部建立Agent注册表
- [ ] 定义标准化的任务交接协议（参考agent-team-orchestration框架）
- [ ] 评估ACN平台，决定是否启用agent-collaboration-network

---
*最后更新: 2026-03-30 by 天禄 | 状态: agent-collaboration-network已从GitHub安装*
