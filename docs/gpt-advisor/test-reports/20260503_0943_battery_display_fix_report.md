# G2 / R1 电量显示修复报告

## 基本信息

- **任务编号**: P0-BATTERY-001
- **执行日期**: 2026-05-03
- **EHPK 路径**: `apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`
- **SHA256**: `2d6b2f0d08642ebfc97e9254e842ce0859ac8f9d8a0810564b4a004d01f12987`
- **构建结果**: 成功（29 modules transformed）

---

## 1. 电量状态来源链路

| 来源 | 函数 | 缓存写入 |
|------|------|---------|
| `bridge.getDeviceInfo()` | `updateDeviceBatteryFromInfo()` | ✅ `setBatteryCache(snapshot, 'getDeviceInfo')` |
| `bridge.onDeviceStatusChanged()` | `updateDeviceBatteryFromStatus()` | ✅ `setBatteryCache(snapshot, 'onDeviceStatusChanged')` |
| 页面刷新缓存 | `initBatteryDisplay()` | 从 `localStorage` 恢复 |

## 2. 当前支持的 battery 字段

### 顶层通用字段
`batteryLevel`, `battery_level`, `battery`, `batteryPercent`, `battery_percent`, `batteryPercentage`, `battery_percentage`, `power`, `powerLevel`, `power_level`, `charge`, `chargeLevel`, `charge_level`, `capacity`, `capacityPercent`, `capacity_percent`, `percent`, `percentage`, `soc`, `level`

### 眼镜专用字段
`glassesBattery`, `glassBattery`, `g2Battery`, `g2_battery`, `glasses_battery`, `glassesBatteryLevel`, `glassBatteryLevel`, `g2BatteryLevel`, `leftGlassBattery`, `rightGlassBattery`

### 戒指专用字段
`ringBattery`, `r1Battery`, `r1_battery`, `ring_battery`, `ringBatteryLevel`, `r1BatteryLevel`, `remoteBattery`, `controllerBattery`, `ringPower`, `r1Power`, `remotePower`, `controllerPower`

### 嵌套路径（递归扫描）
`status`, `data`, `device`, `devices`, `deviceInfo`, `deviceStatus`, `battery`, `batteryInfo`, `power`, `ring`, `r1`, `remote`, `controller`, `glasses`, `g2`

---

## 3. 新增文件

| 文件 | 用途 |
|------|------|
| `src/device/batteryCache.ts` | 电量本地缓存（localStorage） |
| `src/device/extractBatterySnapshot.ts` | 多来源电量解析 |

## 4. 修改文件

| 文件 | 修改内容 |
|------|---------|
| `src/main.ts` | 引入电池模块，`initBatteryDisplay()` 启动时恢复缓存，`updateDeviceBatteryFromInfo/Status()` 写入缓存 |
| `src/style.css` | 新增 `.battery-tools` / `#battery-debug-info` / `#refresh-battery-button` 样式 |
| `index.html` / `dist/index.html` | 顶部初始文案改为"加载中"；设置页新增"设备电量"调试区 |

## 5. Cache 逻辑说明

- **存储键**: `g2vva-battery-v2`
- **写入时机**: 任何一次从 `getDeviceInfo` 或 `onDeviceStatusChanged` 拿到有效电量时
- **读取时机**: 页面初始化时 `initBatteryDisplay()` 先从 localStorage 恢复并立即显示
- **显示**: 不再长期显示 `--%`，优先显示缓存值；从未拿到过电量时显示 `未上报`

## 6. 顶部显示规则

| 状态 | 显示文案 |
|------|---------|
| 有值 | `G2 83%` / `R1 67%` |
| 无值但 bridge 已连接 | `G2 未上报` / `R1 未上报` |
| 设备未连接 | `G2 未连接` / `R1 未连接` |

## 7. 设置页电量面板文案

```
设备电量
G2：83%
R1：67%
来源：onDeviceStatusChanged
更新时间：15:42:18

[刷新电量]
```

如果无值：
```
G2：未上报
R1：未上报
来源：cache
更新时间：--
```

## 8. 构建结果

```
✓ 29 modules transformed
dist/index.html          12.30 kB
dist/assets/*.css        22.79 kB
dist/assets/*.js       182.52 kB
✓ built in 311ms
✓ packed out.ehpk (76461 bytes)
```

## 9. EHPK 信息

- **文件**: `g2-vision-voice-assistant.ehpk`
- **SHA256**: `2d6b2f0d08642ebfc97e9254e842ce0859ac8f9d8a0810564b4a004d01f12987`
- **路径**: `apps/evenhub-plugin/g2-vision-voice-assistant.ehpk`

## 10. 未解决问题

- Even App SDK 是否实际通过 `getDeviceInfo()` 或 `onDeviceStatusChanged` 上报有效电量字段，需真机确认
- 如果 SDK 从不上报电量字段，则需要找其他 event 类型（如 `jsonData`）

## 11. 下一步建议

1. 安装新 EHPK 后测试：连接 G2/R1 后顶部是否显示真实电量值
2. 如果仍显示"未上报"，打开设置页查看"设备电量"调试区的来源字段
3. 抓 `[G2 device info]` / `[G2 device status]` 日志确认 Even App 实际上报了哪些字段
