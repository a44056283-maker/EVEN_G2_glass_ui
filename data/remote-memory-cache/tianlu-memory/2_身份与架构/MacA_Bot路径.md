# Mac A Bot 启动路径

## Bot 目录

| 类型 | 路径 |
|------|------|
| Freqtrade主体 | `~/freqtrade` |
| 控制台UI | `~/freqtrade_console` |
| Bot数据目录 | `~/freqtrade/user_data_*` |

## 各 Bot 端口 - userdir 映射

| 端口 | userdir |
|------|---------|
| 9090 | `/Users/luxiangnan/freqtrade/user_data_gate17656685222` |
| 9091 | `/Users/luxiangnan/freqtrade/user_data_gate85363904550` |
| 9092 | `/Users/luxiangnan/freqtrade/user_data_gate15637798222` |
| 9093 | `/Users/luxiangnan/freqtrade/user_data_okx_9093` |
| 9094 | `/Users/luxiangnan/freqtrade/user_data_okx_9094` |
| 9095 | `/Users/luxiangnan/freqtrade/user_data_okx_9095` |
| 9096 | `/Users/luxiangnan/freqtrade/user_data_okx_9096` |
| 9097 | `/Users/luxiangnan/freqtrade/user_data_okx_9097` |

## 启动命令关键参数

```
SSL_CERT_FILE=/Volumes/TianLu_Storage/certs/ca.crt
FREQTRADE_ROOT=/Users/luxiangnan/freqtrade
venv入口: .venv311/bin/python3 .venv311/bin/freqtrade
```

## 重要教训

**禁止**：
- `pip install -e .`（会破坏 PYTHONPATH 优先级）
- 改 venv site-packages（除非 Mac B 需要同步模块）
- 重启正在跑的机器人
