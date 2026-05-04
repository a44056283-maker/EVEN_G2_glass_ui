# 20260502_2158 Voice Recording Duration And Answer Fallback Report

## Scope

本轮只修复呼叫天禄语音模块的两个关键问题：

1. 手机/网页端按住说话录音容易提前结束或 ASR 空结果诊断不清。
2. 通用问答仍可能显示“我已收到问题，会把结果直接显示在这里”这类占位回答。

未修改 R1 视觉相机控制、交易真实接口、OpenCLAW 控制逻辑、Glass UI 大结构。

## Changes

### apps/evenhub-plugin/src/voice/phoneMicRecorder.ts

- 在 `MediaRecorder.stop()` 前调用 `recorder.requestData()`。
- 目的：强制刷新最后一段音频 chunk，减少“按住说话录了但上传音频不完整”的问题。

### apps/evenhub-plugin/src/main.ts

- `getVoiceRecordMaxMs()` 现在默认保证最长录音为 120 秒，避免旧 localStorage 配置仍停留在 30 秒。
- 手机/耳机麦克风 ASR 空文本提示加入录音大小和录音时长。
- 新增前端通用回答兜底：
  - 如果后端或公网旧服务仍返回占位回答，会在前端拦截。
  - 对“附近有什么好吃好玩/古迹/旅游”等问题给出直接可用的通用建议。
  - 不再把“稍后发送 Telegram/结果会显示在这里”作为最终回答展示。

## ASR Status

本地与公网 `/asr/status` 均返回：

```json
{"available":true,"provider":"http","message":"HTTP ASR 已配置。"}
```

说明当前真实 ASR 入口已配置为 HTTP ASR。

## Verification

Commands:

```bash
npm run typecheck
npm run build
npm run pack:g2
shasum -a 256 apps/evenhub-plugin/g2-vision-voice-assistant.ehpk
```

Results:

- typecheck: passed
- build: passed
- pack:g2: passed

EHPK:

```text
apps/evenhub-plugin/g2-vision-voice-assistant.ehpk
```

SHA256:

```text
41cab673e06cbc3d0daa8a0e2b09c6d7fff47475a082ceca13ffc1a28a8b94c7
```

## Remaining Risks

1. 如果真实录音音量太低或环境噪音过强，本地 Whisper 仍可能返回空文本。
2. 如果线上服务进程没有重启，后端旧占位回答仍可能存在；本轮已在前端增加兜底拦截。
3. G2 原生麦克风是否稳定上报 PCM 仍需要真机持续测试。

## Next

建议下一步专项处理：

1. 真机验证按住说话是否能完整录到 10-20 秒语音。
2. 如果仍出现 ASR 空文本，抓取一次 Voice Debug 中的 `sizeBytes / durationMs / mimeType / provider`，再调整本地 Whisper 输入格式。
3. 继续修复交易模块：只读取 `https://console.tianlu2026.org` 的实时数据，不再显示备份文件路径。
