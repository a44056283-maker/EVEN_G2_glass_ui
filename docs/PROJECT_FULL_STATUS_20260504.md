# 天禄 G2 运维助手 - 完整项目状态报告

生成日期：2026-05-04

## 一、项目概述

**项目名称**：天禄 G2 运维助手
**Plugin ID**：com.luxiangnan.g2visionvoice
**当前版本**：v0.5.0
**整体完成度**：约 45%

## 二、目录结构

```
g2-vision-voice-assistant/
├── apps/
│   └── evenhub-plugin/           # Even Hub 插件前端
│       ├── src/
│       │   ├── main.ts          # 主入口
│       │   ├── index.html       # HTML 入口
│       │   ├── style.css        # 样式
│       │   ├── glass/           # 眼镜端 UI 渲染
│       │   │   ├── GlassRenderer.ts
│       │   │   ├── glassScreens.ts    # 眼镜屏幕模板
│       │   │   ├── glassNavigation.ts # 眼镜导航配置
│       │   │   ├── glassText.ts
│       │   │   ├── glassLayout.ts
│       │   │   ├── glassTheme.ts
│       │   │   ├── glassMicProbe.ts
│       │   │   └── glassInputDebug.ts
│       │   ├── ui/              # 手机网页 UI
│       │   │   ├── phoneUiState.ts   # 手机书签状态
│       │   │   ├── phoneNavigation.ts # 手机导航配置
│       │   │   └── phonePageRegistry.ts
│       │   ├── voice/           # 语音链路
│       │   │   ├── g2MicProbe.ts
│       │   │   ├── g2MicStream.ts
│       │   │   └── g2PcmVoiceSession.ts
│       │   ├── camera/          # 相机控制
│       │   │   ├── cameraStream.ts
│       │   │   └── visionEngine.ts
│       │   ├── api/             # API 适配
│       │   │   └── g2BridgeApi.ts
│       │   ├── device/          # 设备相关
│       │   │   ├── batteryCache.ts
│       │   │   └── extractBatterySnapshot.ts
│       │   ├── input/           # 输入处理
│       │   │   └── normalizeEvenInputEvent.ts
│       │   ├── history.ts       # 历史记录
│       │   ├── speech.ts        # 语音合成/识别
│       │   ├── camera.ts        # 相机控制
│       │   ├── bridge.ts        # Even Hub 桥接
│       │   ├── config.ts        # 配置管理
│       │   ├── display.ts       # 显示管理
│       │   ├── events.ts        # 事件处理
│       │   ├── g2-mic.ts       # G2 麦克风
│       │   └── api.ts          # API 接口
│       ├── dist/                # 构建输出
│       └── app.json            # 插件配置
├── services/
│   └── api-server/             # G2 Bridge 后端
├── docs/                       # 项目文档
├── data/                       # 数据目录
├── scripts/                    # 脚本
└── store-assets/               # 商店素材

```

## 三、已实现功能

### 1. 视觉识别
- 手机拍照/相册选图
- /vision 后端识别
- 结果显示与朗读
- 历史记录（当前版本有缺陷）

### 2. 语音问答（呼叫天禄）
- G2 眼镜麦克风采集
- WebSocket /audio 链路
- ASR 语音转文字（Mock 模式）
- TTS 语音合成（female-shaonv 萝莉音）
- OpenCLAW / ask 问答（存在缺陷）

### 3. 交易状态
- /trading/overview 接口
- 六大分类：运行状态/白名单价格/持仓盈亏/资金分布/订单归因/风控告警
- 眼镜戒指上下切换分类
- AI 评测朗读

### 4. 系统设置
- 设备诊断入口
- 连接扫描
- 权限自检
- TTS 试听

### 5. G2 眼镜端 UI
- GlassRenderer 单容器 HUD
- 眼镜首页 4 菜单：视觉识别/呼叫天禄/交易状态/系统设置
- R1 戒指导航：上下切换/单击执行
- 多页面状态显示

## 四、待修复缺陷

### 1. OpenCLAW 对接缺陷（严重）
**问题**：/ask 接口与 OpenCLAW 的对接不完整，存在以下问题：
- OpenCLAW 网关稳定性未确认
- timeout fallback 未完整实现
- 真实 OpenCLAW 问答可能失败

### 2. 历史记录缺陷（严重）
**问题**：当前版本无法保存任何历史记录
- vision 历史记录未持久化
- voice 历史记录未持久化
- 追问功能无法获取历史上下文

### 3. 眼镜首页显示问题
**问题**：首页可能显示不正确
- 4 菜单模板已实现但未真机验证
- R1 焦点与视觉显示可能不一致

## 五、阶段进度

| 阶段 | 内容 | 完成度 |
|------|------|--------|
| 0 | 工程审计与协作基线 | 100% |
| 1 | 手机网页主版块与二级版块 | 65% |
| 2 | 网页视觉识别闭环 | 50% |
| 3 | G2 眼镜端 Glass UI 稳定验收 | 45% |
| 4 | R1 / G2 输入调试 | 代码已有，待真机 |
| 5 | R1 控制相机 | 未完成 |
| 6 | G2 Mic Probe | 代码已有，待真机 |
| 7 | ASR 语音转文字 | 未完成 |
| 8 | 天禄问答 / OpenCLAW / 交易只读 | 30% |
| 9 | 视觉增强 | 未开始 |
| 10 | 设备诊断与 Runbook | 未完成 |
| 11 | 自动化测试与打包发布 | 部分完成 |

## 六、技术架构

### 前端技术栈
- TypeScript + Vite
- Even Hub SDK（GlassRenderer / glassScreens）
- WebSocket 实时通信
- Web Audio API（G2 麦克风）

### 后端接口
```
POST /vision          # 视觉识别
WS /audio?mode=       # 语音采集（probe/mock-asr/asr）
POST /ask             # 天禄问答 / OpenCLAW
POST /tts             # 语音合成
GET /trading/overview # 交易状态
GET /memory/search    # 记忆搜索
GET /openclaw/status  # OpenCLAW 状态
```

### 网络白名单
- https://g2-vision.tianlu2026.org

## 七、今日任务（2026-05-04）

### P0 紧急
1. 修复 OpenCLAW 真实对接
2. 修复历史记录持久化

### P1 重要
3. 验证眼镜首页 4 菜单显示
4. 验证 R1 导航功能

### P2 一般
5. 完善交易六大分类显示
6. 完善 TTS 试听功能

## 八、EHPK 包信息

- **版本**：v0.5.0
- **大小**：~79KB（evenhub pack）
- **SHA256**：待生成
- **路径**：/Users/luxiangnan/Desktop/EVEN_Hub开发者中心上传包_v0.5.0_upload/

## 九、已知问题汇总

1. OpenCLAW 未真正对接 → 需要修复
2. 历史记录不保存 → 需要修复
3. 眼镜首页可能显示不正确 → 需要真机验证
4. R1 相机控制流程不完整 → 待实现
5. 真实 ASR 未接入 → 待实现
