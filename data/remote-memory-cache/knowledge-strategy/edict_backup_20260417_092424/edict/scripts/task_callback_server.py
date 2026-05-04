#!/usr/bin/env python3
"""尚书省任务回调处理服务器"""
import json, urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

SHANGSHU = "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0"
TASKS_FILE = "/Users/luxiangnan/edict/data/tasks_source.json"
SERVER = "http://127.0.0.1:7891"  # 尚书省dashboard

def load_tasks():
    try:
        with open(TASKS_FILE) as f:
            return json.load(f)
    except: return []

def save_tasks(t):
    with open(TASKS_FILE, 'w') as f:
        json.dump(t, f, f, indent=2)

def update(task_id, action, remark=""):
    tasks = load_tasks()
    action_map = {"approve": "✅ 已批准", "reject": "❌ 已拒绝", "modify": "📝 待修改"}
    for task in tasks:
        if task.get('id') == task_id:
            task['state'] = action
            task['now'] = action_map.get(action, action)
            task['block'] = f"{action} {remark}"
            save_tasks(tasks)
            return True
    return False

def notify(task_id, action, remark=""):
    """通知尚书省"""
    action_map = {"approve": "✅ 批准", "reject": "❌ 拒绝", "modify": "📝 打回修改"}
    msg = f"🎯 **任务处理通知**\n\n🆔 任务: `{task_id}`\n操作: **{action_map.get(action, action)}**"
    if remark:
        msg += f"\n📝 意见: {remark}"
    try:
        data = json.dumps({"msg_type": "text", "content": {"text": msg}}).encode()
        urllib.request.urlopen(urllib.request.Request(SHANGSHU, data=data, headers={"Content-Type": "application/json"}), timeout=5)
    except: pass

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        p = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        task_id = p.get('id', [''])[0]
        action = p.get('action', [''])[0]
        remark = p.get('remark', [''])[0]
        
        if task_id and action:
            update(task_id, action, remark)
            notify(task_id, action, remark)
            html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>完成</title></head><body style="font-family:sans-serif;text-align:center;padding:50px;background:#f0f9ff;min-height:100vh;display:flex;align-items:center;justify-content:center;">
<div style="background:white;border-radius:20px;padding:40px;box-shadow:0 10px 40px rgba(0,0,0,0.1);max-width:500px;">
<h1 style="font-size:64px;margin:0;">✅</h1>
<h2 style="color:#333;margin:20px 0;">任务 {task_id}</h2>
<p style="font-size:24px;color:#666;">已{action_map.get(action, action)}</p>
<p style="color:#999;">通知已发送到尚书省群</p>
<a href="/" style="color:#2196F3;text-decoration:none;margin-top:20px;display:inline-block;">← 返回</a></div></body></html>"""
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        else:
            tasks = load_tasks()
            html = '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>尚书省任务</title></head><body style="font-family:sans-serif;max-width:900px;margin:50px auto;padding:20px;"><h1>📋 尚书省任务处理中心</h1><table border="1" cellpadding="10" style="width:100%;border-collapse:collapse;"><tr style="background:#f5f5f5;"><th>ID</th><th>标题</th><th>状态</th><th>操作</th></tr>'
            for t in tasks[:20]:
                tid = t.get('id','')
                title = t.get('title','')[:40]
                now = t.get('now','')
                html += f'<tr><td>{tid}</td><td>{title}</td><td>{now}</td><td><a href="/?action=approve&id={tid}">✅批准</a> <a href="/?action=reject&id={tid}">❌拒绝</a></td></tr>'
            html += '</table></body></html>'
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))

HTTPServer(('', 7892), Handler).serve_forever()
