# P0-002 R1 相机控制与眼镜菜单确认测试报告

时间：2026-05-02 10:23

## 本轮范围

只修复 R1 菜单确认与视觉相机控制：

1. R1 在首页选择“视觉识别”后进入视觉下一级页。
2. 进入视觉页后预热手机后置摄像头。
3. R1 单击拍照。
4. 已拍照后 R1 单击或双击发送识别。
5. 已拍照后 R1 上滑重拍、下滑取消。

本轮没有修改 G2 麦克风、ASR、OpenCLAW、交易机器人接口。

## 修改文件

- `apps/evenhub-plugin/src/main.ts`
- `apps/evenhub-plugin/src/glass/glassScreens.ts`

## 关键修复

### 1. 视觉页优先处理 R1 事件

原问题：

`handleG2ControlEvent()` 里全局 `double_click` 返回首页逻辑先执行，导致视觉页 `captured` 状态下的 R1 双击发送永远进不到 `handleVisionR1Intent()`。

现修复：

当 `activeGlassPage === 'vision'` 时，所有 R1 intent 先交给 `handleVisionR1Intent()`。

### 2. 首页视觉菜单真正进入下一级

原问题：

R1 单击首页“视觉识别”只调用 `renderG2Bookmark()`，仍停留在首页。

现修复：

`executeFocusedControl()` 和 `executeCurrentG2Bookmark()` 在视觉入口上调用 `enterVisionPage()`，进入视觉页并预热相机。

### 3. 已拍照状态支持确认、重拍、取消

当前行为：

- `camera_ready` + R1 单击：截帧拍照。
- `captured` + R1 单击：发送识别。
- `captured` + R1 双击：发送识别。
- `captured` + R1 上滑：重新截帧拍照。
- `captured` + R1 下滑：取消当前照片，回到相机待命。

## 眼镜端文案

视觉准备：

```text
正在准备相机...
正在预热手机后置
摄像头视频流
就绪后 R1 单击拍照
```

视觉已拍照：

```text
已锁定当前画面
R1 单击  发送识别
R1 双击  也可发送
R1 上滑  重新拍照
R1 下滑  取消返回
```

## 验证命令

```bash
export PATH="/Users/luxiangnan/Desktop/EVEN G2视觉和语音对讲系统/.tools/node-v22.22.2-darwin-arm64/bin:$PATH"
npm run typecheck
npm run build
npm run pack:g2
cp apps/evenhub-plugin/g2-vision-voice-assistant.ehpk apps/evenhub-plugin/g2-视觉-语音助手.ehpk
shasum -a 256 apps/evenhub-plugin/g2-vision-voice-assistant.ehpk apps/evenhub-plugin/g2-视觉-语音助手.ehpk
```

## 验证结果

- `npm run typecheck`：通过。
- `npm run build`：通过。
- `npm run pack:g2`：通过。

## EHPK

路径：

- `apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- `apps/evenhub-plugin/g2-视觉-语音助手.ehpk`

SHA256：

```text
1d1900476b4b642a0218a0d511155ea1a9c0412f72672768f90bf9e3c4813344
```

## 需要真机验收

请在 Even App / G2 真机上按顺序测：

1. R1 上下滑动选中“视觉识别”。
2. R1 单击进入视觉页。
3. 眼镜显示“正在准备相机”后变为“相机已就绪”。
4. R1 单击拍照。
5. 眼镜显示“已锁定当前画面”。
6. R1 单击或双击发送识别。
7. 结果能显示到网页和 G2。
8. 已拍照状态下，上滑能重拍，下滑能取消。

## 仍未解决

- R1 不同固件/容器下的 envelope/type/source 仍需真机日志补全。
- 如果 iOS / Even WebView 不允许 R1 事件触发 `getUserMedia`，视觉页会显示相机权限错误；这属于真机权限策略，需要根据日志再处理。
- G2 麦克风、ASR、OpenCLAW 本轮未处理。

## 下一步建议

如果本轮真机通过，进入：

```text
P0-003：R1 输入真机日志表 + G2 结果显示稳定性
```

如果 R1 仍不能进视觉页或拍照，下一步先打开 `debug_input` 页面记录 R1 单击/双击/上滑/下滑的 envelope/type/source。
