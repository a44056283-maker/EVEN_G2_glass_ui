# Codex 子智能体任务清单

## Agent A：crash-log-agent

交付：

```text
docs/gpt-advisor/audits/YYYYMMDD_HHMM_crash_log_audit.md
runtimeErrorReporter.ts
server logger patch
safeGlassShow 错误记录
R1 防抖
```

## Agent B：location-vision-agent

交付：

```text
locationContext.ts
设置页定位开关
vision prompt 定位上下文
定位失败不阻塞
```

## Agent C：photo-preview-history-agent

交付：

```text
拍照后 G2 文本预览确认
手机端缩略图
historyStore.ts
IndexedDB + localStorage + memory fallback
历史错误提示
```

## Agent D：vision-accuracy-agent

交付：

```text
visionPromptBuilder.ts
低置信度复核
OpenCLAW 记忆上下文
可选 web search 开关
```

## Agent E：trading-cache-focus-agent

交付：

```text
trading submenu focus state
trading cache TTL
loading/waiting words
white-list price minimal G2 page
```

## Agent F：qa-release-agent

交付：

```text
typecheck/build/pack:g2
3轮真机验收矩阵
EHPK SHA256
是否可上架结论
```
