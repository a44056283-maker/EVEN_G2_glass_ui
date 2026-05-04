# 语音模块去除默认 mock-asr 报告

时间：2026-05-02 17:09

## 用户反馈

用户反馈“呼叫天禄”仍不能正常采集并转换成文字，页面看到的是预置的“看一下交易状况”内容。

## 根因

当前前端默认启动语音时仍使用：

```text
mode=mock-asr
```

因此后端 `/audio?mode=mock-asr` 在收到足够 PCM 后会返回预置文本：

```text
你好天禄，帮我看一下交易机器人运行如何
```

这不是用户真实录音转文字。

同时当前 `.env` 中：

```text
ASR_PROVIDER=minimax
MINIMAX_ASR_ENDPOINT=
```

也就是说后端真实 ASR 端点未配置。录音可以采集，但不能真正转文字。

## 本轮修复

1. 前端默认语音模式从 `mock-asr` 改为 `asr`。
2. 手机网页“按住语音对话”强制走 `phone-media-recorder`，不再因为存在 G2 bridge 就默认抢走到 G2 PCM。
3. R1 / G2 语音仍优先走 `g2-pcm`。
4. 如果 ASR 未配置，前端会显示真实错误，不再显示预置假文字。

## 修改文件

- `apps/evenhub-plugin/src/main.ts`

## 当前真实状态

语音录音采集链路：

```text
手机网页按住说话 -> 手机/耳机 MediaRecorder -> /transcribe
R1/G2 单触说话 -> G2 audioEvent.audioPcm -> /audio?mode=asr
```

转文字链路：

```text
ASR_PROVIDER=minimax 但 MINIMAX_ASR_ENDPOINT 为空
```

所以目前如果没有额外配置真实 ASR，软件会正确显示“录音已收到但 ASR 未配置/无法转文字”，不会再返回 mock 预置文本。

## 验证

```text
npm run typecheck  通过
npm run build      通过
npm run pack:g2    通过
```

EHPK：

```text
apps/evenhub-plugin/g2-vision-voice-assistant.ehpk
```

SHA256：

```text
108b75e71b26188f8154fdb1305e5c9451a049db8ce58e7685ed143fe54cb7a3
```

## 下一步

必须接入一个真实 ASR：

1. `ASR_PROVIDER=http` + `ASR_HTTP_URL=真实语音转文字接口`
2. 或 `ASR_PROVIDER=minimax` + `MINIMAX_ASR_ENDPOINT=MiniMax 真实可用 ASR 端点`
3. 或增加本地 Whisper ASR 服务

在真实 ASR 接入前，软件只能做到录音采集与错误诊断，不能凭空把音频转成文字。
