# 20260502_2331 Glass 首页三横卡 + 去拉伸空档报告

## 本轮目标

根据用户反馈修复：

1. 眼镜首页不要再出现 `TL-OS` 等工程头标。
2. 首页三大主入口不要缩在左下角。
3. 上下不要有拉伸空档。
4. R1/触摸滚动时不要出现 WebView 橡皮筋回弹空白。

## 修改内容

### 眼镜端

- 修改 `apps/evenhub-plugin/src/glass/glassScreens.ts`
- `renderHome()` 改为仅显示：
  - 天禄 G2 运维助手
  - 视觉识别 / 呼叫天禄 / 交易状态 三个横向主卡
  - 上下选择 / 单触进入
- 删除首页 `TL-OS // TIANLU` 头标。
- 删除首页多余空行。
- 保留三主入口横向并排，选中项使用更强边框和 `▲` 标记。

### 兜底 G2 文本

- 修改 `apps/evenhub-plugin/src/display.ts`
- `formatForG2()` 不再自动追加 `TL OS + 时间 + 电量`。

### 手机插件 / WebView

- 修改 `apps/evenhub-plugin/src/style.css`
- `html, body` 改为固定 100% 高度并关闭 body 级 overscroll。
- `#app` 改为 `100dvh` 内部滚动，避免整个 WebView 被拉出上下空白。
- 增加 `box-sizing: border-box`，避免 `height: 100dvh + padding` 撑高页面。

## 验证

```bash
npm run typecheck
npm run build
npm run pack:g2
```

结果：全部通过。

## EHPK

```text
apps/evenhub-plugin/g2-vision-voice-assistant.ehpk
```

SHA256：

```text
eb64b0948e255b6563a5d2473f506bc8e91663555291e98411fcd1eb0b405341
```

## 注意

G2 TextContainer 仍然不能像网页一样设置字体大小。当前用“横向三卡 + 双行标题 + 选中边框”模拟大入口视觉。

