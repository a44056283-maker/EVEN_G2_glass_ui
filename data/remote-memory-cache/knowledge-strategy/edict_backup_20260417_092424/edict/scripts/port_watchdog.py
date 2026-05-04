#!/usr/bin/env python3
"""服务端口扫描看门狗"""
import subprocess
import json
from datetime import datetime

PORTS = [9090, 9091, 9092, 9093, 9094, 9095, 9096, 9097, 9099]
FAILED = []

for port in PORTS:
    r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', f'http://localhost:{port}/api/v1/ping'],
                      capture_output=True, timeout=5)
    if r.stdout.decode() != '200':
        FAILED.append(port)

if FAILED:
    print(f"[PORT_WATCHDOG] 宕机端口: {FAILED}")
    # 可以触发重启
    # subprocess.run(['openclaw', 'cron', 'trigger', 'port_restart'])
else:
    print(f"[PORT_WATCHDOG] 全部正常")
