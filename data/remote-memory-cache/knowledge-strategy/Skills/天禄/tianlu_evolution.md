---
name: tianlu-evolution
description: 天禄自我进化系统 - 基于 Claude Code 架构的记忆管理、预算追踪、反思与安全检查。当需要：(1)记录重要事件到记忆系统 (2)检查当前预算状态 (3)进行操作前安全确认 (4)反思提炼规律 (5)执行每日/会话复盘 时触发。
---

# tianlu-evolution - 天禄自我进化系统

基于 Claude Code 源码泄露事件架构：**简单循环 + 分层记忆 + 预算约束 + 安全层**。

## 核心脚本

| 脚本 | 用途 | 触发场景 |
|------|------|----------|
| `scripts/budget_tracker.py` | Token/步骤/时间预算追踪 | 每次行动前、状态查询 |
| `scripts/memory_manager.py` | L0-L4 分层记忆管理 | 记录事件、搜索记忆 |
| `scripts/reflection.py` | 反思与规律提炼 | 会话结束、每日复盘 |
| `scripts/security_checker.py` | 操作风险分类与预检查 | 任何写/删/执行操作前 |
| `scripts/frontmatter_skill_parser.py` | 标准Markdown Frontmatter解析 | 技能加载时 |
| `scripts/structured_memory.py` | 结构化记忆系统（memdir） | 记忆读写 |
| `scripts/cost_tracker.py` | 增强成本追踪（多模型+持久化） | API调用记录 |
| `scripts/buddy_system.py` | 虚拟宠物伙伴系统 | `/buddy feed/play/sleep/work/chat` |

## 快速使用

### 预算检查
```bash
python3 ~/.openclaw/skills/tianlu-evolution/scripts/budget_tracker.py
```

### 记忆记录
```python
from scripts.memory_manager import MemoryManager
mm = MemoryManager()
mm.append_l2("执行了XXX操作", tag="操作记录")
```

### 安全预检
```python
from scripts.security_checker import SecurityChecker
sc = SecurityChecker()
can, reason, warnings = sc.pre_op_check("rm /tmp/test", "/tmp/test")
```

### 反思记录
```python
from scripts.reflection import ReflectionEngine
re = ReflectionEngine()
re.record("exec", "curl api", False, "timeout error", 100)
re.save_session_summary("20260401-1120")
```

## 分层记忆系统

| 层级 | 存储 | 生命周期 |
|------|------|----------|
| L0 | 会话上下文 | 会话结束丢弃 |
| L1 | `workspace-main/sessions/YYYYMMDD-HHMMSS/` | 30天 |
| L2 | `workspace-main/memory/YYYY-MM-DD.md` | 7天→归档 |
| L3 | `workspace-main/MEMORY.md` | 永久 |
| L4 | `workspace-main/memory/archive/` | 参考 |

## 预算阈值

- **60%** Token → 🟡 警告
- **85%** Token → 🔴 停止生成
- **95%** Token → 🚨 紧急，保存状态

## 安全风险等级

- **LOW**: 读取/搜索 → 自动放行
- **MEDIUM**: 写文件(trash) → 确认
- **HIGH**: 执行/发送 → 明确确认
- **CRITICAL**: 删除系统 → 双重确认

## 核心循环

```
while (budget_remaining):
    1. OBSERVE    → 读取输入、上下文
    2. THINK      → 规划行动
    3. ACT        → 执行单个原子动作
    4. REFLECT    → 记录、评估、更新记忆
```

详细架构见 `references/ARCHITECTURE.md`
