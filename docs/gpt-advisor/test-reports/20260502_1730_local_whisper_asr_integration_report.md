# 20260502_1730 本地 Whisper ASR 接入报告

## 本轮目标

解决“呼叫天禄”语音模块仍返回预置 mock 文本、无法把真实录音转成文字的问题。

本轮不改视觉识别、R1 相机控制、OpenCLAW、交易机器人接口和 Glass UI。

## 结论

本地 Whisper ASR 已接入并跑通：

- 本地 ASR 服务：`http://127.0.0.1:8791`
- 后端 ASR 状态：`ASR_PROVIDER=http`
- 后端 `/transcribe` 已能调用本地 Whisper 并返回真实转写文本
- 本地 ASR 已通过 macOS `launchd` 托管，支持开机/登录后自动保持运行

## 新增/修改文件

- `services/local-whisper-asr/server.py`
- `services/local-whisper-asr/requirements.txt`
- `scripts/start-local-whisper-asr.sh`
- `scripts/stop-local-whisper-asr.sh`
- `.env`：ASR provider 改为 HTTP 本地 ASR
- `~/Library/LaunchAgents/com.tianlu.g2.local-whisper-asr.plist`

## 当前 ASR 配置

```text
ASR_PROVIDER=http
ASR_HTTP_URL=http://127.0.0.1:8791/transcribe
ASR_HTTP_API_KEY=
```

MiniMax 文本生成 API 与 ASR 不等价。当前 MiniMax 仍用于文本理解、视觉和 TTS；语音转文字使用本地 Whisper。

## 服务状态

本地 Whisper：

```json
{
  "ok": true,
  "provider": "local-whisper:base",
  "device": "cpu",
  "computeType": "int8"
}
```

后端 ASR：

```json
{
  "available": true,
  "provider": "http",
  "message": "HTTP ASR 已配置。"
}
```

## 转写测试

测试音频：

```text
你好天禄 帮我看一下交易机器人运行如何
```

直接调用本地 ASR 成功，后端 `/transcribe` 调用本地 ASR 也成功：

```json
{
  "provider": "http-asr",
  "text": "你好天路,帮我看一下交易机器人运行如何。"
}
```

“天禄”被识别成“天路”属于 ASR 同音字问题，前端/后端意图路由应继续把“天禄、天路、天鹿”都作为唤醒词处理。

## MiniMax API 测试说明

用户提供的 `sk-api...` key 测试结果：

- `https://api.minimax.io/v1/chat/completions` 返回 `invalid api key (2049)`
- `https://api.minimaxi.com/v1/chat/completions` 返回 `insufficient balance (1008)`

该 key 当前不能作为本项目可用 ASR 接口。且 MiniMax M2.7 文本生成能力不能直接替代 ASR。

## 验证命令

```bash
curl -s http://127.0.0.1:8791/health
curl -s http://127.0.0.1:8787/asr/status
curl -s -X POST http://127.0.0.1:8787/transcribe \
  -H 'Content-Type: text/plain;charset=UTF-8' \
  --data-binary @/tmp/g2-asr-payload.json
```

## 构建结果

```text
npm run typecheck 通过
npm run build     通过
npm run pack:g2   通过
```

EHPK：

```text
apps/evenhub-plugin/g2-vision-voice-assistant.ehpk
```

SHA256：

```text
108b75e71b26188f8154fdb1305e5c9451a049db8ce58e7685ed143fe54cb7a3
```

## 仍未解决

1. Even App / G2 真机是否能采集到音频并上传，还需要真机测试。
2. 如果手机端 `getUserMedia({ audio:true })` 被 Even WebView 拒绝，则手机/耳机录音仍不可用，但 ASR 服务已经可用。
3. 如果 G2 `audioEvent.audioPcm` 没有 bytes 增长，则要继续查 `audioControl(true)` 与 Even 真机事件。

## 下一步

1. 真机打开“呼叫天禄”。
2. 手机端按住说话，测试是否能录音上传。
3. G2 端用 R1 进入语音页，测试 G2 PCM 是否增长。
4. 若录音能上传但文字不准，再升级 Whisper 模型为 `small` 或加入唤醒词纠错。
