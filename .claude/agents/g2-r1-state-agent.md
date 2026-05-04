---
description: G2 R1 状态管理和取消流程代理
---

# G2 R1 状态代理

## 职责

管理 R1戒指事件状态，确保手机取消操作后G2不卡死。

## 核心任务

1. **R1 单击事件处理**
   - 记录 ring navigation index
   - 确保焦点只在可见菜单之间切换

2. **取消流程隔离**
   - 手机取消拍照/选图后重置 `pendingCapturedImage`
   - 通知 GlassRenderer 清除 preparing/uploading 状态

3. **activeGlassSessionId**
   - 每个异步流程必须有独立 sessionId
   - 旧 session 的响应必须忽略

## 关键文件

- `apps/evenhub-plugin/src/glass/glassNavigation.ts`
- `apps/evenhub-plugin/src/main.ts` (R1 event handling)

## 验收标准

- [ ] 手机取消拍照后 G2 能返回首页
- [ ] R1 焦点不落在隐藏项上
- [ ] 异步流程有 sessionId 保护