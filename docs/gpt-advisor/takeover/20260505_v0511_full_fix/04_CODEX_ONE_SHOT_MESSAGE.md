请读取 `01_CODEX_MASTER_PROMPT.md` 并执行。

这次由 Codex 接管 Claude 的历史工作，不要再半成品上架。

必须修 v0.5.11 的 7 个问题：
1. 眼镜端闪退，先审计服务端和前端日志。
2. 增加定位识图能力。
3. 拍照后 G2 显示拍摄成功/短暂预览说明，历史保存。
4. 手机端运行历史和全部历史为空，修历史存储。
5. 识图不准，增加定位、OpenCLAW 记忆、知识库/可选搜索增强。
6. 交易子菜单确认不准和加载慢，增加缓存和等待话术。
7. 交易子菜单 R1 焦点必须移动到子菜单项，白名单价只显示 BTC/ETH/SOL/BNB/DOGE 实时价格。

子智能体分工：
- crash-log-agent
- location-vision-agent
- photo-preview-history-agent
- vision-accuracy-agent
- trading-cache-focus-agent
- qa-release-agent

完成后必须：
- typecheck/build/pack:g2 通过
- 3 轮真机验收
- 生成 EHPK
- SHA256
- 报告
- 不通过不准上架
