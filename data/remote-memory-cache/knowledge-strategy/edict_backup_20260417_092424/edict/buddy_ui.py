#!/usr/bin/env python3
import subprocess, json, os, sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

PORT = 7897
BUDDY = "/Users/luxiangnan/.openclaw/workspace-main/scripts/buddy_system.py"
DATA = "/Users/luxiangnan/.openclaw/workspace-main/memory/buddy.json"

STAR_MAP = {
    "common": "★", "uncommon": "☆☆", "rare": "☆☆☆",
    "epic": "☆☆☆☆", "legendary": "☆☆☆☆☆"
}

def interact(action):
    try:
        r = subprocess.run(["python3", BUDDY, action], capture_output=True, text=True, timeout=10)
        return r.stdout
    except: return ""

def load():
    if Path(DATA).exists(): return json.loads(open(DATA).read())
    return None

class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass
    def do_GET(self):
        try:
            p = urllib.parse.urlparse(self.path)
            path = p.path
            q = urllib.parse.parse_qs(p.query)
            if path in ("/", "/buddy"): self.send_html()
            elif path == "/data": self.send_json(self.get_data())
            elif path == "/a": self.handle_action(q.get("c", [""])[0])
            else: self.send_error(404)
        except: pass
    def send_html(self):
        d = self.get_data()
        html = HTML_TEMPLATE.format(**d)
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))
    def send_json(self, d):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(d).encode("utf-8"))
    def handle_action(self, action):
        out = interact(action)
        emojis = ["💪", "💬", "🍖", "🎾", "💤", "🐣", "🎉", "✨"]
        msg = ""
        for line in out.split("
"):
            line = line.strip()
            for e in emojis:
                if e in line: msg = line; break
            if msg: break
        if not msg:
            lines = [l for l in out.strip().split("
") if l.strip()]
            msg = lines[-1] if lines else "完成"
        d = {"msg": msg}
        if "🐣" in out: d["reload"] = True; d.update(self.get_data())
        self.send_json(d)
    def get_data(self):
        buddy = load()
        if not buddy:
            return {"name": "无伙伴", "level": 1, "exp": 0, "max_exp": 100, "exp_pct": 0, "rarity": "common", "stars": "★", "ascii": "请刷新...", "debug": 0, "patience": 0, "chaos": 0, "wisdom": 0, "snark": 0, "personality": ""}
        out = interact("")
        lines = [l for l in out.split("
") if l.strip()]
        asc_lines = []
        for l in lines:
            if any(l.startswith(e) for e in ["🔵", "⚪", "🟢", "🔵", "🟣", "🟡"]) or (l.startswith("  ") and len(asc_lines) < 6): asc_lines.append(l)
            if len(asc_lines) >= 5: break
        asc = chr(10).join(asc_lines) if asc_lines else out[:200]
        name = buddy.get("name", "?")
        level = buddy.get("level", 1)
        exp = buddy.get("exp", 0)
        max_exp = level * 100
        exp_pct = min(100, (exp / max_exp) * 100) if max_exp else 0
        stats = buddy.get("stats", {})
        rar = buddy.get("rarity", "common")
        return {"name": name, "level": level, "exp": exp, "max_exp": max_exp, "exp_pct": exp_pct, "rarity": rar, "stars": STAR_MAP.get(rar, "★"), "ascii": asc, "debug": min(100, stats.get("DEBUGGING", 0)), "patience": min(100, stats.get("PATIENCE", 0)), "chaos": min(100, stats.get("CHAOS", 0)), "wisdom": min(100, stats.get("WISDOM", 0)), "snark": min(100, stats.get("SNARK", 0)), "personality": buddy.get("personality", "")[:50]}

HTML_TEMPLATE = open("/tmp/buddy_html.txt").read()

if __name__ == "__main__":
    os.chdir(os.path.dirname(__file__) or ".")
    s = HTTPServer(("0.0.0.0", PORT), H)
    print("Buddy UI: http://localhost:" + str(PORT) + "/buddy", flush=True)
    s.serve_forever()