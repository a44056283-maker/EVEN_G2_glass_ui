# 尚书省任务协调优化提案

> 提案日期：2026-03-30
> 提案方：尚书省
> 状态：草稿

---

## 一、问题概述

### 1.1 太子调度升级循环问题

**现象：**
- JJC类持续运行任务（JJC-TRADE-BINGBU-001、JJC-TRADE-ZAOCHAO-001、JJC-TRADE-TAIZI-001等）被太子调度系统重复升级为"停滞"状态
- 升级间隔约15分钟，但任务实际持续运行正常
- 每次升级需尚书省人工介入标记完成，效率低下

**根因分析：**
- 太子调度的 `stallThresholdSec` 检测机制未区分"一次性任务"与"持续运行任务"
- 持续运行任务的 `lastProgressAt` 时间戳与当前时间差持续超出阈值
- 任务标记为 Done 后太子调度不再升级，但新任务会再次触发

**影响：**
- 尚书省需持续关注并手动标记Done，浪费人工
- 大量升级通知造成"狼来了"效应，真正需要关注的任务被淹没

---

### 1.2 OC内部会话错误路由问题

**现象：**
- 大量 OC-tianlu-*、OC-shangshu-* 等内部会话任务被错误路由至尚书省请求派发
- 这类任务是用户自己的会话或心跳检测，不是真正需要六部执行的工作任务
- 尚书省持续回复 NO_REPLY，但系统仍在重复发送

**根因分析：**
- 门下省的派发逻辑未正确过滤 OC（OpenClaw内部会话）类型任务
- OC任务应该有独立的路由机制，不应进入"门下省→尚书省→六部"的派发流程
- 太子调度将 OC 会话也当作普通任务监控其"停滞"状态

**影响：**
- 尚书省被大量无效任务淹没
- 真正需要处理的 JJC 工作任务可能被忽略
- 系统资源浪费在无意义的路由和通知上

---

### 1.3 飞书通道默认账号配置问题

**现象：**
- 飞书通信通道默认路由至 Tianfu（二弟/天福）
- 尚书省（shangshu）配置了独立飞书账号，但 `defaultAccount` 指向 Tianfu
- 导致尚书省的飞书消息被 Tianfu 接收

**根因分析：**
- `openclaw.json` 中 `feishu.defaultAccount` 设置为 `tianfu`
- 未正确配置各 Agent 的飞书账号映射
- 修改 `defaultAccount` 后需要 Gateway 热重载生效

**修复记录：**
- 2026-03-22 已将 `feishu.defaultAccount` 从 `tianfu` 改为 `shangsu`

---

## 二、太子调度系统改进建议

### 2.1 任务类型区分机制

**建议增加任务分类：**

| 任务类型 | 特征 | 停滞检测方式 |
|---------|------|-------------|
| 一次性任务 | 有明确开始和结束 | 传统超时检测 |
| 持续运行任务 | 7×24 长期运行 | 状态码检测（非时间差） |
| 会话类任务 | OC-* / 心跳 | 单独路由，不进入派发流程 |

**实现方案：**
```json
{
  "taskCategories": {
    "JJC-*": {
      "type": "work",
      "stallDetection": "progress-update"  // 根据 progress 字段判断
    },
    "OC-*": {
      "type": "session",
      "dispatchFlow": "direct"  // 不经过尚书省派发
    },
    "heartbeat": {
      "type": "system",
      "dispatchFlow": "skip"  // 完全跳过派发流程
    }
  }
}
```

### 2.2 持续运行任务的白名单机制

**建议：**
- 在太子调度配置中增加 `continuousTasksWhitelist`
- 登记已知的持续运行任务ID
- 白名单内任务不进行停滞检测，只监控状态码

**配置示例：**
```json
{
  "scheduler": {
    "continuousTasksWhitelist": [
      "JJC-TRADE-BINGBU-001",
      "JJC-TRADE-ZAOCHAO-001",
      "JJC-TRADE-TAIZI-001"
    ],
    "whitelistStallThreshold": 0  // 0表示不检测
  }
}
```

### 2.3 升级通知去重机制

**建议：**
- 同一任务在 X 分钟内的重复升级只通知一次
- 累积多次升级后升级通知级别（Warning → Alert → Critical）
- 尚书省可配置"忽略"规则，对已知良性升级直接跳过

**实现：**
```json
{
  "escalation": {
    "dedupWindowMinutes": 30,
    "autoSuppressAfter": 5,
    "suppressedEscalationsNotify": "summary-only"
  }
}
```

---

## 三、任务派发流程优化建议

### 3.1 派发前过滤规则

**建议在派发前增加过滤层：**

| 过滤条件 | 动作 |
|---------|------|
| 任务ID以 "OC-" 开头 | 跳过尚书省派发，直接路由至来源Agent |
| 任务标题包含 "heartbeat" | 标记为系统任务，不派发 |
| 任务旨意包含 "heartbeat" | 标记为心跳任务，不派发 |
| 任务状态为 Done/Cancelled | 跳过派发 |
| 任务为自身会话 | 跳过派发 |

