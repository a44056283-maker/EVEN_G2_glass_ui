# 真实数据对接审计记录 2026-05-01

## 结论

当前版本已禁用会误导测试结果的 mock / stub 返回：

- G2 麦克风 ASR 不再回退到固定模拟文字。
- 交易机器人状态不再回退到 mock-momentum、模拟持仓和模拟 PnL。
- 视觉识别不再回退到 stub 描述。
- 网页和 G2 HUD 顶栏时间不再使用固定时间。
- 交易状态默认页不再显示假心跳、假持仓、假 PnL。

## 真实对接状态

| 功能 | 当前状态 | 说明 |
| --- | --- | --- |
| MiniMax 视觉识别 | 已真实接入 | `VISION_PROVIDER=minimax-vlm`，6 轮均返回 `vision:minimax-vlm+llm` |
| MiniMax TTS | 已真实接入 | 6 轮均返回 `provider=minimax` 和音频数据 |
| 交易只读概览 | 已真实接入 | `TRADING_READONLY_ENABLED=true`，数据来自 `https://console.tianlu2026.org` |
| 天禄问答 | 已真实接入 | 可结合交易只读实时数据与 MiniMax 生成回答 |
| OpenCLAW 状态 | 健康检查可用 | `/health` 正常，显示 gateway=true |
| OpenCLAW 问答 | 未真实打通 | `/v1/chat/completions` 返回 Gateway timeout，插件侧显示 unavailable |
| G2 麦克风 PCM | 前端链路保留 | 真机可收到 PCM，但后端 ASR 未配置真实端点 |
| ASR 语音转文字 | 未真实接入 | `ASR_PROVIDER=minimax` 但 `MINIMAX_ASR_ENDPOINT` 为空 |

## 6 轮轮测结果

测试命令：

```bash
G2_TEST_BASE_URL=https://g2-vision.tianlu2026.org npm run test:real -- 6
```

总结果：

- 通过：36
- 失败：12

失败项：

- `asr-status`：6/6 失败，原因是 MiniMax ASR 端点未配置。
- `openclaw-ask`：6/6 失败，原因是 OpenCLAW Gateway 对话链路超时，后端返回 `openclaw:unavailable`。

通过项：

- `health`：6/6
- `trading-overview`：6/6
- `openclaw-status`：6/6
- `ask-trading`：6/6
- `vision`：6/6
- `tts`：6/6

## OpenCLAW 直接探测

`https://even2026.tianlu2026.org/health` 返回正常。

`/v1/chat/completions` 返回 200，但内容为：

```text
Gateway 暫時無法連線：The operation was aborted due to timeout
```

所以问题不是插件 UI，也不是 G2 Bridge 请求格式，而是 OpenCLAW 网关后面的 agent / relay 当前没有完成有效回答。

## 下一步必须补齐

1. 配置真实 ASR：
   - `ASR_PROVIDER=http`
   - `ASR_HTTP_URL=真实语音转文字服务地址`
   - 或者补齐 MiniMax 可用的 `MINIMAX_ASR_ENDPOINT`

2. 修复 OpenCLAW 后端：
   - 确认 `https://even2026.tianlu2026.org/v1/chat/completions` 能返回真实 agent 回答。
   - 当前 token / endpoint 格式可以到达网关，但网关内层超时。

3. 真机硬件测试仍需人工完成：
   - R1 单击 / 双击 / 下滑事件
   - 手机摄像头真实拍照
   - G2 镜片显示
   - 手机或蓝牙耳机朗读
