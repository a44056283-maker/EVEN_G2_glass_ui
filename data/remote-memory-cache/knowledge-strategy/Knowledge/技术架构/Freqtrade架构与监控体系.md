# Freqtrade架构与监控告警 — 太子专属武器

> 版本：v1.0 | 更新：2026-04-03
> 来源：工部freqtrade_architecture.md
> 定位：Freqtrade机器人架构、监控体系

---

## 一，Freqtrade核心架构

### 1.1 模块结构

| 模块 | 职责 |
|------|------|
| main.py | 入口、启动初始化、命令解析 |
| exchange/ | 对接交易所API（Binance、Gate.io、OKX）|
| pairlist/ | 交易对过滤、管理可交易对 |
| strategy/ | 策略基类，自定义策略继承IStrategy |
| rpc/ | Telegram/Discord通知、API控制 |
| freqtradebot.py | 核心引擎、交易循环、订单管理 |
| misc.py | 通用工具函数 |

### 1.2 核心流程

```
main.py → FreqtradeBot 
  → exchange 获取数据 
  → strategy 产生信号 
  → 执行订单 
  → RPC 通知
```

---

## 二，策略文件结构

```python
from freqtrade.strategy import IStrategy

class MyStrategy(IStrategy):
    # 必要参数
    minimal_roi = {"0": 0.10}  # 止盈
    stoploss = -0.10               # 止损
    timeframe = '5m'              # K线周期

    def populate_indicators(self, dataframe, metadata):
        """添加技术指标"""
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        """生成买入信号"""
        dataframe.loc[
            (dataframe['rsi'] < 30) & (dataframe['volume'] > 0),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        """生成卖出信号"""
        dataframe.loc[dataframe['rsi'] > 70, 'exit_long'] = 1
        return dataframe
```

---

## 三，监控告警体系

### 3.1 进程监控

| 检查项 | 方法 | 阈值 |
|--------|------|------|
| 进程存活 | lsof检查端口 | 任意端口无监听=告警 |
| API可用性 | /api/v1/ping | 返回非200=告警 |
| 日志ERROR | 日志文件扫描 | 存在ERROR=告警 |
| 磁盘空间 | df检查 | <10%可用=告警 |

### 3.2 Python实现

```python
import subprocess
import json

def check_bot_status(port, user="freqtrade", pass_="freqtrade"):
    """检查机器人状态"""
    try:
        r = subprocess.run(
            ["curl", "-s", "-u", f"{user}:{pass_}",
             f"http://127.0.0.1:{port}/api/v1/ping"],
            capture_output=True, timeout=5
        )
        if r.returncode == 0 and b'"status":"ok"' in r.stdout:
            return {"port": port, "status": "online"}
    except:
        pass
    return {"port": port, "status": "offline"}

def scan_all_bots(ports=[9090,9091,9092,9093,9094,9095,9096,9097]):
    """扫描所有机器人"""
    results = []
    for port in ports:
        results.append(check_bot_status(port))
    return results
```

---

## 四，健康检查脚本

```python
#!/usr/bin/env python3
"""Freqtrade健康检查"""
PORTS = range(9090, 9098)
ALERT_FILE = "/tmp/freqtrade_alert.txt"

def health_check():
    alerts = []
    for port in PORTS:
        status = check_bot_status(port)
        if status["status"] == "offline":
            alerts.append(f"Port {port} is OFFLINE")

    if alerts:
        with open(ALERT_FILE, "w") as f:
            f.write("\n".join(alerts))
        return False
    return True

if __name__ == "__main__":
    if not health_check():
        print("ALERT: Some bots are offline!")
    else:
        print("All bots healthy")
```

---

## 五，故障排查清单

| 症状 | 可能原因 | 处理方法 |
|------|---------|---------|
| 进程存在但API无响应 | RPC端口被阻塞 | 检查防火墙/重启进程 |
| 日志显示空文件 | venv损坏 | 重建venv |
| 403 Forbidden | API权限不足 | 检查config.json的keys |
| Websocket断连 | 网络问题 | 检查代理/重启 |
| 强平未触发 | 保证金率计算错误 | 检查 config.json |

---

_本策略由太子（天禄）整理_