**优先级过滤：**
```python
def should_dispatch(task):
    # 1. 过滤OC会话任务
    if task.id.startswith('OC-'):
        return False, "OC会话任务不经过尚书省派发"
    
    # 2. 过滤心跳任务
    if 'heartbeat' in task.title.lower() or 'heartbeat' in task.intent.lower():
        return False, "心跳任务不派发"
    
    # 3. 过滤已完成任务
    if task.state in ['Done', 'Cancelled']:
        return False, "任务已结束"
    
    # 4. 过滤自身会话
    if task.id.startswith('OC-shangshu-'):
        return False, "尚书省自身会话不派发"
    
    return True, "需要派发"
```

### 3.2 尚书省入队限流

**问题：**
- 大量 OC 心跳任务同时入队可能造成尚书省过载

**建议：**
- 尚书省任务处理队列设置最大并发（如 5 个 subagent）
- 超出并发的任务进入等待队列
- 设置任务优先级，JJC 工作任务优先于其他

### 3.3 任务状态回传优化

**当前流程：**
```
六部执行完成 → 尚书省汇总 → 回传中书省
```

**优化建议：**
- 六部执行完成后可直接回传中书省（尚书省仅做协调记录）
- 尚书省只在大面积失败或需要协调时才介入
- 增加"自动汇总"功能，尚书省可配置何时自动汇总

---

## 四、飞书通信配置优化

### 4.1 多Agent飞书账号隔离

**建议：**
- 每个 Agent 有独立的飞书 App 配置
- 在 `openclaw.json` 中明确映射：

```json
{
  "feishu": {
    "accounts": {
      "shangshu": {
        "appId": "cli_xxx_shangshu",
        "appSecret": "xxx"
      },
      "tianfu": {
        "appId": "cli_xxx_tianfu",
        "appSecret": "xxx"
      }
    },
    "defaultAccount": "shangshu",
    "agentAccountMapping": {
      "shangshu": "shangshu",
      "tianfu": "tianfu"
    }
  }
}
```

### 4.2 飞书消息路由规则

**建议增加路由规则：**
- 根据 Agent ID 选择对应的飞书账号
- 紧急任务使用高优先级通道
- 非紧急通知使用低优先级通道

---

## 五、监控与告警优化

### 5.1 尚书省Dashboard

**建议增加监控面板：**
- 当前派发任务列表及状态
- 六部执行进度
- 升级任务队列
- 系统健康状态

### 5.2 告警分级

| 级别 | 条件 | 通知方式 |
|-----|------|---------|
| P0 | 任务失败 + 影响核心业务 | 立即通知 + 电话 |
| P1 | 任务停滞 > 1小时 | 飞书通知 |
| P2 | 任务超时但仍在运行 | 记录日志 |
| P3 | 系统警告（如大量OC任务） | 静默记录 |

### 5.3 自动恢复机制

**建议：**
- 太子调度增加"自动恢复"能力
- 检测到任务实际在运行时，自动更新 `lastProgressAt` 时间戳
- 减少误升级概率

---

## 六、实施计划

### Phase 1：紧急修复（1-2天）
- [ ] 修复太子调度对持续运行任务的误判
- [ ] 增加 OC/heartbeat 任务过滤规则
- [ ] 验证飞书账号配置生效

### Phase 2：短期优化（1周）
- [ ] 实现任务分类机制
- [ ] 增加白名单机制
- [ ] 优化升级通知去重

### Phase 3：长期优化（1个月）
- [ ] 尚书省Dashboard
- [ ] 自动汇总功能
- [ ] 多Agent飞书隔离

---

## 七、预期收益

| 优化项 | 当前状态 | 优化后 |
|-------|---------|--------|
| 误升级次数 | 每天约50-100次 | <5次 |
| 尚书省无效操作 | 每小时约10-20次 | <1次 |
| 任务派发准确率 | ~60% | >95% |
| 飞书消息路由延迟 | 不确定 | <1秒 |

---

## 八、附录

### A. 相关配置文件
- `/Users/luxiangnan/.openclaw/openclaw.json`
- `/Users/luxiangnan/.openclaw/workspace-shangshu/scripts/kanban_update.py`

### B. 受影响任务ID记录
- JJC-TRADE-BINGBU-001（已标记Done，停止升级）
- JJC-TRADE-ZAOCHAO-001（已标记Done，停止升级）
- JJC-TRADE-TAIZI-001（已标记Done，停止升级）
- OC-tianlu-* 系列（持续出现，建议路由优化）
- OC-shangshu-* 系列（持续出现，建议路由优化）

### C. 太子调度升级记录（部分）
```
JJC-TRADE-BINGBU-001: 48694秒停滞（误判）
JJC-TRADE-ZAOCHAO-001: 48694秒停滞（误判）
JJC-TRADE-TAIZI-001: 48694秒停滞（误判）
```

---

**提案完成**
尚书省 | 2026-03-30
