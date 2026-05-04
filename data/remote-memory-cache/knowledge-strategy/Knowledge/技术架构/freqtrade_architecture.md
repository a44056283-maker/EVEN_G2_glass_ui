# Freqtrade 架构与监控告警学习笔记

## 学习日期：2025-07-17
## 岗位：基础设施工程师（工部/技术运维部）

---

## 一、Freqtrade 源码架构

### 1.1 核心模块结构

Freqtrade 是一个开源的加密货币量化交易机器人，核心架构分为以下模块：

| 模块 | 路径 | 职责 |
|------|------|------|
| `freqtrade/main.py` | 入口 | 启动初始化、命令解析 |
| `freqtrade/exchange/` | 交易所接口 | 对接交易所API（ Binance, Gate.io, OKX 等） |
| `freqtrade/pairlist/` | 交易对过滤 | 管理可交易交易对列表 |
| `freqtrade/strategy/` | 策略基类 | 策略接口定义，所有自定义策略继承自 `IStrategy` |
| `freqtrade/rpc/` | RPC通信 | Telegram/Discord 通知、API控制 |
| `freqtrade/freqtradebot.py` | 核心引擎 | 交易循环、订单管理、持仓跟踪 |
| `freqtrade/misc.py` | 工具函数 | 通用工具 |
| `freqtrade/configuration/` | 配置管理 | config.json 解析加载 |

**核心流程：**
```
main.py → FreqtradeBot → exchange 获取数据 → strategy 产生信号 → 执行订单 → RPC 通知
```

### 1.2 策略文件（Strategy）结构

策略文件必须实现 `IStrategy` 接口，核心方法：

```python
from freqtrade.strategy import IStrategy
from backtesting import BTConfig

class MyStrategy(IStrategy):
    # 1. 必要参数
    minimal_roi = { "0": 0.10 }  # 止盈：0分钟盈利10%即平仓
    stoploss = -0.10              # 止损：-10%
    timeframe = '5m'             # K线周期

    # 2. 核心信号方法（必须实现）
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """添加技术指标（RSI、MACD、Bollinger Bands等）"""
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """生成买入信号"""
        dataframe.loc[
            (dataframe['rsi'] < 30) & (dataframe['volume'] > 0),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """生成卖出信号"""
        dataframe.loc[
            (dataframe['rsi'] > 70),
            'exit_long'] = 1
        return dataframe
```

### 1.3 DCA（Dollar-Cost Averaging）机制实现原理

DCA 在 Freqtrade 中称为 **DCA（Decreasing Cost Average）** 或通过 **安全卫士（Stoploss Guards）** 实现：

**核心概念：**
- 初始仓位建仓后，价格不利时**补仓**降低成本
- 每次补仓后重新计算平均入场价
- 当价格回升到**盈亏平衡点**以上时一次性平仓

**Freqtrade 实现方式：**

```python
# config.json 中配置 DCA
{
    "position_stacking": true,       # 允许同一交易对多个持仓
    "unfilledtimeout": {
        "entry": 10,                 # 入场未成交超时（分钟）
        "exit": 30,
        "exit_timeout_count": 3      # 3次超时后强制平仓
    },
    "entry_pricing": {
        "price_last_balance": 0.0    # 使用盘口价格
    }
}
```

**DCA 本质逻辑：**
```
持仓亏损 → 触发补仓信号 → 以更低价格加仓 → 平均成本下降 → 价格回升后平仓获利
```

---

## 二、监控告警设计

### 2.1 监控的3个层级

| 层级 | 检查内容 | 实现方式 |
|------|----------|----------|
| **L1 进程存活** | 进程是否存在、进程数量 | `pgrep freqtrade`、`systemctl status` |
| **L2 端口响应** | RPC/API端口是否监听、HTTP是否响应 | `netstat/ss -tlnp` + `curl localhost:8080/ping` |
| **L3 业务指标** | 订单状态、持仓、盈亏、延迟 | Freqtrade RPC API 查询 |

### 2.2 告警阈值设计

```python
ALERT_THRESHOLDS = {
    "cpu_percent": 80,        # CPU > 80% 告警
    "memory_percent": 85,     # 内存 > 85% 告警
    "order_latency_ms": 500,  # 订单延迟 > 500ms 告警
    "open_trades_max": 10,    # 开放交易 > 10个 告警
    "daily_loss_percent": 5,  # 日亏损 > 5% 告警
}
```

### 2.3 灾难恢复基本流程

```
1. 告警触发 → 记录日志 + 发送通知（Telegram/Discord）
2. 自动止血 → 停止新开仓、关闭高风险持仓
3. 人工介入 → 排查原因（进程崩溃/网络/交易所问题）
4. 服务恢复 → 重启进程 / 切换备用实例
5. 复盘记录 → 更新监控阈值 / 修复Bug
```

---

## 三、Python实现 — 端口监控脚本

```python
#!/usr/bin/env python3
"""
端口监控脚本 - 检查Freqtrade RPC端口是否响应
作者：工部/基础设施工程师
"""

import socket
import sys
import time
import subprocess
import logging
from datetime import datetime

# 配置
HOST = "127.0.0.1"
PORT = 8080  # Freqtrade RPC默认端口
TIMEOUT = 5  # 连接超时（秒）
CHECK_INTERVAL = 60  # 检查间隔（秒）

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='/var/log/freqtrade_monitor.log'
)

def check_port(host: str, port: int, timeout: int) -> bool:
    """检查端口是否响应"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        logging.error(f"端口检查异常: {e}")
        return False

def get_process_status() -> str:
    """获取Freqtrade进程状态"""
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'freqtrade'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            return f"运行中 (PID: {', '.join(pids)})"
        else:
            return "未运行"
    except Exception as e:
        return f"检查失败: {e}"

def health_check():
    """健康检查主逻辑"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # L1: 进程状态
    proc_status = get_process_status()
    print(f"[{timestamp}] 进程状态: {proc_status}")
    
    # L2: 端口响应
    port_ok = check_port(HOST, PORT, TIMEOUT)
    port_status = "正常" if port_ok else "异常"
    print(f"[{timestamp}] 端口状态: {HOST}:{PORT} - {port_status}")
    
    # 综合状态
    if not port_ok:
        logging.warning(f"监控告警: 端口 {HOST}:{PORT} 无响应!")
        print(f"🚨 告警: RPC端口无响应，请检查Freqtrade服务!")
        return False
    else:
        logging.info(f"状态正常: {HOST}:{PORT}")
        return True

if __name__ == "__main__":
    print("=" * 50)
    print("Freqtrade 端口监控系统")
    print("=" * 50)
    
    healthy = health_check()
    sys.exit(0 if healthy else 1)
```

**使用方法：**
```bash
# 直接运行
python3 freqtrade_monitor.py

# 持续监控（每60秒检查一次）
watch -n 60 python3 freqtrade_monitor.py

# 添加到crontab
# */5 * * * * /usr/bin/python3 /opt/freqtrade_monitor.py >> /var/log/freqtrade_monitor_cron.log 2>&1
```

---

## 核心理解总结

1. **Freqtrade架构**：模块化设计，策略层与执行层分离，通过RPC实现远程控制
2. **DCA机制**：本质是金字塔加仓，通过补仓降低平均成本，需配合严格的止损
3. **监控层级**：进程 → 端口 → 业务，三层递进，越上层越需要业务知识
4. **告警原则**：宁缺毋滥，误报率高的告警比没有告警更糟糕
5. **灾难恢复**：止血优先，恢复其次，复盘最后
