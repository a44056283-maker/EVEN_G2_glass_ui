# G2 Glass UI 设计基线

## 目标风格

眼镜端采用 `TL OS` 风格：

- 低功耗
- 单色绿色层级
- 运维仪表盘
- 短行文本
- 状态清晰
- R1 操作提示固定

## 约束

- 画布：576 x 288 px
- 眼镜端不是 HTML/CSS
- 不支持 flex/grid/DOM layout
- TextContainer 无字体大小、粗体、居中控制
- 真机优先稳定，复杂多容器必须逐步验证

## 初版策略

当前优先使用单个全屏 `TextContainerProperty`，避免多容器真机空白或不稳定。

允许使用：

- `TL-OPS` / `TL-VISION` / `TL-VOICE` / `TL-SYS`
- `◆ ◇ ● ○ >`
- `━━━━━━━━`
- `▰▰▱▱`
- 短边框字符

避免使用：

- 大量空格居中
- 复杂多行卡片
- 一屏 10 行以上
- 长中文句子
- 未经真机验证的多容器布局

## 页面初版

### Home

```text
TL OS        22:35
天禄 G2 运维助手
━━━━━━━━━━━━━━━
◆ 视觉扫描  CAM
◇ 天禄问答  MIC
◇ 交易状态  BOT
◇ 设备诊断  SYS
━━━━━━━━━━━━━━━
G2 ONLINE  CLAW READY
R1上下切换  单击进入
```

### Vision Ready

```text
TL-VISION    READY
━━━━━━━━━━━━━━━
相机已就绪

     R1 单击拍照

双击返回
下滑返回首页
```

### Voice Mic Probe

```text
TL-VOICE     MIC
━━━━━━━━━━━━━━━
天禄正在监听

PCM: 128000 bytes
Chunks: 40
ASR: WAITING

说：你好天禄
```

### Trading

```text
TL-OPS       BOT
━━━━━━━━━━━━━━━
状态：运行正常
心跳：8 秒前
策略：mock-momentum
持仓：2   挂单：1
PnL：+1.2%
风险：正常
R1 单击刷新
```

## 验收

- 真机不空白。
- 不重叠。
- 文字可读。
- R1 操作提示明确。
- 后续再逐步验证多容器 HUD。
