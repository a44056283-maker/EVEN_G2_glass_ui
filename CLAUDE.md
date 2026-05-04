# CLAUDE.md

## 项目名称
天禄 G2 运维助手

## 目标网站
https://g2-vision.tianlu2026.org

## 核心规则

1. 手机网页 UI 和 G2 眼镜端 Glass UI 必须彻底分离。
2. 手机网页 UI 不得被 Glass UI 改动污染。
3. G2 眼镜端 UI 只通过 Even Hub SDK container / GlassRenderer / glassScreens 渲染。
4. 手机网页 UI 使用 DOM / CSS / Web App layout。
5. 任何修改 Glass UI 的任务，禁止改手机网页布局、手机网页 CSS、手机网页模块结构。
6. 任何修改手机网页 UI 的任务，禁止改 G2 GlassRenderer / glassScreens，除非用户明确要求。
7. G2 主菜单只保留：
   - 视觉识别
   - 呼叫天禄
   - 交易状态
8. 手机网页可以保留完整模块：
   - 视觉识别
   - 呼叫天禄
   - 交易状态
   - 设置 / 连接诊断 / 权限自检 / 历史 / 调试
9. 眼镜端不显示设置、OpenCLAW、连接扫描、权限自检、相册选图、设备诊断、实时采集、视频采集、场景记忆等杂项。
10. 设置类、诊断类、权限类功能只放手机网页端。
11. 不要把手机网页中的按钮、书签、CSS 类名、布局结构用于 G2 眼镜端。
12. 不要把 G2 眼镜端的文本 HUD 模板覆盖到手机网页 DOM。
13. R1 / G2 输入只作为眼镜端控制逻辑，不应改变手机网页 UI 布局。
14. G2 原生麦克风主链路是：
    bridge.audioControl(true) -> event.audioEvent.audioPcm -> WebSocket /audio。
15. 浏览器 SpeechRecognition 只能作为 experimental fallback，不能作为 G2 主路径。
16. 交易机器人第一阶段只读，不允许下单，平仓、改杠杆、改策略、提现。
17. 所有审计、补丁任务、测试报告都写入：
    docs/gpt-advisor/
18. 不输出 .env、API key、token、交易密钥、私钥。

## 当前优先级

P0：
1. 恢复手机网页 UI，不要受 Glass UI 改动污染。
2. 建立 Phone UI 与 Glass UI 的文件级隔离。
3. 保持 G2 Glass UI 三大主类：视觉识别、呼叫天禄、交易状态。
4. 继续修呼叫天禄语音链路。
