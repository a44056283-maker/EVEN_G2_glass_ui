# 20260502_2146 呼叫天禄回答质量与面板稳定性修复报告

## 本轮范围

只修复呼叫天禄模块中两个高频问题：

1. 普通问答返回“我已收到问题，会显示在这里”这类占位式假回答。
2. 语音状态更新时网页面板容易飘回首页/当前焦点菜单，导致呼叫天禄页面不稳定。

未修改：

- R1 视觉相机状态机
- 交易写接口
- OpenCLAW 网关配置
- 真实 ASR 接入方式
- 交易机器人真实接口

## 修改文件

- `services/api-server/src/server.ts`
- `apps/evenhub-plugin/src/main.ts`
- `apps/evenhub-plugin/src/style.css`

## 修复内容

### 1. 后端问答占位回答拦截

`/ask` 现在在 MiniMax 首次回答被判定为无效占位时，会进行一次严格二次追问：

- 禁止回复“收到问题”
- 禁止回复“稍后显示”
- 禁止回复“发到 Telegram/手机/第三方平台”
- 要求直接回答当前问题

如果二次追问仍无效，则返回本地 fallback：

- 附近/地点/美食/景点类问题：提示当前没有定位，并要求用户补充城市、街区或位置。
- 其他普通问题：提示补充对象或目标，而不是假装已经处理。

### 2. 呼叫天禄页面不再被状态更新带回首页

`setVoiceStatus()` 更新语音状态时，如果当前处于 `activeGlassPage === 'voice'`，会强制保持网页 active bookmark 为 `voice`。

目的：

- 防止语音回答、录音状态、朗读状态更新时，网页区域飘回首页或其他书签。
- 保持呼叫天禄问答结果仍显示在呼叫天禄模块里。

### 3. Voice Debug 默认强制隐藏

新增 CSS：

```css
#app:not([data-show-voice-debug="true"]) .voice-debug-panel {
  display: none !important;
}
```

目的：

- 语音调试信息不再挤在用户回答下面。
- 后续如需要调试，可显式设置 `data-show-voice-debug="true"` 再显示。

## 本地验证

### typecheck

通过：

```bash
npm run typecheck
```

### build

通过：

```bash
npm run build
```

### pack

通过：

```bash
npm run pack:g2
```

输出：

```text
apps/evenhub-plugin/g2-vision-voice-assistant.ehpk
73438 bytes
SHA256: 5c79bc5fc0a3b527563d9e45ff7f6cbc3c4d2afaee43a33d4280572c92e5b284
```

### /ask 普通问题测试

测试问题：

```text
你好天禄，你知道附近有什么好玩的地方好吃的地方吗
```

返回结果：

```text
你好！我不知道你在哪里，无法推荐附近的地点。
请告诉我你所在的城市或具体位置，我再帮你找好吃好玩的地方。
```

结论：不再返回“收到问题，会显示在这里”。

## 未解决问题

1. 真机仍需验证呼叫天禄语音回答区域是否还会飘回首页。
2. 真实 ASR 仍需继续稳定化，尤其是手机/耳机和 G2 原生麦克风不同环境的最终链路。
3. R1 电量若仍显示 `--`，需要抓取 `[G2 device status]` 原始事件确认 Even App 是否上报 R1 电量字段。

## 下一步建议

1. 安装本次 EHPK，优先测试普通问答是否能直接回答。
2. 测试语音回答后网页是否仍停留在呼叫天禄区域。
3. 继续修：真实 ASR 返回空文字、视觉意图自动触发、R1 电量原始字段确认。
