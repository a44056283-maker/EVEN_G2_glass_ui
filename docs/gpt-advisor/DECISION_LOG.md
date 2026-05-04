# 决策记录

更新时间：2026-05-02

## D-001：GPT Advisor Folder 固定位置

决策：

```text
docs/gpt-advisor/
```

原因：

- 所有 GPT 建议、Codex 提示词、审计、交接和测试结果集中管理。
- 避免聊天记录丢失或上下文压缩后找不到依据。

## D-002：手机网页 UI 与 G2 眼镜端 UI 分离

决策：

- Phone Web UI 用于手机端调试、设置、日志和预览。
- Glass UI 用于 G2 眼镜端 576 x 288 显示。

原因：

- G2 眼镜端不是 HTML/CSS。
- 眼镜端必须通过 Even Hub SDK container 渲染。

## D-003：G2 端优先单 TextContainer

决策：

- 当前阶段优先使用单个全屏 `TextContainerProperty`。

原因：

- 真机稳定性优先。
- 多容器容易重叠、空白、事件捕获异常。

## D-004：语音主链路使用 G2 PCM

决策：

```text
bridge.audioControl(true)
-> audioEvent.audioPcm
-> WebSocket
-> 后端 ASR
```

原因：

- 浏览器麦克风权限不是 G2 麦克风主链路。
- `SpeechRecognition` 只能做实验兜底。

## D-005：交易功能第一版只读

决策：

- 只查看价格、状态、持仓、盈亏、风险、错误。
- 不下单、不平仓、不改杠杆、不改策略。

原因：

- 安全优先。
- 眼镜端误触风险高。

