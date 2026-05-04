# 机器人UI平仓冷却失效故障

**日期**: 2026-04-22
**现象**: 点击机器人原生UI（`http://localhost:9090/`）的"平仓"按钮后，冷却不生效
**影响**: 所有机器人的UI平仓按钮（9090-9097）

---

## 症状

点击"平仓"按钮后：
- 弹出提示"平仓成功，冷却已设置"（用户以为成功了）
- 但冷却实际未写入
- 冷却UI显示"🛡️冷却:多12h/空10h"只是配置文字，不是当前状态

---

## 根本原因

**文件**: `.venv311/lib/python3.11/site-packages/freqtrade/rpc/api_server/ui/installed/index.html`

`forceClose()` 和 `forceReverse()` 函数调用了**不存在的端点**：

```javascript
// 错误代码（两处）
fetch(BASE+'/autopilot/exit_cooldown', {...})  // ❌ 不存在
fetch(BASE+'/autopilot/sync_cooldown', {...})  // ❌ 路径不对
```

实际有效的端点路径：
```
/api/v1/autopilot/sync_cooldown   ← 正确
/autopilot/sync_cooldown           ← 返回405 Method Not Allowed
```

**验证方法**：
```bash
# ❌ 错误路径（405）
curl -X POST http://127.0.0.1:9090/autopilot/sync_cooldown
# 返回: HTTP/1.1 405 Method Not Allowed

# ✅ 正确路径（200）
curl -X POST http://127.0.0.1:9090/api/v1/autopilot/sync_cooldown
# 返回: {"ok":true,"pair":"ETH","direction":"SHORT","cooldown_sec":36000}
```

---

## 修复步骤

**修复文件**（venv，直接影响运行中的bot）：
`/Users/luxiangnan/freqtrade/.venv311/lib/python3.11/site-packages/freqtrade/rpc/api_server/ui/installed/index.html`

**修改1** - `forceClose()` 函数（约第1045行）：
```javascript
// 修复前
fetch(BASE+'/autopilot/exit_cooldown', {...})
alert('平仓成功，冷却已设置（同向6小时/反向2小时）');

// 修复后
fetch(BASE+'/api/v1/autopilot/sync_cooldown', {...})
const cdNote = direction === 'SHORT' ? '做空10小时' : '做多12小时';
alert('平仓成功，冷却已设置（同向' + cdNote + '，反向放行）');
```

**修改2** - `forceReverse()` 函数（约第1101行）：
```javascript
// 修复前
fetch(BASE+'/autopilot/exit_cooldown', {...})

// 修复后
fetch(BASE+'/api/v1/autopilot/sync_cooldown', {...})
```

---

## 验证冷却是否生效

```bash
# 平仓后查询冷却状态
curl -s -u "freqtrade:freqtrade" "http://127.0.0.1:9090/api/v1/autopilot/cooldown_status?pair=BTC" | python3 -m json.tool

# 期望结果：same_remaining_sec > 0（约36000秒=10小时）
# 如果 same_remaining_sec = 0，说明冷却未写入
```

---

## 冷却参数

| 方向 | 冷却时间 |
|------|---------|
| LONG（做多）| 12小时 |
| SHORT（做空）| 10小时 |
| 反向 | 不限制 |
