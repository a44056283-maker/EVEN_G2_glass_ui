# 20260502_1558 Voice Adaptive Capture Patch Report

## 本轮范围

只处理呼叫天禄语音入口的采集方式与意图路由：

- 手机/网页端：`按住语音对话`，松开后处理语音文字。
- 眼镜/R1端：进入呼叫天禄后优先启动 G2 麦克风 WebSocket ASR 链路。
- 语义命中“看一下 / 看一看 / 瞅一瞅 / 这是什么”等视觉意图时，自动进入视觉拍照识别流程。

本轮未修改交易接口、OpenCLAW 配置和视觉上传接口。

## 修改文件

- `apps/evenhub-plugin/index.html`
  - `语音对话` 按钮改为 `按住语音对话`。
  - 语音采集最长时间配置上限从 10 秒提升到 120 秒。

- `apps/evenhub-plugin/src/config.ts`
  - `g2RecordMs` 最大值提升到 `120000ms`。

- `apps/evenhub-plugin/src/speech.ts`
  - `listenOnce` 增加 `maxMs`、`AbortSignal`、中间文本回调。
  - 支持按住录音时松开停止。

- `apps/evenhub-plugin/src/glass/glassMicProbe.ts`
  - 增加 `mode: probe | asr | mock-asr`。
  - 眼镜语音入口可连接 `/audio?mode=asr`。

- `apps/evenhub-plugin/src/main.ts`
  - 手机端 `voice-record-action` 改为 pointer 按住采集。
  - 无 G2 Bridge 时提示使用手机/耳机麦克风。
  - 有 G2 Bridge 时优先走 G2 麦克风 `/audio?mode=asr`。
  - ASR transcript 命中视觉意图时自动调用视觉识别流程。
  - 视觉意图词扩展：`看一看`、`瞅一瞅`、`瞅一下`、`瞅瞅`、`瞧一瞧`、`帮我瞅`、`帮我瞧`。

## 验证

- `npm run typecheck`：通过。
- `npm run build`：通过。
- `npm run pack:g2`：通过。

## EHPK

- `apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- `apps/evenhub-plugin/g2-视觉-语音助手.ehpk`

SHA256:

`78a309ffb9429d399ffc2a90a1114fa3c4cdee3507977723d87eec73dcd06f59`

## 仍需真机验证

1. 手机网页按住 `按住语音对话` 是否能弹出/使用手机或耳机麦克风。
2. Even App 内 R1 进入呼叫天禄后，G2 麦克风是否能通过 `/audio?mode=asr` 返回 transcript。
3. 如果真实 ASR endpoint 未配置，眼镜端仍会收到 ASR 配置错误；这不是采集入口问题，需要后续 R0-003b 接真实 ASR。
4. 语音命中“帮我看一下这是什么”后，是否能按当前运行环境打开视觉拍照流程。

## 下一步

- R0-003b：确认 ASR provider 配置。当前后端已有 `/audio?mode=asr`，但是否能出文字取决于真实 ASR endpoint。
- R0-003c：把语音视觉意图的拍照流程做成“手机端拍照后自动上传，眼镜端显示结果”的专项验收。
