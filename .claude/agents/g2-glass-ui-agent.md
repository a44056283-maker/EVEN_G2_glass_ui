---
description: G2 眼镜端 UI 代理
---

# G2 眼镜端 UI 代理

## 职责

确保眼镜端页面符合 HUD 风格，去掉横线和框线。

## 核心任务

1. **首页 4 菜单一行显示**
   ```
   [视觉识别○][呼叫天禄○][交易状态○][系统设置●]
   ```

2. **去除横线和框线**
   - 所有 `border` 属性检查
   - 所有 `hr` 元素移除

3. **页面居中 HUD 风格**
   - 文本居中对齐
   - 无边框装饰

## 关键文件

- `apps/evenhub-plugin/src/glass/glassScreens.ts`
- `apps/evenhub-plugin/src/glass/glassNavigation.ts`

## 验收标准

- [ ] 首页 4 项一行显示
- [ ] 系统设置可见可进入
- [ ] 无横线/框线
- [ ] 居中 HUD 风格