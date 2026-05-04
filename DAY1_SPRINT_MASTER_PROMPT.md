# Day1 Sprint Master Prompt

## 日期：2026-05-05

## 目标

完成天禄 G2 运维助手 Day1 冲刺任务。

## 任务清单

### 1. 首页 4 菜单一行显示

```
[视觉识别○][呼叫天禄○][交易状态○][系统设置●]
```

要求：
- 4 个菜单横向排列在一行
- 每个菜单等宽
- 系统设置必须可见可进入

### 2. R1 焦点隔离

- R1 ring navigation 只在 4 个可见菜单之间切换
- 不能选到隐藏项
- 添加 activeGlassSessionId 保护

### 3. 取消流程修复

手机取消拍照/选图/对话后：
- 重置 pendingCapturedImage
- 清除 preparing/uploading 状态
- G2 能正常返回

### 4. 语音意图触发视觉

识别以下关键词：
- "看一看"
- "这是什么"
- "帮我看看"
- "看一下前面"

处理方式：
- 优先复用 lastVisionResult
- 无结果时触发拍照流程

### 5. 交易状态标签分类

手机端：
- 运行概览
- 白名单价格
- 持仓/挂单
- 风险告警
- 最近日志

眼镜端：
- trading_status
- trading_prices
- trading_positions
- trading_distribution
- trading_attribution
- trading_alerts

### 6. R1 单触交互修复

- 子菜单单触进入当前标签
- 标签详情页单触刷新
- 上下滑切换交易标签
- 下滑返回上级或首页

### 7. 去除 G2 横线和框线

- 检查所有 border 属性
- 移除所有 hr 元素
- 保持居中 HUD 风格

## 执行流程

1. 读取相关源文件
2. 按任务清单逐项修改
3. typecheck / build / pack:g2
4. 生成测试报告
5. git commit / push

## 禁止事项

- 不改 R1 视觉相机状态机
- 不新增交易写操作
- 不重构整个 UI
- 不改 SpeechRecognition 主路径