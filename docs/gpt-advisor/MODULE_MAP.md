# 模块地图

更新时间：2026-05-04

## 当前阶段

```
P0 CORE TRUE_DEVICE PASSED
Release Candidate: 0.5.5
```

## 根目录

| 路径 | 说明 |
| --- | --- |
| `SOFTWARE_ROADMAP.md` | 软件制作总路线图 |
| `TIMED_PROGRESS_LOG.md` | 定时进度日志 |
| `GPT_DESKTOP_HANDOFF.md` | GPT 桌面版交接信息 |
| `AGENTS.md` | Codex 工程规则 |

## 前端插件

| 路径 | 说明 |
| --- | --- |
| `apps/evenhub-plugin/` | Even Hub 插件前端 |
| `apps/evenhub-plugin/index.html` | 插件 HTML 入口 |
| `apps/evenhub-plugin/src/main.ts` | 前端主逻辑 |
| `apps/evenhub-plugin/src/style.css` | 手机网页样式 |
| `apps/evenhub-plugin/src/glass/` | G2 眼镜端 Glass UI |
| `apps/evenhub-plugin/src/input/` | R1/G2 输入事件归一化 |
| `apps/evenhub-plugin/src/camera/` | 手机相机与截图逻辑 |
| `apps/evenhub-plugin/src/voice/` | G2 麦克风与语音链路；`g2PcmVoiceSession.ts` 为 R0-003 按住说话 / R1 单触录音 / PCM WebSocket 主链路，`g2MicProbe.ts` 为诊断入口 |
| `apps/evenhub-plugin/src/api/` | 前端请求后端 API |
| `apps/evenhub-plugin/app.json` | Even Hub 插件配置与权限 |

## 后端服务

| 路径 | 说明 |
| --- | --- |
| `services/api-server/` | 当前实际 G2 Bridge / API 后端服务 |
| `services/api-server/src/server.ts` | `/vision`、`/ask`、WebSocket `/audio`、`/tts`、`/asr/status` 路由 |
| `services/api-server/src/asrAdapter.ts` | 流式 PCM ASR 适配器，当前 R0-003a 不调用真实 ASR |
| `services/api-server/src/openclaw.ts` | OpenCLAW 适配器 |
| `services/api-server/src/tradingBotAdapter.ts` | 交易机器人只读适配器 |

## 文档

| 路径 | 说明 |
| --- | --- |
| `docs/current-state.md` | 当前状态 |
| `docs/architecture.md` | 架构说明 |
| `docs/acceptance-checklist.md` | 验收清单 |
| `docs/codex-execution-plan-v1.md` | Codex 执行计划 |
| `docs/glass-ui-design.md` | G2 Glass UI 设计约束 |
| `docs/gpt-advisor/` | GPT Advisor 工作台 |
| `docs/gpt-advisor/MODULE_UPGRADE_WORKFLOW.md` | 从 `tianlu_g2_module_plans_codex_prompts` 读取后整理出的后续模块升级工作流 |
| `docs/gpt-advisor/patch-requests/20260502_2048_r0_003_voice_answer_display_and_intent_fix.md` | 下一轮呼叫天禄语音闭环修复任务 |

## 打包输出

| 路径 | 说明 |
| --- | --- |
| `apps/evenhub-plugin/g2-vision-voice-assistant.ehpk` | 英文名 EHPK |
| `apps/evenhub-plugin/g2-视觉-语音助手.ehpk` | 中文名 EHPK |
