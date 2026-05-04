#!/usr/bin/env python3
"""
兵部监控台 API 服务器 - 增强版
端口: 7892
提供 bingbu unified + pareto + officials + 舆情 + 干预数据 + 实时持仓
"""

import json
import pathlib
import sys
import requests
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

BINGBU_BASE = pathlib.Path.home() / '.openclaw/workspace-bingbu/data'
BINGBU_REPORTS = pathlib.Path.home() / '.openclaw/workspace-bingbu/data/reports'
EDICT_DATA = pathlib.Path("/Users/luxiangnan/edict/data")
HOME = pathlib.Path.home()

# 舆情和干预数据文件
SENTIMENT_FILE = HOME / ".sentiment_latest.json"
INTERVENTION_FILE = EDICT_DATA / "bingbu_intervention.json"
FREEZE_FILE = EDICT_DATA / "bingbu_freeze.json"
INJECT_FILE = EDICT_DATA / "bingbu_sentiment_inject.json"

# FreqTrade 机器人配置（全部使用 Basic Auth）
import base64

def _basic_auth(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"

FREQTRADE_CONFIGS = {
    9090: {
        "host": "http://127.0.0.1:9090",
        "auth": _basic_auth("freqtrade", "freqtrade"),
        "label": "Gate-17656685222",
        "exchange": "Gate.io",
    },
    9091: {
        "host": "http://127.0.0.1:9091",
        "auth": _basic_auth("freqtrade", "freqtrade"),
        "label": "Gate-85363904550",
        "exchange": "Gate.io",
    },
    9092: {
        "host": "http://127.0.0.1:9092",
        "auth": _basic_auth("freqtrade", "freqtrade"),
        "label": "Gate-15637798222",
        "exchange": "Gate.io",
    },
    9093: {
        "host": "http://127.0.0.1:9093",
        "auth": _basic_auth("admin", "Xy@06130822"),
        "label": "OKX-15637798222",
        "exchange": "OKX",
    },
    9094: {
        "host": "http://127.0.0.1:9094",
        "auth": _basic_auth("admin", "Xy@06130822"),
        "label": "OKX-BOT85363904550",
        "exchange": "OKX",
    },
    9095: {
        "host": "http://127.0.0.1:9095",
        "auth": _basic_auth("admin", "Xy@06130822"),
        "label": "OKX-BOTa44056283",
        "exchange": "OKX",
    },
    9096: {
        "host": "http://127.0.0.1:9096",
        "auth": _basic_auth("admin", "Xy@06130822"),
        "label": "OKX-BHB16638759999",
        "exchange": "OKX",
    },
    9097: {
        "host": "http://127.0.0.1:9097",
        "auth": _basic_auth("admin", "Xy@06130822"),
        "label": "OKX-17656685222",
        "exchange": "OKX",
    },
}


def fetch_positions_from_bots() -> list:
    """从所有机器人获取实时持仓"""
    all_positions = []

    for port, cfg in FREQTRADE_CONFIGS.items():
        try:
            resp = requests.get(
                f"{cfg['host']}/api/v1/status",
                headers={"Authorization": cfg["auth"]},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                positions = data if isinstance(data, list) else data.get("result", [])
                for pos in positions:
                    if pos.get("is_open"):
                        all_positions.append({
                            "bot": cfg["label"],
                            "port": port,
                            "exchange": cfg["exchange"],
                            "pair": pos.get("pair", "").replace(":USDT", ""),
                            "side": "LONG" if not pos.get("is_short") else "SHORT",
                            "amount": round(float(pos.get("amount") or 0), 4),
                            "entry_price": round(float(pos.get("open_rate") or 0), 2),
                            "current_price": round(float(pos.get("current_rate") or 0), 2),
                            "unrealized_pnl": round(float(pos.get("profit_abs") or 0), 2),
                            "liquidation_price": round(float(pos.get("liquidation_price") or 0), 2),
                            "leverage": pos.get("leverage", 1),
                            "is_open": pos.get("is_open", True),
                            "profit_pct": round(float(pos.get("profit_pct") or 0), 2),
                        })
        except Exception:
            pass  # 单个机器人失败不影响整体

    return all_positions


def read_json(path, default=None):
    """安全读取JSON文件"""
    try:
        if path and path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    except Exception as e:
        print(f"读取失败 {path}: {e}")
    return default if default is not None else {}


class Handler(BaseHTTPRequestHandler):
    MIME = {
        '.html': 'text/html; charset=utf-8',
        '.json': 'application/json; charset=utf-8',
        '.js': 'application/javascript',
        '.css': 'text/css',
    }

    def log_message(self, fmt, *args):
        pass  # silence

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path).path.rstrip('/')
        
        # 根路径 - 返回HTML
        if p in ('', '/'):
            self.send_file(pathlib.Path(__file__).parent / '兵部监控台.html')
        
        # === 原有API ===
        elif p == '/api/unified':
            self.send_json(read_json(BINGBU_REPORTS / 'bingbu_unified_status.json', {}))
        elif p == '/api/pareto':
            self.send_json(read_json(BINGBU_REPORTS / 'pareto_summary.json', {}))
        elif p == '/api/officials':
            self.send_json(read_json(BINGBU_BASE / 'officials_stats.json', {}))
        elif p == '/api/live':
            self.send_json(read_json(BINGBU_BASE / 'live_status.json', {}))
        
        # === 新增: 舆情相关API ===
        elif p == '/api/sentiment':
            # 天福舆情系统输出
            self.send_json(read_json(SENTIMENT_FILE, {
                "sentiment_direction": "NEUTRAL",
                "sentiment_confidence": 0,
                "sentiment_urgency": 0,
                "sentiment_signal": "无数据",
                "recommended_action": "等待",
                "black_swan_alert": False,
                "fear_greed_value": 50,
                "fetch_time": datetime.now().isoformat()
            }))
        
        elif p == '/api/intervention':
            # 当前干预状态
            interventions = read_json(INTERVENTION_FILE, [])
            latest = interventions[0] if interventions else None
            
            freeze_status = read_json(FREEZE_FILE, {"frozen": False})
            inject_status = read_json(INJECT_FILE, None)
            
            self.send_json({
                "latest": latest,
                "freeze": freeze_status.get("frozen", False),
                "inject": inject_status,
                "intervention_count": len(interventions)
            })
        
        elif p == '/api/intervention_history':
            # 干预历史记录
            query = parse_qs(urlparse(self.path).query)
            limit = int(query.get('limit', [20])[0])
            interventions = read_json(INTERVENTION_FILE, [])
            self.send_json(interventions[:limit])
        
        elif p == '/api/intervention_log':
            # 干预日志
            log_file = EDICT_DATA / "bingbu_intervention.log"
            if log_file.exists():
                content = log_file.read_text(encoding='utf-8')
                lines = content.strip().split('\n')[-50:]  # 最近50条
                self.send_json({"lines": lines})
            else:
                self.send_json({"lines": []})

        elif p == '/api/positions':
            # 实时持仓（从所有机器人获取）
            positions = fetch_positions_from_bots()
            total_pnl = sum(p["unrealized_pnl"] for p in positions)
            self.send_json({
                "positions": positions,
                "count": len(positions),
                "total_pnl": round(total_pnl, 2),
                "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
        
        # === 日常报告API ===
        elif p.startswith('/api/daily/'):
            parts = p.replace('/api/daily/', '').split('/')
            if len(parts) >= 2:
                date_str = parts[0]
                report_file = parts[1]
                datedir = f'{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}'
                full_path = BINGBU_REPORTS / 'daily' / datedir / f'{report_file}.json'
                self.send_json(read_json(full_path, {}))
            else:
                self.send_json({})
        
        # === 静态文件 ===
        else:
            fp = pathlib.Path(__file__).parent / p.lstrip('/')
            if fp.is_file():
                self.send_file(fp)
            else:
                self.send_response(404)
                self.end_headers()

    def send_file(self, path):
        if not path.exists():
            self.send_response(404)
            self.end_headers()
            return
        body = path.read_bytes()
        ext = path.suffix
        mime = self.MIME.get(ext, 'application/octet-stream')
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 7892
    print(f'兵部监控台 API 服务器启动: http://localhost:{port}')
    print(f'API列表:')
    print(f'  /api/sentiment - 舆情信号')
    print(f'  /api/intervention - 干预状态')
    print(f'  /api/intervention_history - 干预历史')
    print(f'  /api/intervention_log - 干预日志')
    print(f'  /api/positions - 实时持仓（全部机器人）')
    server = HTTPServer(('0.0.0.0', port), Handler)
    print(f'兵部监控台API启动 → http://0.0.0.0:{port}（远程可访问）')
    server.serve_forever()
