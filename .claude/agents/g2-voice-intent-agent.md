---
description: G2 语音意图路由代理
---

# G2 语音意图代理

## 职责

路由语音转文字后的意图，分发到视觉/交易/普通问答。

## 核心任务

1. **意图关键词检测**
   - 视觉意图：看一看、这是什么、帮我看看、看下前面
   - 交易意图：交易、持仓、收益、机器人
   - 普通问答：其他所有

2. **视觉意图处理**
   - 优先复用 `lastVisionResult`
   - 无结果时触发拍照流程

3. **交易意图处理**
   - 调用 `/trading/overview`
   - 复用 MiniMax-M2.7 评测

## 关键文件

- `apps/evenhub-plugin/src/voice/handleTranscript.ts`
- `apps/evenhub-plugin/src/voice/routeVoiceIntent.ts`

## 验收标准

- [ ] "帮我看看" 触发视觉
- [ ] "交易状态如何" 触发交易查询
- [ ] 普通问题走 MiniMax 问答