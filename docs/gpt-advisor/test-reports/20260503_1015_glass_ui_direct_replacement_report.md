# 眼镜端 UI 直接替换报告

## 基本信息

- **任务编号**: GLASS-UI-DIRECT-REPLACE
- **执行日期**: 2026-05-03
- **EHPK 路径**: `apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- **SHA256**: `9adbe30a41a32fd7d4a9b0b13f60ed2d76908a0bd8de519cbe84d22affe737f2`
- **构建结果**: 成功（29 modules transformed）

---

## 1. 替换文件

| 文件 | 来源 |
|------|------|
| `src/glass/glassScreens.ts` | `direct_glass_ui_replacement_package/replacement/glass/glassScreens.ts` |
| `src/glass/glassLayout.ts` | `direct_glass_ui_replacement_package/replacement/glass/glassLayout.ts` |

## 2. 修复的问题

### phonePageRegistry.ts 类型错误

**问题**: `PHONE_PAGE_SECTIONS` 缺少 `diagnostics`、`history`、`debug` 三个书签条目，导致 TypeScript 类型检查失败。

**修复**: 补全缺失条目：
```typescript
diagnostics: ['debug-log'],
history: [],
debug: ['debug-log'],
```

## 3. 眼镜端 UI 改动内容

### 首页（home）
```
第一行：时间 + 电量
第二行：天禄助手
第三行：副标题
中间：[CAM]   [AI]   [BOT]
      视觉识别  呼叫天禄  交易状态
底部：● / ○ / ○ 选择指示器
      G2 ONLINE  R1 READY
      ↑↓ 选择   单触进入
```

### 视觉页（vision_*）
- `vision_preparing`：正在打开手机相机、请完成拍照
- `vision_ready`：相机已就绪、R1 单触拍照、下滑返回
- `vision_captured`：已锁定当前画面、再次单触上传、上滑重拍下滑取消
- `vision_uploading`：正在发送图片、[AI ANALYZING]

### 语音页（voice_*）
- `voice_menu`/`voice_idle`：呼叫天禄、手机端按住说话、R1单触开始/结束、最长录音120秒
- `voice_recording`：时间 + PCM + CHUNKS 实时显示
- `voice_finalizing`：录音结束、正在识别、[ASR PROCESSING]
- `voice_to_vision`：检测到视觉意图、正在切换
- `voice_answer`：天禄回复 + 单触继续/下滑返回
- `voice_error`：语音错误 + 单触重试/下滑返回
- `voice_no_pcm`：未收到麦克风数据 + 检查G2连接/权限

### 交易页（trading_status）
```
运行正常 / 运行需关注
心跳 | 策略
持仓/挂单 | PnL
风险
单触刷新  下滑返回
```

### 回复页（reply）
- 居中显示标题 + 内容
- R1 单击返回

## 4. 构建结果

```
✓ 29 modules transformed
dist/index.html          12.30 kB
dist/assets/*.css        22.79 kB
dist/assets/*.js       182.93 kB
✓ built in 741ms
✓ packed out.ehpk (76377 bytes)
```

## 5. EHPK 信息

- **文件**: `g2-vision-voice-assistant.ehpk`
- **SHA256**: `9adbe30a41a32fd7d4a9b0b13f60ed2d76908a0bd8de519cbe84d22affe737f2`
- **路径**: `apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`

## 6. 未解决问题

无

## 7. 下一步

- [ ] 真机验证眼镜端首页显示
- [ ] 真机验证视觉页流程
- [ ] 真机验证语音页录音显示
- [ ] 真机验证交易页数据展示
