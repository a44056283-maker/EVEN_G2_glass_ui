# 20260502_2114 呼叫天禄语音回答与交易路由修复报告

## 本轮范围

本轮只修呼叫天禄语音模块中的三类问题：

1. 手机网页圆形语音按钮按住录音容易被触摸事件打断。
2. 交易类语音问题仍走旧 `/ask` 路径，可能返回 mock 或过短摘要。
3. 普通问答中的无效占位回答过滤不够强。

未修改：

- R1 视觉相机控制。
- 视觉识别上传链路。
- OpenCLAW 写操作。
- 交易真实写接口。
- Glass UI 大重构。

## 修改文件

- `apps/evenhub-plugin/src/main.ts`
- `apps/evenhub-plugin/src/style.css`
- `services/api-server/src/server.ts`

## 关键修复

### 1. 语音按钮按压稳定性

- 为圆形语音按钮增加 `touch-action: none`、`user-select: none`。
- `pointercancel` 不再结束录音，只提示“触摸被系统打断，录音仍继续”。
- 增加 `phoneHoldMaxTimer`，录音提前结束后会清理 120 秒上限计时器，避免后续残留定时器误触发。

### 2. 交易语音问答

`handleTradingVoiceIntent()` 不再调用旧 `runAssistantQuestion()`，改为：

```text
语音转文字
→ isTradingVoiceIntent
→ getTradingOverview()
→ formatTradingOverviewSummary()
→ renderTradingOverview()
→ G2/网页显示
→ 语音朗读
```

这样语音问“交易状态 / 持仓 / 收益 / 风险 / 白名单价格”会复用公网 9099 实时只读源和 MiniMax-M2.7 交易评测，不再使用旧 mock 简答。

### 3. 占位回答过滤

前端和后端都增强了无效回答过滤：

- “我已收到问题”
- “收到问题”
- “把结果直接显示”
- “Telegram / 电报 / TG / 第三方平台”

命中后前端会显示：

```text
天禄没有拿到有效回答，请再问一次或换个说法。
```

## 验证

```text
npm run typecheck  通过
npm run build      通过
npm run pack:g2    通过
```

## EHPK

```text
apps/evenhub-plugin/g2-vision-voice-assistant.ehpk
```

SHA256：

```text
cd037732f28db27c096bcffc326b7435ee38d59331df5a8132d763dc201da236
```

## 仍需真机验证

1. 手机网页圆形按钮按住 10-20 秒是否还会提前中断。
2. 语音问“交易机器人现在持仓怎么样”是否显示公网实时交易概览和 MiniMax 评测。
3. 普通问答是否还出现“我已收到问题，会把结果显示在这里”这类占位回答。
4. G2/R1 电量读取仍不稳定，R1 仍可能显示 `--`，需单独排查 SDK device info/status 字段。

## 下一步建议

下一轮优先修：

1. 语音普通问答 `/ask` 的真实 MiniMax 回答质量与错误兜底。
2. 视觉意图自动切换：识别到“看一看 / 这是什么”后进入现有视觉拍照流程。
3. R1 电量字段映射与设备状态日志。
