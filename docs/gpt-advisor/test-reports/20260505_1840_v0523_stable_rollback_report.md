# v0.5.23 稳定回退救援包报告

时间：2026-05-05 18:40

## 结论

v0.5.22 仍出现安装后插件不可显示、菜单不可点击，说明 v0.5.19-v0.5.22 的定位诊断、Bridge 历史主存储或图片 SDK 兼容路径仍可能触发 Even App 宿主异常。

本版本不继续叠加功能，直接回退到 v0.5.18 的稳定插件代码，只保留版本号 `0.5.23`，目标是先恢复：

1. 插件能在“我的插件”显示。
2. 启动不闪退。
3. 手机端菜单可点击。

本版本状态：救援测试包，不批准正式上架。

## 回退范围

回退到 `5f6e431` 的 `apps/evenhub-plugin` 状态，并移除以下高风险改动：

- `location` manifest 权限。
- 设置页“实时定位诊断”。
- Even Bridge 历史主存储。
- v0.5.19 的灰度 `updateImageRawData` 多 payload 预览路径。
- `min_sdk_version: 0.0.10`。

保留：

- `package_id` 不变。
- `min_sdk_version` 为 `0.0.9`。
- 版本号提升为 `0.5.23`。

## 验证

- `node node_modules/typescript/bin/tsc --noEmit -p apps/evenhub-plugin/tsconfig.json`：通过
- `esbuild` 前端构建：通过
- EvenHub CLI pack：通过

## 产物

- EHPK：`/Users/luxiangnan/Desktop/g2-vision-voice-assistant-v0.5.23-stable-rollback.ehpk`
- SHA256：`954d2d93184eb15dcd6091ad9197456c15392750c5607983b1d0519e2ad73b48`

## 后续原则

先确认 v0.5.23 能显示、能点击，再把定位/历史/预览拆成单独实验分支，不能再把高风险能力一起合并进主测试包。

