# 2026-05-02 23:20 · G2 眼镜子模块居中 HUD 重塑报告

## 本轮目标

按用户提供的 GPT PNG 设计参考，统一眼镜端所有主要 Glass 页面：

- 内容居中
- 主任务突出
- 去掉首页工程状态干扰
- 三大主版块优先：视觉识别、呼叫天禄、交易状态
- 设置/诊断仍保留为手机插件端功能，按需同步到眼镜

## 修改文件

- `apps/evenhub-plugin/src/glass/glassScreens.ts`
- `apps/evenhub-plugin/src/main.ts`
- `apps/evenhub-plugin/app.json`
- `apps/evenhub-plugin/package.json`
- `package-lock.json`

## 关键调整

1. 首页去掉 `G2 ONLINE / R1 READY / LINK OK` 等工程状态。
2. 首页只显示三个核心入口，并全部居中：
   - 视觉识别
   - 呼叫天禄
   - 交易状态
3. 视觉、语音、交易、回复、错误、诊断、设置页面的主体文案统一居中。
4. 交易状态主入口修复：R1 单触确认后会直接执行 `runTradingOverview()`，不再只停留在书签说明。
5. 插件版本提升到 `0.4.0`。

## 验证结果

- `npm run typecheck`：通过
- `npm run build`：通过
- `npm run pack:g2`：通过

## EHPK

- 路径：`apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- 版本：`0.4.0`
- SHA256：`8fefbe9216b5cf0d4dc10eec9cad50e372f2fccb2a39527f532bd8a9f3d6d807`

## 仍需真机观察

- G2 单 TextContainer 对居中文案的实际显示行距。
- 交易状态 R1 单触后公网控制台数据加载是否稳定。
- 视觉识别/呼叫天禄/交易状态三大入口的选中提示是否足够清楚。
