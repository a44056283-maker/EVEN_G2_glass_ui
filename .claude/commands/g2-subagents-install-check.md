---
description: 检查 Day1 子代理是否已安装
---

# 子代理安装检查

## 检查项

### agents 目录

```
.claude/agents/
├── g2-r1-state-agent.md
├── g2-glass-ui-agent.md
├── g2-voice-intent-agent.md
├── g2-trading-ui-agent.md
├── g2-qa-release-agent.md
└── g2-report-sync-agent.md
```

### commands 目录

```
.claude/commands/
├── g2-day1-subagent-sprint.md
├── g2-subagents-install-check.md
├── g2-apply-gpt-review.md
├── g2-make-review-bundle.md
└── g2-check-cloud.md
```

### 其他文件

```
DAY1_SPRINT_MASTER_PROMPT.md
GPT_REVIEW_DAY0_20260504_1145.md
04_GPT_REVIEW_RESPONSES/
```

## 输出格式

```
子代理安装检查:
✓ g2-r1-state-agent.md
✓ g2-glass-ui-agent.md
...
✗ missing-file.md

状态: INSTALLED / PARTIAL / MISSING
```