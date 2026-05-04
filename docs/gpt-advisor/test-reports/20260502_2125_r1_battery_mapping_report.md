# R1 电量映射修复报告

时间：2026-05-02 21:25

## 本轮范围

只修复 R1 电量显示为“未上报 / --”的问题，不修改视觉、语音、交易、OpenCLAW 逻辑。

## 问题判断

当前代码可以读取 G2 电量，但 R1 电量容易丢失，主要有两个风险点：

1. `deviceStatusChanged` 事件中，R1 可能被 `isWearing` 等字段误判为 G2。
2. Even App / SDK 实际上报的 R1 电量字段可能不是单一 `batteryLevel`，旧解析路径过窄。

## 修改文件

- `apps/evenhub-plugin/src/main.ts`

## 关键修改

1. 优先用已知 G2 SN 反推未知设备为 R1，避免 R1 被误归类为 G2。
2. 扩展 R1 电量字段识别：
   - `ringBattery`
   - `r1Battery`
   - `ringBatteryLevel`
   - `r1BatteryLevel`
   - `remoteBattery`
   - `controllerBattery`
   - `ringPower`
   - `r1Power`
   - `remotePower`
   - `controllerPower`
3. 扩展嵌套结构解析：
   - `status`
   - `data`
   - `device`
   - `devices`
   - `deviceInfo`
   - `deviceStatus`
   - `battery`
   - `batteryInfo`
   - `power`
   - `ring`
   - `r1`
   - `remote`
   - `controller`
   - `glasses`
   - `g2`
4. 支持字符串百分比，例如 `"58%"`。
5. 增加 `kindSpecific` 日志，便于真机确认 R1 电量字段来源。

## 验证结果

```text
npm run typecheck  通过
npm run build      通过
npm run pack:g2    通过
```

## EHPK

```text
apps/evenhub-plugin/g2-vision-voice-assistant.ehpk
```

大小：

```text
73361 bytes
```

SHA256：

```text
9c556cc213500b4d7368a2dc7c67a4c179e35765141fb63f0a2f77e6de4772a4
```

## 仍需真机确认

如果上传此版本后 R1 仍显示“未上报”，说明当前 Even App 真机事件没有提供 R1 电量，或字段名仍不在本轮已覆盖列表内。

下一步需要抓手机网页控制台日志里的：

```text
[G2 device status]
[G2 battery update]
[G2 battery fallback]
```

重点看 R1 对应 JSON 中是否存在电量字段、SN、source/kind 字段。

## 下一步建议

1. 上传本轮 EHPK 真机验证 R1 电量。
2. 如果仍未上报，先不要伪造电量；改为把 R1 原始状态 JSON 缩短显示到诊断面板，定位真实字段名。
3. 若 Even SDK 当前不提供 R1 电量，则 UI 保持“未上报”，并在设置诊断里解释为“R1 电量未由 Even App 上报”。
