# R0-003 呼叫天禄语音模块完整修复任务

时间：2026-05-02 16:38

## 本轮目标

只修复“呼叫天禄”语音模块链路：

1. 呼叫天禄作为独立模块，子菜单只显示：语音对话、手动发送、语音诊断。
2. 手机网页语音对话支持按住说话，松开结束，最长 120 秒。
3. G2/R1 端使用单触开始、再单触结束，最长 120 秒。
4. G2 主链路使用官方方式：`audioControl(true)` + `audioEvent.audioPcm`。
5. PCM 通过 WebSocket 发送到 `/audio`，支持 `probe`、`mock-asr`、`asr`。
6. `mock-asr` 必须收到真实 PCM 后才返回 `final_transcript`。
7. `final_transcript` 必须进入 `handleTranscript`，再由 `routeVoiceIntent` 分发。
8. 支持视觉意图和交易意图：
   - “看一看 / 看一下 / 这是什么 / 识别一下”等进入视觉意图。
   - “交易机器人 / 今天收益 / 持仓 / 风险”等进入交易只读意图。

## 本轮禁止事项

1. 不修改 R1 视觉相机控制状态机。
2. 不修改网页视觉识别闭环。
3. 不修改 OpenCLAW Gateway 主逻辑。
4. 不修改交易机器人真实交易接口。
5. 不修改 MiniMax VLM。
6. 不做手机网页 UI 大美化。
7. 不做整体 Glass UI 大重构。
8. 不修改视觉识别相机启动逻辑。
9. 不修改 R1 单触拍照 / 上传识别流程。
10. 不把 `SpeechRecognition` 作为主语音路径。
11. 不跳过 PCM 探针假装识别成功。
12. 不让真实 ASR 未配置伪装成成功。

## 官方 G2 麦克风调用方式

主链路必须是：

```text
waitForEvenAppBridge()
→ bridge.onEvenHubEvent(event => event.audioEvent?.audioPcm)
→ bridge.audioControl(true)
→ WebSocket binary /audio
→ final_transcript
→ handleTranscript
→ routeVoiceIntent
```

音频格式：

- PCM 16kHz
- signed 16-bit little-endian
- mono

## 按住说话交互

手机网页：

- 按下：开始录音并立即反馈。
- 松开：结束录音并发送 `end_of_speech`。
- 最长 120 秒，到时自动结束。

G2/R1：

- 单触：开始录音。
- 再单触：结束录音。
- 最长 120 秒，到时自动结束。

## 真实 ASR 未配置时

`mode=asr` 必须返回明确错误，不得假装成功。

`mode=mock-asr` 可用于闭环测试，但必须收到真实 PCM 后才返回固定文字。

## 验收标准

1. 呼叫天禄子菜单不再显示视觉识别按钮。
2. 手机端按住说话有录音计时和释放结束。
3. G2/R1 可单触开始、再单触结束。
4. G2 PCM bytes/chunks 可被统计并发给 `/audio`。
5. `/audio?mode=mock-asr` 收到 PCM 后返回 `final_transcript`。
6. `final_transcript` 进入 `handleTranscript`。
7. 视觉意图进入现有视觉流程或最近视觉结果回答。
8. 交易意图进入交易只读 fallback。
9. 手动发送可用。

