# P0 设置诊断真实化测试报告

时间：2026-05-02 11:49

## 本轮范围

修复第四个“设置”书签下仍显示旧 OpenCLAW 语音占位的问题，并把连接诊断从 UI 摆设改为可执行动作。

## 修改文件

- `apps/evenhub-plugin/src/main.ts`
- `apps/evenhub-plugin/src/glass/glassScreens.ts`
- `apps/evenhub-plugin/index.html`
- `apps/evenhub-plugin/app.json`
- `apps/evenhub-plugin/package.json`

## 功能变化

- 设置书签下方三个子按钮改为：`一键扫描`、`一键修复`、`权限自检`。
- 眼镜诊断页改为中文：`天禄诊断中心`。
- 眼镜诊断页 R1 操作：单击扫描、上滑修复、下滑/双击返回。
- 网页设置面板增加：`一键扫描`、`一键修复`。
- 一键扫描会检查：后端 `/health`、视觉引擎状态、ASR 状态、OpenClaw 状态、交易只读接口。
- 一键修复会尝试重新请求相机、手机/耳机麦克风、G2 麦克风开关，并继续检查后端能力。
- `app.json` 新增 `phone-microphone` 权限，用于手机/蓝牙耳机麦克风兜底诊断。

## 构建测试

- `npm run typecheck`：通过
- `npm run build`：通过
- `evenhub pack`：通过

## EHPK

路径：`apps/evenhub-plugin/g2-视觉-语音助手.ehpk`

SHA256：

```text
9951df0950564ce190d666c97d3aeed16b296749eede464a80166f5a8f6603bd
```

版本：`0.2.5`

## 未解决

- 一键修复不能直接打开 iOS 系统设置，只能在当前 WebView 中重新请求权限并给出诊断结果。
- R1 首次直接启动手机摄像头仍受 iOS/WKWebView user activation 限制，仍建议手机端先启动视觉引擎。
- 真实 ASR 仍依赖后端 ASR endpoint 配置。
