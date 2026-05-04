# R0-003 呼叫天禄语音模块测试报告

时间：2026-05-02 16:53

## 本轮范围

本轮执行 `R0-003：呼叫天禄语音模块完整修复`，重点修复：

1. 呼叫天禄独立子菜单：语音对话 / 手动发送 / 语音诊断。
2. 手机端按住说话入口：按下开始、松开结束、最长 120 秒。
3. G2/R1 等价入口：单触开始录音，再单触结束录音。
4. G2 原生麦克风主链路：`audioControl(true)` + `audioEvent.audioPcm` + WebSocket `/audio`。
5. `/audio` 支持 `end_of_speech`，`mock-asr` 只在收到 PCM 后返回 `final_transcript`。
6. `final_transcript -> handleTranscript -> routeVoiceIntent`。
7. 视觉意图、交易意图、普通问答的分流。

本轮没有改动 R1 视觉相机状态机、OpenCLAW 主逻辑、交易真实接口和视觉识别相机启动逻辑。

## 关键实现

### 前端

- 新增 `apps/evenhub-plugin/src/voice/g2PcmVoiceSession.ts`
  - 建立 `/audio?mode=probe|mock-asr|asr&source=g2` WebSocket。
  - 先注册 `bridge.onEvenHubEvent`，再调用 `bridge.audioControl(true)`。
  - 读取 `event.audioEvent?.audioPcm`，转成 `Uint8Array` 后二进制发送。
  - 支持 `stop(reason)` 发送 `end_of_speech`。
  - 支持 120 秒录音上限和 5 秒无 PCM 诊断。

- 修改 `apps/evenhub-plugin/src/main.ts`
  - `呼叫天禄` 子菜单改为：语音对话 / 手动发送 / 语音诊断。
  - `语音对话` 进入 `startHoldToTalkSession({ mode: 'mock-asr' })`。
  - R1 在语音页：单触开始、再单触结束；双击/下滑取消返回。
  - `final_transcript` 进入 `handleTranscript()`，再走 `routeVoiceIntent()`。
  - 交易意图优先于视觉意图，避免“帮我看一下交易机器人运行如何”被误判为看图。
  - 手动发送也走同一套 `handleTranscript -> routeVoiceIntent`。

- 修改 `apps/evenhub-plugin/src/glass/glassScreens.ts`
  - 增加语音菜单、录音中、结束识别、视觉切换、回复、错误等 G2 页面文案。

- 修改 `apps/evenhub-plugin/index.html`
  - 增加 `语音诊断` 按钮。

- 修改 `apps/evenhub-plugin/src/config.ts`
  - 默认录音上限改为 120000ms。

### 后端

- 修改 `services/api-server/src/server.ts`
  - `/audio` 支持 `end_of_speech` 控制消息。
  - `mode=probe` 仅返回 `audio_debug`，不调用 ASR。
  - `mode=mock-asr` 必须收到 PCM 数据，且满足 `bytes >= 16000` 或 `chunks >= 5` 后才返回 `final_transcript`。
  - `mockText` 可从 query 参数覆盖。
  - 不再在 `/audio` 内直接调用问答，避免跳过前端 `handleTranscript`。

## 意图路由

### 视觉意图

关键词包括：看一看、看一下、帮我看看、这是什么、识别一下、读一下、屏幕内容、菜单、图片内容、前面是什么。

处理规则：

- 有最近视觉结果时，直接基于最近结果回答。
- 没有最近视觉结果时，尝试复用现有视觉识别流程。
- 不新写相机逻辑，不强行打开 file input。

### 交易意图

关键词包括：交易机器人、机器人运行、运行如何、状态如何、今天收益、收益、PnL、风险、持仓、挂单、交易状态、白名单、价格。

处理规则：

- 交易意图优先于视觉意图。
- 调用现有只读问答/交易状态链路。
- 不执行下单、平仓、改杠杆、改策略等真实交易动作。

## 验证结果

### 命令验证

```text
npm run typecheck
结果：通过

npm run build
结果：通过

npm run pack:g2
结果：通过
```

### EHPK

路径：

```text
apps/evenhub-plugin/g2-vision-voice-assistant.ehpk
```

大小：

```text
69239 bytes
```

SHA256：

```text
ce18e373354684cb19b2263bc2bd1b3cc1eecbb3376e1d02e8d826355181c4dd
```

## 尚未完成 / 需要真机验证

1. 本地无法替代 Even G2 真机验证 `audioEvent.audioPcm` 是否持续增长。
2. 真实 ASR 仍未接入，本轮只保证 `mock-asr` 闭环条件和路由结构。
3. 如果真机 `totalBytes/chunks` 不增长，下一步必须继续查：
   - `audioControl(true)` 是否成功；
   - `g2-microphone` 权限是否被 Even App 正确授予；
   - 真机事件里是否实际发送 `audioEvent.audioPcm`；
   - 当前安装包是否为最新 EHPK。

## 下一步建议

1. 真机安装本包，进入“呼叫天禄 -> 语音对话”。
2. R1 单触开始，观察 Voice Debug：
   - `audioControlCalled=true`
   - `wsStatus=open`
   - `totalBytes/chunks` 是否增长
3. 如果 PCM 增长，进入 `R0-003b：真实 ASR 接入`。
4. 如果 PCM 不增长，继续做 `G2 audioEvent` 真机日志专项。
