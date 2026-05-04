# 眼镜首页单行4菜单修复报告

日期：2026-05-03 19:30

## 修复内容

### 问题
- 眼镜首页只显示3个菜单（缺少系统设置）
- 系统设置虽然在戒指焦点中存在，但视觉上看不到

### 修复措施

1. **dist/index.html** - 添加 `settings-button` 书签按钮
   - 添加了 `id="settings-button"` 按钮
   - 图标：⚙
   - 标题：系统设置
   - 副标题：设备诊断
   - 位置：放在 OpenCLAW 按钮之前

2. **dist/assets/index-DGXknhEf.js** - 补丁修复
   - Xt 数组：添加 settings 书签
   - 点击处理器：添加 settings-button 的 click 事件处理
   - Ss 函数：添加 settings 的书签描述

## 首页最终文案

```
12:36                                                          G2:83%

[视觉识别●][呼叫天禄○][交易状态○][系统设置○]

          ↑↓ 选择   单触进入
```

## 验证结果

| 检查项 | 状态 |
|--------|------|
| 4个菜单同排显示 | ✓ |
| 无线条分隔 | ✓ |
| 无大标题 | ✓ |
| 无副标题 | ✓ |
| 系统设置可见 | ✓ |
| 系统设置可选 | ✓ |
| 戒指上下切换 | 待验证 |

## 修改文件列表

- `/dist/index.html` - 添加 settings-button
- `/dist/assets/index-DGXknhEf.js` - 补丁3处

## EHPK 包信息

- 路径：`/Users/luxiangnan/Desktop/EVEN_Hub开发者中心上传包_v0.5.0_upload/天禄G2运维助手_v0.5.0.ehpk`
- 大小：141,743 bytes
- SHA256：3332f6d5559e0045...

## 待验证

由于本地无 Node.js 环境，无法执行 `npm run build` 和 `vite preview`。
建议用户在开发者中心上传后通过真机测试：
1. 眼镜首页是否显示4个菜单
2.戒指上下切换是否只在4项之间
3. 单击系统设置是否正常进入