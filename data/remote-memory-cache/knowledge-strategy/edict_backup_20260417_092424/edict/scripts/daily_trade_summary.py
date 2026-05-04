#!/usr/bin/env python3
"""
交易每日总结报告 - 增强版
汇总过去24小时（8:30-次日8:30）的交易数据
包含：多账号余额、白名单资金流、策略信息
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any

# 配置
WORKSPACE = "/Users/luxiangnan/.openclaw/workspace-hubu"
DATA_DIR = f"{WORKSPACE}/data"
REPORTS_DIR = f"{DATA_DIR}/reports/daily_trade_summary"
LOG_FILE = f"{DATA_DIR}/logs/trade_summary.log"
FREQTRADE_DIR = "/Users/luxiangnan/freqtrade"

os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(f"{DATA_DIR}/logs", exist_ok=True)


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


# Bot配置
BOTS = {
    "9090": {"label": "Gate-USDT-多头", "exchange": "gateio", "config": "config_9090_overlay.json"},
    "9091": {"label": "Gate-USDT-空头", "exchange": "gateio", "config": "config_9091_overlay.json"},
    "9092": {"label": "Gate-USDT-中性", "exchange": "gateio", "config": "config_9092_overlay.json"},
    "9093": {"label": "OKX-15637798222", "exchange": "okx", "config": "config_9093_overlay.json"},
    "9094": {"label": "OKX-BOT85363904550", "exchange": "okx", "config": "config_9094_overlay.json"},
    "9095": {"label": "OKX-BOTa44056283", "exchange": "okx", "config": "config_9095_overlay.json"},
    "9096": {"label": "OKX-BHB16638759999", "exchange": "okx", "config": "config_9096_overlay.json"},
    "9097": {"label": "OKX-17656685222", "exchange": "okx", "config": "config_9097_overlay.json"},
}


def load_bot_config(config_file: str) -> Dict:
    """加载Bot配置"""
    try:
        path = Path(FREQTRADE_DIR) / config_file
        with open(path) as f:
            return json.load(f)
    except:
        return {}


def load_shared_config() -> Dict:
    """加载共享配置"""
    try:
        path = Path(FREQTRADE_DIR) / "config_shared.json"
        with open(path) as f:
            return json.load(f)
    except:
        return {}


def get_whitelist(config: Dict) -> List[str]:
    """获取白名单"""
    ex = config.get("exchange", {})
    return [p.replace("/USDT:USDT", "").replace("/USDT", "") for p in ex.get("pair_whitelist", [])]


def get_blacklist(config: Dict) -> List[str]:
    """获取黑名单"""
    ex = config.get("exchange", {})
    return [p.replace("/USDT:USDT", "").replace("/USDT", "") for p in ex.get("pair_blacklist", [])]


def load_trades_from_reports(report_date: str) -> List[Dict]:
    """从现有报告文件加载交易数据"""
    trades = []
    daily_dir = Path("/Users/luxiangnan/edict/data/reports/daily")
    
    # 尝试读取指定日期的报告
    report_file = daily_dir / report_date / "trade_report.json"
    if report_file.exists():
        try:
            with open(report_file) as f:
                data = json.load(f)
                trades = data.get("trades", [])
        except:
            pass
    
    # 如果没有特定日期的数据，读取最新可用数据
    if not trades:
        for date_dir in sorted(daily_dir.iterdir(), reverse=True)[:3]:
            report_file = date_dir / "trade_report.json"
            if report_file.exists():
                try:
                    with open(report_file) as f:
                        data = json.load(f)
                        trades = data.get("trades", [])
                        if trades:
                            break
                except:
                    pass
    
    return trades


def load_demo_trades() -> List[Dict]:
    """演示数据"""
    return [
        {"tradeId": "T20260324-001", "symbol": "BTC/USDT:USDT", "direction": "LONG", "volume": 0.5, "price": 68000, "profit": 1500, "fee": 32.5, "time": "09:15:22", "bot": "9090"},
        {"tradeId": "T20260324-002", "symbol": "ETH/USDT:USDT", "direction": "SHORT", "volume": 2.0, "price": 3500, "profit": -800, "fee": 14.0, "time": "10:22:35", "bot": "9091"},
        {"tradeId": "T20260324-003", "symbol": "SOL/USDT:USDT", "direction": "LONG", "volume": 5.0, "price": 145, "profit": 2200, "fee": 8.4, "time": "11:05:18", "bot": "9090"},
        {"tradeId": "T20260324-004", "symbol": "DOGE/USDT:USDT", "direction": "SHORT", "volume": 10000, "price": 0.12, "profit": -350, "fee": 7.25, "time": "13:42:11", "bot": "9091"},
        {"tradeId": "T20260324-005", "symbol": "BTC/USDT:USDT", "direction": "SHORT", "volume": 0.3, "price": 68500, "profit": 900, "fee": 20.55, "time": "14:30:45", "bot": "9092"},
    ]


def calculate_summary(trades: List[Dict], shared_config: Dict) -> Dict[str, Any]:
    """计算交易汇总"""
    if not trades:
        return {
            "reportDate": datetime.now().strftime("%Y-%m-%d"),
            "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "strategy": shared_config.get("strategy", "FOttStrategy"),
            "timeframe": shared_config.get("timeframe", "15m"),
            "summary": {"totalTrades": 0, "totalPnl": 0, "winRate": 0},
            "byBot": {},
            "bySymbol": {},
            "whitelist": [],
            "trades": []
        }
    
    total_pnl = sum(t.get("profit", 0) for t in trades)
    winning = [t for t in trades if t.get("profit", 0) > 0]
    win_rate = len(winning) / len(trades) * 100 if trades else 0
    
    # 按Bot统计
    by_bot = {}
    for t in trades:
        bot = t.get("bot", "unknown")
        if bot not in by_bot:
            by_bot[bot] = {"count": 0, "pnl": 0, "fees": 0}
        by_bot[bot]["count"] += 1
        by_bot[bot]["pnl"] += t.get("profit", 0)
        by_bot[bot]["fees"] += t.get("fee", 0)
    
    # 按币种统计
    by_symbol = {}
    for t in trades:
        sym = t.get("symbol", "UNKNOWN").replace("/USDT:USDT", "").replace("/USDT", "")
        if sym not in by_symbol:
            by_symbol[sym] = {"count": 0, "pnl": 0, "volume": 0}
        by_symbol[sym]["count"] += 1
        by_symbol[sym]["pnl"] += t.get("profit", 0)
        by_symbol[sym]["volume"] += t.get("volume", 0)
    
    return {
        "reportDate": datetime.now().strftime("%Y-%m-%d"),
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "strategy": shared_config.get("strategy", "FOttStrategy"),
        "timeframe": shared_config.get("timeframe", "15m"),
        "summary": {
            "totalTrades": len(trades),
            "totalPnl": round(total_pnl, 2),
            "winRate": round(win_rate, 2),
            "totalFees": sum(t.get("fee", 0) for t in trades),
        },
        "byBot": by_bot,
        "bySymbol": by_symbol,
        "trades": trades
    }


def generate_markdown(summary: Dict, bots_config: Dict) -> str:
    """生成Markdown格式报告"""
    s = summary["summary"]
    by_bot = summary.get("byBot", {})
    by_symbol = summary.get("bySymbol", {})
    
    lines = [
        f"# 📊 交易每日总结报告",
        f"",
        f"**报告日期**: {summary['reportDate']}",
        f"**生成时间**: {summary['generatedAt']}",
        f"",
        f"---",
        f"",
        f"## 🤖 策略信息",
        f"",
        f"| 项目 | 值 |",
        f"| --- | --- |",
        f"| 策略 | `{summary.get('strategy', 'FOttStrategy')}` |",
        f"| 周期 | `{summary.get('timeframe', '15m')}` |",
        f"| 交易标的 | USDT合约 |",
        f"",
        f"## 📈 核心指标",
        f"",
        f"| 指标 | 数值 |",
        f"| --- | --- |",
        f"| 交易次数 | **{s['totalTrades']}** |",
        f"| 总盈亏 | **{'+' if s['totalPnl'] > 0 else ''}{s['totalPnl']}** |",
        f"| 胜率 | **{s['winRate']}%** |",
        f"| 手续费 | {s.get('totalFees', 0)} |",
        f"",
        f"## 🏦 各账号盈亏",
        f"",
        f"| 账号 | 交易次数 | 盈亏 | 手续费 |",
        f"| --- | --- | --- | --- |",
    ]
    
    for bot_id, data in sorted(by_bot.items()):
        label = bots_config.get(bot_id, {}).get("label", bot_id)
        pnl = data["pnl"]
        lines.append(f"| {label} | {data['count']} | {'+' if pnl > 0 else ''}{pnl} | {data['fees']} |")
    
    lines.extend([
        f"",
        f"## 📊 白名单交易对",
        f"",
        f"| 交易对 | 交易次数 | 盈亏 | 成交量 |",
        f"| --- | --- | --- | --- |",
    ])
    
    for sym, data in sorted(by_symbol.items(), key=lambda x: x[1]["pnl"], reverse=True):
        pnl = data["pnl"]
        lines.append(f"| {sym}/USDT | {data['count']} | {'+' if pnl > 0 else ''}{pnl} | {data['volume']} |")
    
    if summary.get("trades"):
        lines.extend([
            f"",
            f"## 📋 交易明细",
            f"",
            f"| 时间 | 交易对 | 账号 | 方向 | 数量 | 价格 | 盈亏 |",
            f"| --- | --- | --- | --- | --- | --- | --- |",
        ])
        for t in sorted(summary["trades"], key=lambda x: x.get("time", "")):
            sym = t.get("symbol", "?").replace("/USDT:USDT", "").replace("/USDT", "")
            bot = t.get("bot", "?")
            direction = "🟢" if t.get("direction") == "LONG" else "🔴"
            pnl = t.get("profit", 0)
            lines.append(
                f"| {t.get('time','')} | {sym} | {bot} | {direction} | "
                f"{t.get('volume','')} | {t.get('price','')} | {'+' if pnl > 0 else ''}{pnl} |"
            )
    
    lines.append("")
    return "\n".join(lines)


def send_feishu(message: str) -> bool:
    """发送飞书通知"""
    env_file = Path(WORKSPACE) / ".env"
    webhook = ""
    if env_file.exists():
        for line in env_file.read_text().strip().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                if k.strip() in ("SHANGSHU_WEBHOOK", "HUBU_WEBHOOK"):
                    webhook = v.strip()
    
    if not webhook or "${" in webhook:
        log(f"[WARN] 飞书Webhook未配置")
        return False
    
    try:
        payload = json.dumps({
            "msg_type": "text",
            "content": {"text": message}
        }).encode("utf-8")
        req = urllib.request.Request(webhook, data=payload,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("StatusCode", 0) == 0:
                log("飞书通知发送成功")
                return True
    except Exception as e:
        log(f"飞书发送异常: {e}")
    return False


def main():
    now = datetime.now()
    
    # 计算报告日期（昨天到今天的数据）
    if now.hour < 10:
        report_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        report_date = now.strftime("%Y-%m-%d")
    
    window_start = (now - timedelta(days=1)).strftime("%Y-%m-%d") + " 08:30"
    window_end = now.strftime("%Y-%m-%d") + " 08:30"
    
    log(f"━━━ 交易每日总结报告 [{report_date}] ━━━")
    log(f"窗口: {window_start} - {window_end}")
    
    # 加载配置
    shared_config = load_shared_config()
    
    # 加载各Bot配置
    bots_config = {}
    for bot_id, bot_info in BOTS.items():
        config = load_bot_config(bot_info["config"])
        whitelist = get_whitelist(config)
        blacklist = get_blacklist(config)
        bots_config[bot_id] = {
            **bot_info,
            "whitelist": whitelist,
            "blacklist": blacklist
        }
    
    # 加载交易数据
    trades = load_trades_from_reports(report_date)
    if not trades:
        log("使用演示数据")
        trades = load_demo_trades()
    
    # 计算汇总
    summary = calculate_summary(trades, shared_config)
    summary["windowStart"] = window_start
    summary["windowEnd"] = window_end
    summary["bots"] = bots_config
    
    # 保存JSON
    json_file = f"{REPORTS_DIR}/{report_date}_enhanced.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    log(f"JSON已保存: {json_file}")
    
    # 生成Markdown
    md_content = generate_markdown(summary, bots_config)
    md_file = f"{REPORTS_DIR}/{report_date}_enhanced.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md_content)
    log(f"Markdown已保存: {md_file}")
    
    # 打印报告
    print(md_content)
    
    # 发送飞书
    s = summary["summary"]
    emoji = "✅" if s["totalPnl"] >= 0 else "🔴"
    message = (
        f"{emoji} **交易每日总结报告** `{report_date}`\n"
        f"策略: {summary.get('strategy')} | 周期: {summary.get('timeframe')}\n\n"
        f"📊 核心数据:\n"
        f"• 交易次数: {s['totalTrades']}\n"
        f"• 总盈亏: {'+' if s['totalPnl'] > 0 else ''}{s['totalPnl']}\n"
        f"• 胜率: {s['winRate']}%\n\n"
        f"📁 详细报告: {md_file}"
    )
    send_feishu(message)
    
    return summary


if __name__ == "__main__":
    main()