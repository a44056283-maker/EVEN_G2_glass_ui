# 20260502_1624 手机/耳机麦克风真实录音补丁报告

## 本轮范围

只修复“呼叫天禄”里手机/耳机麦克风采集一直报 `SpeechRecognition not-allowed` 的问题。

## 核心结论

旧逻辑使用 `window.SpeechRecognition / webkitSpeechRecognition` 做语音识别，Even App WebView / iOS 容器容易直接返回 `not-allowed`。这不是可靠的麦克风录音链路。

本轮已把手机/耳机兜底改为：

1. 按住“按住语音对话”
2. 使用 `navigator.mediaDevices.getUserMedia({ audio })`
3. 用 `MediaRecorder` 真实录音
4. 松开后上传 `/transcribe`
5. 有 ASR 返回文字则交给天禄处理
6. ASR 未配置或不支持格式时，明确显示“已采集音频，但暂时不能转文字”

## 修改文件

- `apps/evenhub-plugin/src/voice/phoneMicRecorder.ts`
- `apps/evenhub-plugin/src/main.ts`
- `apps/evenhub-plugin/src/api.ts`
- `packages/shared/src/index.ts`
- `packages/asr-adapter/src/index.ts`

## 关键变化

- 新增 `phoneMicRecorder.ts`，使用 MediaRecorder 采集真实音频，不再用 Web Speech 作为手机/耳机主路径。
- `main.ts` 中按住语音按钮改为“按住录音、松开上传转文字”。
- `/transcribe` 请求增加 `mimeType / durationMs / source` 字段。
- ASR adapter 增加 `mock` 和 `http` 转写入口。
- MiniMax ASR 对非 PCM 音频明确返回 unsupported-format，避免把 webm/mp4 错当 PCM。

## 当前限制

如果 Even App WebView 仍拒绝 `getUserMedia({ audio })`，界面会继续显示麦克风权限被容器拒绝。这代表当前容器不允许手机/耳机麦克风录音，需要：

1. 在 Safari 直接打开 `https://g2-vision.tianlu2026.org` 测试手机麦克风；
2. 或继续走 G2 麦克风 `audioControl(true) -> audioEvent.audioPcm`；
3. 或配置一个真实 ASR HTTP 服务后再完整闭环。

## 验证结果

- `npm run typecheck`：通过
- `npm run build`：通过
- `npm run pack:g2`：通过

## EHPK

- `apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- `apps/evenhub-plugin/g2-视觉-语音助手.ehpk`

SHA256:

`7d574e4f842bb970fd3c6df94193ff0a8c1185d0b0eaec5b80668a170f43f8c2`

## 下一步

如果真机按住语音后能看到“已录音：xx KB”，下一步接真实 ASR。

如果仍然 `not-allowed`，说明 Even App 当前容器拒绝手机/耳机麦克风，下一步应专注 G2 麦克风 PCM 采集链路，而不是继续修 SpeechRecognition。
