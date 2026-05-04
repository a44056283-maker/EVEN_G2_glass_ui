# Bot隔离规则

**核心原则：每个机器人必须有独立文件夹和完整隔离，不允许任何共享文件。**

## 必须隔离的内容

每个机器人必须独立拥有：

| 类别 | 具体文件 |
|------|---------|
| **数据库** | `tradesv3_*.sqlite`（含 -wal, -shm）|
| **配置文件** | `config_*_overlay.json` |
| **策略文件** | `FOttStrategy.py`, `SupportResistanceEngine.py` |
| **缓存数据** | `data/`（K线数据），`logs/` |

## 可共享的文件（安全）

| 文件 | 说明 |
|------|------|
| `config_shared.json` | 无API keys，只有共享设置 |
| Freqtrade主体 | `.venv/` 中的 venv 本身 |
| `bot_manager.sh` | 启动脚本（配置表指定不同 userdir 即可）|

## userdir 路径必须用绝对路径

- 禁止用相对路径（如 `user_data_okx`）
- 正确：`/Users/luxiangnan/freqtrade/user_data_okx_9093`
- 错误：`user_data_okx_9093` 或空字符串

## 验证方法

```bash
# 检查无重复进程
./bot_manager.sh status

# 检查启动命令中有 --userdir 且为绝对路径
ps aux | grep "freqtrade trade" | grep "9090"
```
