# Bot 启动命令（正确方式）

**更新: 2026-04-22 验证**

## 正确启动模板

```bash
cd /Users/luxiangnan/freqtrade
SSL_CERT_FILE=/Volumes/TianLu_Storage/certs/ca.crt \
FREQTRADE_ROOT=/Users/luxiangnan/freqtrade \
HTTPS_PROXY= HTTP_PROXY= ALL_PROXY= \
nohup .venv311/bin/python3 .venv311/bin/freqtrade trade \
  --config config_shared.json \
  --config config_XXXX_overlay.json \
  --userdir /Users/luxiangnan/freqtrade/user_data_XXX \
  -s FOttStrategy > /private/tmp/bot_XXXX.log 2>&1 &
```

## 关键点
- 用 `.venv311/bin/python3 .venv311/bin/freqtrade` 而非直接调用
- **禁止**加 `PYTHONPATH=...` 环境变量（会破坏 venv 模块查找）
- 日志输出到 `/private/tmp/bot_XXXX.log`

## 错误做法（会导致 ModuleNotFoundError）

```bash
# ❌ 错误：加了 PYTHONPATH
PYTHONPATH=/Users/luxiangnan/freqtrade nohup .venv311/bin/freqtrade trade ...

# ❌ 错误：用完整 Python 路径
/opt/homebrew/Cellar/python@3.11/.../Python .venv311/bin/freqtrade trade ...
```

## 工具脚本
```bash
cd /Users/luxiangnan/freqtrade
./bot_manager.sh status          # 查看所有机器人
./bot_manager.sh start 9091     # 启动 9091
./bot_manager.sh stop 9091      # 停止 9091
./bot_manager.sh cleanup        # 清理重复进程
```

## 各端口配置速查

| 端口 | 交易所 | userdir |
|------|--------|---------|
| 9090 | Gate | user_data_gate17656685222 |
| 9091 | Gate | user_data_gate85363904550 |
| 9092 | Gate | user_data_gate15637798222 |
| 9093-9097 | OKX | user_data_okx_XXXX |

## 验证命令
```bash
ps aux | grep "freqtrade trade" | grep -v grep
lsof -i :9090 -i :9091 -i :9092
curl -s -u "freqtrade:freqtrade" http://127.0.0.1:9090/api/v1/ping
```
