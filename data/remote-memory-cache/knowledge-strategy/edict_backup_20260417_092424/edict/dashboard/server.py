#!/usr/bin/env python3
"""
三省六部 · 看板本地 API 服务器
Port: 7891 (可通过 --port 修改)

Endpoints:
  GET  /                       → dashboard.html
  GET  /api/live-status        → data/live_status.json
  GET  /api/agent-config       → data/agent_config.json
  POST /api/set-model          → {agentId, model}
  GET  /api/model-change-log   → data/model_change_log.json
  GET  /api/last-result        → data/last_model_change_result.json
"""
import json, pathlib, subprocess, sys, threading, argparse, datetime, logging, re, os, base64, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen
import requests

# ── 兵部外网访问地址（cloudflared 隧道，动态下发）───────────
BINGBU_PUBLIC_BASE = os.environ.get(
    "BINGBU_PUBLIC_BASE",
    ""   # 启动时通过 --public-url 参数设置
)

# 引入文件锁工具，确保与其他脚本并发安全
scripts_dir = str(pathlib.Path(__file__).parent.parent / 'scripts')
dashboard_dir = str(pathlib.Path(__file__).parent)
sys.path.insert(0, dashboard_dir)  # 先加当前目录，找 court_discuss 等本地模块
sys.path.append(scripts_dir)   # append 避免抢占 dashboard 目录
from file_lock import atomic_json_read, atomic_json_write, atomic_json_update
from utils import validate_url, read_json, now_iso
from court_discuss import (
    create_session as cd_create, advance_discussion as cd_advance,
    get_session as cd_get, conclude_session as cd_conclude,
    list_sessions as cd_list, destroy_session as cd_destroy,
    get_fate_event as cd_fate, OFFICIAL_PROFILES as CD_PROFILES,
)

# ── 兵部干预系统 ──────────────────────────────────────────────
from intervention_store import add_intervention as bingbu_add_intervention, load_interventions as bingbu_load_interventions

# FreqTrade 机器人配置
def _basic_auth(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"

BINGBU_FREQTRADE = {
    9090: {"host": "http://127.0.0.1:9090", "auth": _basic_auth("freqtrade", "freqtrade"), "label": "Gate-17656685222", "exchange": "Gate.io"},
    9091: {"host": "http://127.0.0.1:9091", "auth": _basic_auth("freqtrade", "freqtrade"), "label": "Gate-85363904550", "exchange": "Gate.io"},
    9092: {"host": "http://127.0.0.1:9092", "auth": _basic_auth("freqtrade", "freqtrade"), "label": "Gate-15637798222", "exchange": "Gate.io"},
    9093: {"host": "http://127.0.0.1:9093", "auth": _basic_auth("admin", "Xy@06130822"), "label": "OKX-15637798222", "exchange": "OKX"},
    9094: {"host": "http://127.0.0.1:9094", "auth": _basic_auth("admin", "Xy@06130822"), "label": "OKX-BOT85363904550", "exchange": "OKX"},
    9095: {"host": "http://127.0.0.1:9095", "auth": _basic_auth("admin", "Xy@06130822"), "label": "OKX-BOTa44056283", "exchange": "OKX"},
    9096: {"host": "http://127.0.0.1:9096", "auth": _basic_auth("admin", "Xy@06130822"), "label": "OKX-BHB16638759999", "exchange": "OKX"},
    9097: {"host": "http://127.0.0.1:9097", "auth": _basic_auth("admin", "Xy@06130822"), "label": "OKX-17656685222", "exchange": "OKX"},
}
BINGBU_SENTIMENT_FILE = pathlib.Path.home() / ".sentiment_latest.json"
BINGBU_EDICT_DATA = pathlib.Path.home() / "edict/data"
BINGBU_INTERVENTION_FILE = BINGBU_EDICT_DATA / "bingbu_intervention.json"
BINGBU_FREEZE_FILE = BINGBU_EDICT_DATA / "bingbu_freeze.json"
BINGBU_INJECT_FILE = BINGBU_EDICT_DATA / "bingbu_sentiment_inject.json"


def _bingbu_fetch_positions() -> list:
    """从所有机器人并发获取实时持仓

    FreqTrade /api/v1/status 返回的 amount 字段：
    - 多头：正数（当前剩余持仓量，已含部分平仓）
    - 空头：负数（绝对值=当前剩余持仓量）
    因此必须用 abs() 取正值。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _fetch_one(port, cfg):
        try:
            resp = requests.get(
                f"{cfg['host']}/api/v1/status",
                headers={"Authorization": cfg["auth"]},
                timeout=3,
            )
            if resp.status_code != 200:
                return []
            positions = []
            for pos in resp.json():
                if not pos.get("is_open"):
                    continue
                # amount：多头为正，空头为负；abs()后得到实际持仓数量
                raw_amount = float(pos.get("amount") or 0)
                remaining_amount = round(abs(raw_amount), 4)
                positions.append({
                    "bot": cfg["label"], "port": port, "exchange": cfg["exchange"],
                    "pair": pos.get("pair", "").replace(":USDT", ""),
                    "side": "LONG" if not pos.get("is_short") else "SHORT",
                    "amount": remaining_amount,
                    "original_amount": round(abs(raw_amount), 4),
                    "entry_price": round(float(pos.get("open_rate") or 0), 2),
                    "current_price": round(float(pos.get("current_rate") or 0), 2),
                    "unrealized_pnl": round(float(pos.get("profit_abs") or 0), 2),
                    "liquidation_price": round(float(pos.get("liquidation_price") or 0), 2),
                    "leverage": pos.get("leverage", 1),
                    "is_open": True,
                    "profit_pct": round(float(pos.get("profit_pct") or 0), 2),
                    "trade_id": str(pos.get("trade_id", "")),
                })
            return positions
        except Exception:
            return []

    all_positions = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_one, port, cfg): port for port, cfg in BINGBU_FREQTRADE.items()}
        for fut in as_completed(futures):
            all_positions.extend(fut.result())
    return all_positions


def _bingbu_read_json(path, default=None):
    try:
        if path and path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        pass
    return default if default is not None else {}

log = logging.getLogger('server')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s', datefmt='%H:%M:%S')

OCLAW_HOME = pathlib.Path.home() / '.openclaw'
MAX_REQUEST_BODY = 1 * 1024 * 1024  # 1 MB
ALLOWED_ORIGIN = None  # Set via --cors; None means restrict to localhost
_DEFAULT_ORIGINS = {
    'http://127.0.0.1:7891', 'http://localhost:7891',
    'http://127.0.0.1:5173', 'http://localhost:5173',  # Vite dev server
}
_SAFE_NAME_RE = re.compile(r'^[a-zA-Z0-9_\-\u4e00-\u9fff]+$')

BASE = pathlib.Path(__file__).parent
DIST = BASE / 'dist'          # React 构建产物 (npm run build)
DATA = BASE.parent / "data"
SCRIPTS = BASE.parent / 'scripts'

# 静态资源 MIME 类型
_MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js':   'application/javascript; charset=utf-8',
    '.css':  'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png':  'image/png',
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif':  'image/gif',
    '.svg':  'image/svg+xml',
    '.ico':  'image/x-icon',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf':  'font/ttf',
    '.map':  'application/json',
}


def cors_headers(h):
    req_origin = h.headers.get('Origin', '')
    if ALLOWED_ORIGIN:
        origin = ALLOWED_ORIGIN
    elif req_origin in _DEFAULT_ORIGINS:
        origin = req_origin
    else:
        origin = 'http://127.0.0.1:7891'
    h.send_header('Access-Control-Allow-Origin', origin)
    h.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    h.send_header('Access-Control-Allow-Headers', 'Content-Type')


def load_tasks():
    return atomic_json_read(DATA / 'tasks_source.json', [])


def save_tasks(tasks):
    atomic_json_write(DATA / 'tasks_source.json', tasks)
    # Trigger refresh (异步，不阻塞，避免僵尸进程)
    def _refresh():
        try:
            subprocess.run(['python3', str(SCRIPTS / 'refresh_live_data.py')], timeout=30)
        except Exception as e:
            log.warning(f'refresh_live_data.py 触发失败: {e}')
    threading.Thread(target=_refresh, daemon=True).start()


def handle_task_action(task_id, action, reason):
    """Stop/cancel/resume a task from the dashboard."""
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}

    old_state = task.get('state', '')
    _ensure_scheduler(task)
    _scheduler_snapshot(task, f'task-action-before-{action}')

    if action == 'stop':
        task['state'] = 'Blocked'
        task['block'] = reason or '皇上叫停'
        task['now'] = f'⏸️ 已暂停：{reason}'
    elif action == 'cancel':
        task['state'] = 'Cancelled'
        task['block'] = reason or '皇上取消'
        task['now'] = f'🚫 已取消：{reason}'
    elif action == 'resume':
        # Resume to previous active state or Doing
        task['state'] = task.get('_prev_state', 'Doing')
        task['block'] = '无'
        task['now'] = f'▶️ 已恢复执行'

    if action in ('stop', 'cancel'):
        task['_prev_state'] = old_state  # Save for resume

    task.setdefault('flow_log', []).append({
        'at': now_iso(),
        'from': '皇上',
        'to': task.get('org', ''),
        'remark': f'{"⏸️ 叫停" if action == "stop" else "🚫 取消" if action == "cancel" else "▶️ 恢复"}：{reason}'
    })

    if action == 'resume':
        _scheduler_mark_progress(task, f'恢复到 {task.get("state", "Doing")}')
    else:
        _scheduler_add_flow(task, f'皇上{action}：{reason or "无"}')

    task['updatedAt'] = now_iso()

    save_tasks(tasks)
    if action == 'resume' and task.get('state') not in _TERMINAL_STATES:
        dispatch_for_state(task_id, task, task.get('state'), trigger='resume')
    label = {'stop': '已叫停', 'cancel': '已取消', 'resume': '已恢复'}[action]
    return {'ok': True, 'message': f'{task_id} {label}'}


def handle_archive_task(task_id, archived, archive_all_done=False):
    """Archive or unarchive a task, or batch-archive all Done/Cancelled tasks."""
    tasks = load_tasks()
    if archive_all_done:
        count = 0
        for t in tasks:
            if t.get('state') in ('Done', 'Cancelled') and not t.get('archived'):
                t['archived'] = True
                t['archivedAt'] = now_iso()
                count += 1
        save_tasks(tasks)
        return {'ok': True, 'message': f'{count} 道旨意已归档', 'count': count}
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}
    task['archived'] = archived
    if archived:
        task['archivedAt'] = now_iso()
    else:
        task.pop('archivedAt', None)
    task['updatedAt'] = now_iso()
    save_tasks(tasks)
    label = '已归档' if archived else '已取消归档'
    return {'ok': True, 'message': f'{task_id} {label}'}


def update_task_todos(task_id, todos):
    """Update the todos list for a task."""
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}

    task['todos'] = todos
    task['updatedAt'] = now_iso()
    save_tasks(tasks)
    return {'ok': True, 'message': f'{task_id} todos 已更新'}


def read_skill_content(agent_id, skill_name):
    """Read SKILL.md content for a specific skill."""
    # 输入校验：防止路径遍历
    if not _SAFE_NAME_RE.match(agent_id) or not _SAFE_NAME_RE.match(skill_name):
        return {'ok': False, 'error': '参数含非法字符'}
    cfg = read_json(DATA / 'agent_config.json', {})
    agents = cfg.get('agents', [])
    ag = next((a for a in agents if a.get('id') == agent_id), None)
    if not ag:
        return {'ok': False, 'error': f'Agent {agent_id} 不存在'}
    sk = next((s for s in ag.get('skills', []) if s.get('name') == skill_name), None)
    if not sk:
        return {'ok': False, 'error': f'技能 {skill_name} 不存在'}
    skill_path = pathlib.Path(sk.get('path', '')).resolve()
    # 路径遍历保护：确保路径在 OCLAW_HOME 或项目目录下
    allowed_roots = (OCLAW_HOME.resolve(), BASE.parent.resolve())
    if not any(str(skill_path).startswith(str(root)) for root in allowed_roots):
        return {'ok': False, 'error': '路径不在允许的目录范围内'}
    if not skill_path.exists():
        return {'ok': True, 'name': skill_name, 'agent': agent_id, 'content': '(SKILL.md 文件不存在)', 'path': str(skill_path)}
    try:
        content = skill_path.read_text()
        return {'ok': True, 'name': skill_name, 'agent': agent_id, 'content': content, 'path': str(skill_path)}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def add_skill_to_agent(agent_id, skill_name, description, trigger=''):
    """Create a new skill for an agent with a standardised SKILL.md template."""
    if not _SAFE_NAME_RE.match(skill_name):
        return {'ok': False, 'error': f'skill_name 含非法字符: {skill_name}'}
    if not _SAFE_NAME_RE.match(agent_id):
        return {'ok': False, 'error': f'agentId 含非法字符: {agent_id}'}
    workspace = OCLAW_HOME / f'workspace-{agent_id}' / 'skills' / skill_name
    workspace.mkdir(parents=True, exist_ok=True)
    skill_md = workspace / 'SKILL.md'
    desc_line = description or skill_name
    trigger_section = f'\n## 触发条件\n{trigger}\n' if trigger else ''
    template = (f'---\n'
                f'name: {skill_name}\n'
                f'description: {desc_line}\n'
                f'---\n\n'
                f'# {skill_name}\n\n'
                f'{desc_line}\n'
                f'{trigger_section}\n'
                f'## 输入\n\n'
                f'<!-- 说明此技能接收什么输入 -->\n\n'
                f'## 处理流程\n\n'
                f'1. 步骤一\n'
                f'2. 步骤二\n\n'
                f'## 输出规范\n\n'
                f'<!-- 说明产出物格式与交付要求 -->\n\n'
                f'## 注意事项\n\n'
                f'- (在此补充约束、限制或特殊规则)\n')
    skill_md.write_text(template)
    # Re-sync agent config
    try:
        subprocess.run(['python3', str(SCRIPTS / 'sync_agent_config.py')], timeout=10)
    except Exception:
        pass
    return {'ok': True, 'message': f'技能 {skill_name} 已添加到 {agent_id}', 'path': str(skill_md)}


def add_remote_skill(agent_id, skill_name, source_url, description=''):
    """从远程 URL 或本地路径为 Agent 添加 skill SKILL.md 文件。
    
    支持的源：
    - HTTPS URLs: https://raw.githubusercontent.com/...
    - 本地路径: /path/to/SKILL.md 或 file:///path/to/SKILL.md
    """
    # 输入校验
    if not _SAFE_NAME_RE.match(agent_id):
        return {'ok': False, 'error': f'agentId 含非法字符: {agent_id}'}
    if not _SAFE_NAME_RE.match(skill_name):
        return {'ok': False, 'error': f'skillName 含非法字符: {skill_name}'}
    if not source_url or not isinstance(source_url, str):
        return {'ok': False, 'error': 'sourceUrl 必须是有效的字符串'}
    
    source_url = source_url.strip()
    
    # 检查 Agent 是否存在
    cfg = read_json(DATA / 'agent_config.json', {})
    agents = cfg.get('agents', [])
    if not any(a.get('id') == agent_id for a in agents):
        return {'ok': False, 'error': f'Agent {agent_id} 不存在'}
    
    # 下载或读取文件内容
    try:
        if source_url.startswith('http://') or source_url.startswith('https://'):
            # HTTPS URL 校验
            if not validate_url(source_url, allowed_schemes=('https',)):
                return {'ok': False, 'error': 'URL 无效或不安全（仅支持 HTTPS）'}
            
            # 从 URL 下载，带超时保护
            req = Request(source_url, headers={'User-Agent': 'OpenClaw-SkillManager/1.0'})
            try:
                resp = urlopen(req, timeout=10)
                content = resp.read(10 * 1024 * 1024).decode('utf-8')  # 最多 10MB
                if len(content) > 10 * 1024 * 1024:
                    return {'ok': False, 'error': '文件过大（最大 10MB）'}
            except Exception as e:
                return {'ok': False, 'error': f'URL 无法访问: {str(e)[:100]}'}
        
        elif source_url.startswith('file://'):
            # file:// URL 格式
            local_path = pathlib.Path(source_url[7:])
            if not local_path.exists():
                return {'ok': False, 'error': f'本地文件不存在: {local_path}'}
            content = local_path.read_text()
        
        elif source_url.startswith('/') or source_url.startswith('.'):
            # 本地绝对或相对路径
            local_path = pathlib.Path(source_url).resolve()
            if not local_path.exists():
                return {'ok': False, 'error': f'本地文件不存在: {local_path}'}
            # 路径遍历防护
            allowed_roots = (OCLAW_HOME.resolve(), BASE.parent.resolve())
            if not any(str(local_path).startswith(str(root)) for root in allowed_roots):
                return {'ok': False, 'error': '路径不在允许的目录范围内'}
            content = local_path.read_text()
        
        else:
            return {'ok': False, 'error': '不支持的 URL 格式（仅支持 https://, file://, 或本地路径）'}
    except Exception as e:
        return {'ok': False, 'error': f'文件读取失败: {str(e)[:100]}'}
    
    # 基础验证：检查是否为 Markdown 且包含 YAML frontmatter
    if not content.startswith('---'):
        return {'ok': False, 'error': '文件格式无效（缺少 YAML frontmatter）'}
    
    # 验证 frontmatter 结构（先做字符串检查，再尝试 YAML 解析）
    parts = content.split('---', 2)
    if len(parts) < 3:
        return {'ok': False, 'error': '文件格式无效（YAML frontmatter 结构错误）'}
    if 'name:' not in content[:500]:
        return {'ok': False, 'error': '文件格式无效：frontmatter 缺少 name 字段'}
    try:
        import yaml
        yaml.safe_load(parts[1])  # 严格校验 YAML 语法
    except ImportError:
        pass  # PyYAML 未安装，跳过严格验证，字符串检查已通过
    except Exception as e:
        return {'ok': False, 'error': f'YAML 格式无效: {str(e)[:100]}'}
    
    # 创建本地目录
    workspace = OCLAW_HOME / f'workspace-{agent_id}' / 'skills' / skill_name
    workspace.mkdir(parents=True, exist_ok=True)
    skill_md = workspace / 'SKILL.md'
    
    # 写入 SKILL.md
    skill_md.write_text(content)
    
    # 保存源信息到 .source.json
    source_info = {
        'skillName': skill_name,
        'sourceUrl': source_url,
        'description': description,
        'addedAt': now_iso(),
        'lastUpdated': now_iso(),
        'checksum': _compute_checksum(content),
        'status': 'valid',
    }
    source_json = workspace / '.source.json'
    source_json.write_text(json.dumps(source_info, ensure_ascii=False, indent=2))
    
    # Re-sync agent config
    try:
        subprocess.run(['python3', str(SCRIPTS / 'sync_agent_config.py')], timeout=10)
    except Exception:
        pass
    
    return {
        'ok': True,
        'message': f'技能 {skill_name} 已从远程源添加到 {agent_id}',
        'skillName': skill_name,
        'agentId': agent_id,
        'source': source_url,
        'localPath': str(skill_md),
        'size': len(content),
        'addedAt': now_iso(),
    }


def get_remote_skills_list():
    """列表所有已添加的远程 skills 及其源信息"""
    remote_skills = []
    
    # 遍历所有 workspace
    for ws_dir in OCLAW_HOME.glob('workspace-*'):
        agent_id = ws_dir.name.replace('workspace-', '')
        skills_dir = ws_dir / 'skills'
        if not skills_dir.exists():
            continue
        
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_name = skill_dir.name
            source_json = skill_dir / '.source.json'
            skill_md = skill_dir / 'SKILL.md'
            
            if not source_json.exists():
                # 本地创建的 skill，跳过
                continue
            
            try:
                source_info = json.loads(source_json.read_text())
                # 检查 SKILL.md 是否存在
                status = 'valid' if skill_md.exists() else 'not-found'
                remote_skills.append({
                    'skillName': skill_name,
                    'agentId': agent_id,
                    'sourceUrl': source_info.get('sourceUrl', ''),
                    'description': source_info.get('description', ''),
                    'localPath': str(skill_md),
                    'addedAt': source_info.get('addedAt', ''),
                    'lastUpdated': source_info.get('lastUpdated', ''),
                    'status': status,
                })
            except Exception:
                pass
    
    return {
        'ok': True,
        'remoteSkills': remote_skills,
        'count': len(remote_skills),
        'listedAt': now_iso(),
    }


def update_remote_skill(agent_id, skill_name):
    """更新已添加的远程 skill 为最新版本（重新从源 URL 下载）"""
    if not _SAFE_NAME_RE.match(agent_id):
        return {'ok': False, 'error': f'agentId 含非法字符: {agent_id}'}
    if not _SAFE_NAME_RE.match(skill_name):
        return {'ok': False, 'error': f'skillName 含非法字符: {skill_name}'}
    
    workspace = OCLAW_HOME / f'workspace-{agent_id}' / 'skills' / skill_name
    source_json = workspace / '.source.json'
    skill_md = workspace / 'SKILL.md'
    
    if not source_json.exists():
        return {'ok': False, 'error': f'技能 {skill_name} 不是远程 skill（无 .source.json）'}
    
    try:
        source_info = json.loads(source_json.read_text())
        source_url = source_info.get('sourceUrl', '')
        if not source_url:
            return {'ok': False, 'error': '源 URL 不存在'}
        
        # 重新下载
        result = add_remote_skill(agent_id, skill_name, source_url, 
                                  source_info.get('description', ''))
        if result['ok']:
            result['message'] = f'技能已更新'
            source_info_updated = json.loads(source_json.read_text())
            result['newVersion'] = source_info_updated.get('checksum', 'unknown')
        return result
    except Exception as e:
        return {'ok': False, 'error': f'更新失败: {str(e)[:100]}'}


def remove_remote_skill(agent_id, skill_name):
    """移除已添加的远程 skill"""
    if not _SAFE_NAME_RE.match(agent_id):
        return {'ok': False, 'error': f'agentId 含非法字符: {agent_id}'}
    if not _SAFE_NAME_RE.match(skill_name):
        return {'ok': False, 'error': f'skillName 含非法字符: {skill_name}'}
    
    workspace = OCLAW_HOME / f'workspace-{agent_id}' / 'skills' / skill_name
    if not workspace.exists():
        return {'ok': False, 'error': f'技能不存在: {skill_name}'}


# 三省六部 子代理汇报
AGENT_META = {
    'shangshu':  {'dept': '尚书省',  'label': '📜 尚书省',  'icon': '📜'},
    'hubu':      {'dept': '户部',      'label': '💰 户部',      'icon': '💰'},
    'bingbu':    {'dept': '兵部',      'label': '⚔️ 兵部',      'icon': '⚔️'},
    'xingbu':    {'dept': '刑部',      'label': '⚖️ 刑部',      'icon': '⚖️'},
    'qintianjian': {'dept': '钦天监',  'label': '🔭 钦天监',  'icon': '🔭'},
    'gongbu':    {'dept': '工部',      'label': '🏗️ 工部',      'icon': '🏗️'},
    'tianlu':    {'dept': '中书省',    'label': '🦁 中书省',    'icon': '🦁'},
}


def get_agent_reports():
    """读取各子代理 workspace memory/tasks/ 下的汇报文件"""
    reports = []
    for agent_id, meta in AGENT_META.items():
        tasks_dir = OCLAW_HOME / f'workspace-{agent_id}' / 'memory' / 'tasks'
        if not tasks_dir.exists():
            continue
        for f in sorted(tasks_dir.glob('*.md'), key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
            content = f.read_text(encoding='utf-8', errors='ignore')
            # 提取第一行作为标题，其余作为摘要
            lines = content.strip().split('\n')
            title = lines[0].lstrip('#*\- ').strip() or f.name
            summary = '\n'.join(lines[1:]).strip()[:300]
            reports.append({
                'agent': agent_id,
                'dept': meta['dept'],
                'label': meta['label'],
                'icon': meta['icon'],
                'file': f.name,
                'title': title,
                'summary': summary,
                'mtime': datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
                'content': content.strip(),
            })
    # 按 mtime 倒序
    reports.sort(key=lambda x: x['mtime'], reverse=True)
    return reports


# ─────────────────────────────────────────────────────────────
# 子代理任务创建 API（供各省部子代理自动调用）
# POST /api/agent-task/create
# body: { title, dept, official, description, priority }
# ─────────────────────────────────────────────────────────────
def handle_agent_task_create(title, dept='尚书省', official='尚书令',
                              description='', priority='normal', source_agent=''):
    """子代理自动创建任务，写入旨意看板流水线。"""
    if not title or not title.strip():
        return {'ok': False, 'error': '任务标题不能为空'}
    title = title.strip()
    if len(title) < 4:
        return {'ok': False, 'error': f'标题过短（{len(title)}<4字）'}

    today = datetime.datetime.now().strftime('%Y%m%d')
    tasks = load_tasks()
    today_ids = [t['id'] for t in tasks if t.get('id', '').startswith(f'JJC-{today}-')]
    seq = 1
    if today_ids:
        nums = [int(tid.split('-')[-1]) for tid in today_ids if tid.split('-')[-1].isdigit()]
        seq = max(nums) + 1 if nums else 1
    task_id = f'JJC-{today}-{seq:03d}'

    now_str = now_iso()
    flow_log = [{
        'at': now_str,
        'from': source_agent or dept,
        'to': '尚书省',
        'remark': f'【{dept}自奏】：{title}'
    }]
    if description:
        flow_log.append({
            'at': now_str,
            'from': dept,
            'to': dept,
            'remark': f'任务描述：{description[:200]}'
        })

    new_task = {
        'id': task_id,
        'title': title,
        'official': official,
        'org': dept,
        'state': 'Doing',       # 子代理任务直接进执行阶段
        'now': f'【{dept}执行中】{title}',
        'eta': '-',
        'block': '无',
        'output': '',
        'ac': '',
        'priority': priority,
        'flow_log': flow_log,
        'updatedAt': now_str,
        'sourceAgent': source_agent,
        'description': description,
    }

    _ensure_scheduler(new_task)
    _scheduler_mark_progress(new_task, f'{dept}自奏任务')

    tasks.insert(0, new_task)
    save_tasks(tasks)

    log.info(f'子代理任务创建: {task_id} | {dept} | {title[:40]}')
    return {'ok': True, 'taskId': task_id, 'state': 'Doing', 'message': f'{dept}任务已创建并开始执行'}


# ─────────────────────────────────────────────────────────────
# 子代理任务更新 API
# POST /api/agent-task/update
# body: { task_id, state, output, now }
# ─────────────────────────────────────────────────────────────
def handle_agent_task_update(task_id, state=None, output='', now='', remark=''):
    """子代理更新任务状态（执行结果回写）。"""
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}
    if state:
        task['state'] = state
    if output:
        task['output'] = output
    if now:
        task['now'] = now
    if remark:
        task['flow_log'].append({
            'at': now_iso(),
            'from': task.get('org', ''),
            'to': '旨意看板',
            'remark': remark
        })
    task['updatedAt'] = now_iso()
    save_tasks(tasks)
    log.info(f'子代理任务更新: {task_id} -> {state} | {now}')
    return {'ok': True, 'taskId': task_id}


def _compute_checksum(content: str) -> str:
    """计算内容的简单校验和（SHA256 的前16字符）"""
    import hashlib
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def push_to_feishu():
    """Push morning brief link to Feishu via webhook."""
    cfg = read_json(DATA / 'morning_brief_config.json', {})
    webhook = cfg.get('feishu_webhook', '').strip()
    if not webhook:
        return
    if not validate_url(webhook, allowed_schemes=('https',), allowed_domains=('open.feishu.cn', 'open.larksuite.com')):
        log.warning(f'飞书 Webhook URL 不合法: {webhook}')
        return
    brief = read_json(DATA / 'morning_brief.json', {})
    date_str = brief.get('date', '')
    total = sum(len(v) for v in (brief.get('categories') or {}).values())
    if not total:
        return
    cat_lines = []
    for cat, items in (brief.get('categories') or {}).items():
        if items:
            cat_lines.append(f'  {cat}: {len(items)} 条')
    summary = '\n'.join(cat_lines)
    date_fmt = date_str[:4] + '年' + date_str[4:6] + '月' + date_str[6:] + '日' if len(date_str) == 8 else date_str
    payload = json.dumps({
        'msg_type': 'interactive',
        'card': {
            'header': {'title': {'tag': 'plain_text', 'content': f'📰 天下要闻 · {date_fmt}'}, 'template': 'blue'},
            'elements': [
                {'tag': 'div', 'text': {'tag': 'lark_md', 'content': f'共 **{total}** 条要闻已更新\n{summary}'}},
                {'tag': 'action', 'actions': [{'tag': 'button', 'text': {'tag': 'plain_text', 'content': '🔗 查看完整简报'}, 'url': BINGBU_PUBLIC_BASE, 'type': 'primary'}]},
                {'tag': 'note', 'elements': [{'tag': 'plain_text', 'content': f"采集于 {brief.get('generated_at', '')}"}]}
            ]
        }
    }).encode()
    try:
        req = Request(webhook, data=payload, headers={'Content-Type': 'application/json'})
        resp = urlopen(req, timeout=10)
        print(f'[飞书] 推送成功 ({resp.status})')
    except Exception as e:
        print(f'[飞书] 推送失败: {e}', file=sys.stderr)


# 旨意标题最低要求
_MIN_TITLE_LEN = 6
_JUNK_TITLES = {
    '?', '？', '好', '好的', '是', '否', '不', '不是', '对', '了解', '收到',
    '嗯', '哦', '知道了', '开启了么', '可以', '不行', '行', 'ok', 'yes', 'no',
    '你去开启', '测试', '试试', '看看',
}


def handle_create_task(title, org='中书省', official='中书令', priority='normal', template_id='', params=None, target_dept=''):
    """从看板创建新任务（圣旨模板下旨）。"""
    if not title or not title.strip():
        return {'ok': False, 'error': '任务标题不能为空'}
    title = title.strip()
    # 剥离 Conversation info 元数据
    title = re.split(r'\n*Conversation info\s*\(', title, maxsplit=1)[0].strip()
    title = re.split(r'\n*```', title, maxsplit=1)[0].strip()
    # 清理常见前缀: "传旨:" "下旨:" 等
    title = re.sub(r'^(传旨|下旨)[：:\uff1a]\s*', '', title)
    if len(title) > 100:
        title = title[:100] + '…'
    # 标题质量校验：防止闲聊被误建为旨意
    if len(title) < _MIN_TITLE_LEN:
        return {'ok': False, 'error': f'标题过短（{len(title)}<{_MIN_TITLE_LEN}字），不像是旨意'}
    if title.lower() in _JUNK_TITLES:
        return {'ok': False, 'error': f'「{title}」不是有效旨意，请输入具体工作指令'}
    # 生成 task id: JJC-YYYYMMDD-NNN
    today = datetime.datetime.now().strftime('%Y%m%d')
    tasks = load_tasks()
    today_ids = [t['id'] for t in tasks if t.get('id', '').startswith(f'JJC-{today}-')]
    seq = 1
    if today_ids:
        nums = [int(tid.split('-')[-1]) for tid in today_ids if tid.split('-')[-1].isdigit()]
        seq = max(nums) + 1 if nums else 1
    task_id = f'JJC-{today}-{seq:03d}'
    # 正确流程起点：皇上 -> 太子分拣
    # target_dept 记录模板建议的最终执行部门（仅供尚书省派发参考）
    initial_org = '太子'
    new_task = {
        'id': task_id,
        'title': title,
        'official': official,
        'org': initial_org,
        'state': 'Taizi',
        'now': '等待太子接旨分拣',
        'eta': '-',
        'block': '无',
        'output': '',
        'ac': '',
        'priority': priority,
        'templateId': template_id,
        'templateParams': params or {},
        'flow_log': [{
            'at': now_iso(),
            'from': '皇上',
            'to': initial_org,
            'remark': f'下旨：{title}'
        }],
        'updatedAt': now_iso(),
    }
    if target_dept:
        new_task['targetDept'] = target_dept

    _ensure_scheduler(new_task)
    _scheduler_snapshot(new_task, 'create-task-initial')
    _scheduler_mark_progress(new_task, '任务创建')

    tasks.insert(0, new_task)
    save_tasks(tasks)
    log.info(f'创建任务: {task_id} | {title[:40]}')

    dispatch_for_state(task_id, new_task, 'Taizi', trigger='imperial-edict')

    return {'ok': True, 'taskId': task_id, 'message': f'旨意 {task_id} 已下达，正在派发给太子'}


def handle_review_action(task_id, action, comment=''):
    """门下省御批：准奏/封驳。"""
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}
    if task.get('state') not in ('Review', 'Menxia'):
        return {'ok': False, 'error': f'任务 {task_id} 当前状态为 {task.get("state")}，无法御批'}

    _ensure_scheduler(task)
    _scheduler_snapshot(task, f'review-before-{action}')

    if action == 'approve':
        if task['state'] == 'Menxia':
            task['state'] = 'Assigned'
            task['now'] = '门下省准奏，移交尚书省派发'
            remark = f'✅ 准奏：{comment or "门下省审议通过"}'
            to_dept = '尚书省'
        else:  # Review
            task['state'] = 'Done'
            task['now'] = '御批通过，任务完成'
            remark = f'✅ 御批准奏：{comment or "审查通过"}'
            to_dept = '皇上'
    elif action == 'reject':
        round_num = (task.get('review_round') or 0) + 1
        task['review_round'] = round_num
        task['state'] = 'Zhongshu'
        task['now'] = f'封驳退回中书省修订（第{round_num}轮）'
        remark = f'🚫 封驳：{comment or "需要修改"}'
        to_dept = '中书省'
    elif action == 'modify':
        round_num = (task.get('review_round') or 0) + 1
        task['review_round'] = round_num
        task['state'] = 'Zhongshu'
        task['now'] = f'修改意见退回中书省修订（第{round_num}轮）'
        remark = f'📝 修改意见：{comment or "需要修改后重新提交"}'
        to_dept = '中书省'
    else:
        return {'ok': False, 'error': f'未知操作: {action}'}

    task.setdefault('flow_log', []).append({
        'at': now_iso(),
        'from': '门下省' if task.get('state') != 'Done' else '皇上',
        'to': to_dept,
        'remark': remark
    })
    _scheduler_mark_progress(task, f'审议动作 {action} -> {task.get("state")}')
    task['updatedAt'] = now_iso()
    save_tasks(tasks)

    # 🚀 审批后自动派发对应 Agent
    new_state = task['state']
    if new_state not in ('Done',):
        dispatch_for_state(task_id, task, new_state)

    label = '已准奏' if action == 'approve' else ('已封驳' if action == 'reject' else '已退回修改')
    dispatched = ' (已自动派发 Agent)' if new_state != 'Done' else ''
    return {'ok': True, 'message': f'{task_id} {label}{dispatched}'}


def handle_register_review_task(task_id, title, from_dept, proposal_title, detail, extra_params=None):
    """注册待审议任务（由通知发送方提前写入，供审批按钮回调使用）。"""
    tasks = load_tasks()
    # 检查是否已存在
    existing = next((t for t in tasks if t.get('id') == task_id), None)
    if existing:
        return {'ok': True, 'task_id': task_id, 'message': '任务已存在'}
    task = {
        'id': task_id,
        'title': title,
        'state': 'Menxia',
        'org': from_dept,
        'official': '侍中',
        'priority': 'normal',
        'review_round': 0,
        'now': f'等待门下省审议',
        'params': {
            'proposal_title': proposal_title,
            'detail': detail,
            **(extra_params or {}),
        },
        'flow_log': [{
            'at': now_iso(),
            'from': from_dept,
            'to': '门下省',
            'remark': '提交审议'
        }],
        'createdAt': now_iso(),
        'updatedAt': now_iso(),
    }
    tasks.append(task)
    save_tasks(tasks)
    return {'ok': True, 'task_id': task_id}


# ══ Agent 在线状态检测 ══

_AGENT_DEPTS = [
    {'id':'taizi',   'label':'太子',  'emoji':'🤴', 'role':'太子',     'rank':'储君'},
    {'id':'zhongshu','label':'中书省','emoji':'📜', 'role':'中书令',   'rank':'正一品'},
    {'id':'menxia',  'label':'门下省','emoji':'🔍', 'role':'侍中',     'rank':'正一品'},
    {'id':'shangshu','label':'尚书省','emoji':'📮', 'role':'尚书令',   'rank':'正一品'},
    {'id':'hubu',    'label':'户部',  'emoji':'💰', 'role':'户部尚书', 'rank':'正二品'},
    {'id':'libu',    'label':'礼部',  'emoji':'📝', 'role':'礼部尚书', 'rank':'正二品'},
    {'id':'bingbu',  'label':'兵部',  'emoji':'⚔️', 'role':'兵部尚书', 'rank':'正二品'},
    {'id':'xingbu',  'label':'刑部',  'emoji':'⚖️', 'role':'刑部尚书', 'rank':'正二品'},
    {'id':'gongbu',  'label':'工部',  'emoji':'🔧', 'role':'工部尚书', 'rank':'正二品'},
    {'id':'libu_hr', 'label':'吏部',  'emoji':'👔', 'role':'吏部尚书', 'rank':'正二品'},
    {'id':'zaochao', 'label':'钦天监','emoji':'📰', 'role':'朝报官',   'rank':'正三品'},
]


def _check_gateway_alive():
    """检测 Gateway 进程是否在运行。"""
    try:
        result = subprocess.run(['pgrep', '-f', 'openclaw-gateway'],
                                capture_output=True, text=True, timeout=1)
        return result.returncode == 0
    except Exception:
        return False


def _check_gateway_probe():
    """通过 HTTP probe 检测 Gateway 是否响应。"""
    try:
        from urllib.request import urlopen
        resp = urlopen('http://127.0.0.1:18789/', timeout=1)
        return resp.status == 200
    except Exception:
        return False


def _get_agent_session_status(agent_id):
    """读取 Agent 的 sessions.json 获取活跃状态。
    返回: (last_active_ts_ms, session_count, is_busy)
    """
    sessions_file = OCLAW_HOME / 'agents' / agent_id / 'sessions' / 'sessions.json'
    if not sessions_file.exists():
        return 0, 0, False
    try:
        data = json.loads(sessions_file.read_text())
        if not isinstance(data, dict):
            return 0, 0, False
        session_count = len(data)
        last_ts = 0
        for v in data.values():
            ts = v.get('updatedAt', 0)
            if isinstance(ts, (int, float)) and ts > last_ts:
                last_ts = ts
        now_ms = int(datetime.datetime.now().timestamp() * 1000)
        age_ms = now_ms - last_ts if last_ts else 9999999999
        is_busy = age_ms <= 2 * 60 * 1000  # 2分钟内视为正在工作
        return last_ts, session_count, is_busy
    except Exception:
        return 0, 0, False


def _check_agent_process(agent_id):
    """检测是否有该 Agent 的 openclaw-agent 进程正在运行。"""
    try:
        result = subprocess.run(
            ['pgrep', '-f', f'openclaw.*--agent.*{agent_id}'],
            capture_output=True, text=True, timeout=1
        )
        return result.returncode == 0
    except Exception:
        return False


def _check_agent_workspace(agent_id):
    """检查 Agent 工作空间是否存在。"""
    ws = OCLAW_HOME / f'workspace-{agent_id}'
    return ws.is_dir()


def get_agents_status():
    """获取所有 Agent 的在线状态（并发优化版）。
    返回各 Agent 的:
    - status: 'running' | 'idle' | 'offline' | 'unconfigured'
    - lastActive: 最后活跃时间
    - sessions: 会话数
    - hasWorkspace: 工作空间是否存在
    - processAlive: 是否有进程在运行
    """
    gateway_alive = _check_gateway_alive()
    gateway_probe = _check_gateway_probe() if gateway_alive else False

    # ── 并发检查所有 agent ──────────────────────────────
    def _check_one(aid):
        has_workspace = _check_agent_workspace(aid)
        last_ts, sess_count, is_busy = _get_agent_session_status(aid)
        process_alive = _check_agent_process(aid)
        return aid, has_workspace, last_ts, sess_count, is_busy, process_alive

    seen_ids = {dept['id'] for dept in _AGENT_DEPTS}
    agent_checks = {}
    with ThreadPoolExecutor(max_workers=min(len(seen_ids), 8)) as pool:
        futures = {pool.submit(_check_one, aid): aid for aid in seen_ids}
        for fut in as_completed(futures):
            aid, has_workspace, last_ts, sess_count, is_busy, process_alive = fut.result()
            agent_checks[aid] = (has_workspace, last_ts, sess_count, is_busy, process_alive)

    agents = []
    for dept in _AGENT_DEPTS:
        aid = dept['id']
        has_workspace, last_ts, sess_count, is_busy, process_alive = agent_checks.get(
            aid, (False, 0, 0, False, False))

        # 状态判定
        if not has_workspace:
            status = 'unconfigured'
            status_label = '❌ 未配置'
        elif not gateway_alive:
            status = 'offline'
            status_label = '🔴 Gateway 离线'
        elif process_alive or is_busy:
            status = 'running'
            status_label = '🟢 运行中'
        elif last_ts > 0:
            now_ms = int(datetime.datetime.now().timestamp() * 1000)
            age_ms = now_ms - last_ts
            if age_ms <= 10 * 60 * 1000:  # 10分钟内
                status = 'idle'
                status_label = '🟡 待命'
            elif age_ms <= 3600 * 1000:  # 1小时内
                status = 'idle'
                status_label = '⚪ 空闲'
            else:
                status = 'idle'
                status_label = '⚪ 休眠'
        else:
            status = 'idle'
            status_label = '⚪ 无记录'

        # 格式化最后活跃时间
        last_active_str = None
        if last_ts > 0:
            try:
                last_active_str = datetime.datetime.fromtimestamp(
                    last_ts / 1000
                ).strftime('%m-%d %H:%M')
            except Exception:
                pass

        agents.append({
            'id': aid,
            'label': dept['label'],
            'emoji': dept['emoji'],
            'role': dept['role'],
            'status': status,
            'statusLabel': status_label,
            'lastActive': last_active_str,
            'lastActiveTs': last_ts,
            'sessions': sess_count,
            'hasWorkspace': has_workspace,
            'processAlive': process_alive,
        })

    return {
        'ok': True,
        'gateway': {
            'alive': gateway_alive,
            'probe': gateway_probe,
            'status': '🟢 运行中' if gateway_probe else ('🟡 进程在但无响应' if gateway_alive else '🔴 未启动'),
        },
        'agents': agents,
        'checkedAt': now_iso(),
    }


def wake_agent(agent_id, message=''):
    """唤醒指定 Agent，发送一条心跳/唤醒消息。"""
    if not _SAFE_NAME_RE.match(agent_id):
        return {'ok': False, 'error': f'agent_id 非法: {agent_id}'}
    if not _check_agent_workspace(agent_id):
        return {'ok': False, 'error': f'{agent_id} 工作空间不存在，请先配置'}
    if not _check_gateway_alive():
        return {'ok': False, 'error': 'Gateway 未启动，请先运行 openclaw gateway start'}

    # agent_id 直接作为 runtime_id（openclaw agents list 中的注册名）
    runtime_id = agent_id
    msg = message or f'🔔 系统心跳检测 — 请回复 OK 确认在线。当前时间: {now_iso()}'

    def do_wake():
        try:
            cmd = ['openclaw', 'agent', '--agent', runtime_id, '-m', msg, '--timeout', '120']
            log.info(f'🔔 唤醒 {agent_id}...')
            # 带重试（最多2次）
            for attempt in range(1, 3):
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=130)
                if result.returncode == 0:
                    log.info(f'✅ {agent_id} 已唤醒')
                    return
                err_msg = result.stderr[:200] if result.stderr else result.stdout[:200]
                log.warning(f'⚠️ {agent_id} 唤醒失败(第{attempt}次): {err_msg}')
                if attempt < 2:
                    import time
                    time.sleep(5)
            log.error(f'❌ {agent_id} 唤醒最终失败')
        except subprocess.TimeoutExpired:
            log.error(f'❌ {agent_id} 唤醒超时(130s)')
        except Exception as e:
            log.warning(f'⚠️ {agent_id} 唤醒异常: {e}')
    threading.Thread(target=do_wake, daemon=True).start()

    return {'ok': True, 'message': f'{agent_id} 唤醒指令已发出，约10-30秒后生效'}


# ══ Agent 实时活动读取 ══

# 状态 → agent_id 映射
_STATE_AGENT_MAP = {
    'Taizi': 'taizi',
    'Zhongshu': 'zhongshu',
    'Menxia': 'menxia',
    'Assigned': 'shangshu',
    'Doing': None,         # 六部，需从 org 推断
    'Review': 'shangshu',
    'Next': None,          # 待执行，从 org 推断
    'Pending': 'zhongshu', # 待处理，默认中书省
}
_ORG_AGENT_MAP = {
    '礼部': 'libu', '户部': 'hubu', '兵部': 'bingbu',
    '刑部': 'xingbu', '工部': 'gongbu', '吏部': 'libu_hr',
    '中书省': 'zhongshu', '门下省': 'menxia', '尚书省': 'shangshu',
}

_TERMINAL_STATES = {'Done', 'Cancelled'}


def _parse_iso(ts):
    if not ts or not isinstance(ts, str):
        return None
    try:
        return datetime.datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except Exception:
        return None


def _ensure_scheduler(task):
    sched = task.setdefault('_scheduler', {})
    if not isinstance(sched, dict):
        sched = {}
        task['_scheduler'] = sched
    sched.setdefault('enabled', True)
    sched.setdefault('stallThresholdSec', 600)
    sched.setdefault('maxRetry', 2)
    sched.setdefault('retryCount', 0)
    sched.setdefault('escalationLevel', 0)
    sched.setdefault('autoRollback', True)
    if not sched.get('lastProgressAt'):
        sched['lastProgressAt'] = task.get('updatedAt') or now_iso()
    if 'stallSince' not in sched:
        sched['stallSince'] = None
    if 'lastDispatchStatus' not in sched:
        sched['lastDispatchStatus'] = 'idle'
    if 'snapshot' not in sched:
        sched['snapshot'] = {
            'state': task.get('state', ''),
            'org': task.get('org', ''),
            'now': task.get('now', ''),
            'savedAt': now_iso(),
            'note': 'init',
        }
    return sched


def _scheduler_add_flow(task, remark, to=''):
    task.setdefault('flow_log', []).append({
        'at': now_iso(),
        'from': '太子调度',
        'to': to or task.get('org', ''),
        'remark': f'🧭 {remark}'
    })


def _scheduler_snapshot(task, note=''):
    sched = _ensure_scheduler(task)
    sched['snapshot'] = {
        'state': task.get('state', ''),
        'org': task.get('org', ''),
        'now': task.get('now', ''),
        'savedAt': now_iso(),
        'note': note or 'snapshot',
    }


def _scheduler_mark_progress(task, note=''):
    sched = _ensure_scheduler(task)
    sched['lastProgressAt'] = now_iso()
    sched['stallSince'] = None
    sched['retryCount'] = 0
    sched['escalationLevel'] = 0
    sched['lastEscalatedAt'] = None
    if note:
        _scheduler_add_flow(task, f'进展确认：{note}')


def _update_task_scheduler(task_id, updater):
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return False
    sched = _ensure_scheduler(task)
    updater(task, sched)
    task['updatedAt'] = now_iso()
    save_tasks(tasks)
    return True


def get_scheduler_state(task_id):
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}
    sched = _ensure_scheduler(task)
    last_progress = _parse_iso(sched.get('lastProgressAt') or task.get('updatedAt'))
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    stalled_sec = 0
    if last_progress:
        stalled_sec = max(0, int((now_dt - last_progress).total_seconds()))
    return {
        'ok': True,
        'taskId': task_id,
        'state': task.get('state', ''),
        'org': task.get('org', ''),
        'scheduler': sched,
        'stalledSec': stalled_sec,
        'checkedAt': now_iso(),
    }


def handle_scheduler_retry(task_id, reason=''):
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}
    state = task.get('state', '')
    if state in _TERMINAL_STATES or state == 'Blocked':
        return {'ok': False, 'error': f'任务 {task_id} 当前状态 {state} 不支持重试'}

    sched = _ensure_scheduler(task)
    sched['retryCount'] = int(sched.get('retryCount') or 0) + 1
    sched['lastRetryAt'] = now_iso()
    sched['lastDispatchTrigger'] = 'taizi-retry'
    _scheduler_add_flow(task, f'触发重试第{sched["retryCount"]}次：{reason or "超时未推进"}')
    task['updatedAt'] = now_iso()
    save_tasks(tasks)

    dispatch_for_state(task_id, task, state, trigger='taizi-retry')
    return {'ok': True, 'message': f'{task_id} 已触发重试派发', 'retryCount': sched['retryCount']}


def handle_scheduler_escalate(task_id, reason=''):
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}
    state = task.get('state', '')
    if state in _TERMINAL_STATES:
        return {'ok': False, 'error': f'任务 {task_id} 已结束，无需升级'}

    sched = _ensure_scheduler(task)
    current_level = int(sched.get('escalationLevel') or 0)
    next_level = min(current_level + 1, 2)
    target = 'menxia' if next_level == 1 else 'shangshu'
    target_label = '门下省' if next_level == 1 else '尚书省'

    sched['escalationLevel'] = next_level
    sched['lastEscalatedAt'] = now_iso()
    _scheduler_add_flow(task, f'升级到{target_label}协调：{reason or "任务停滞"}', to=target_label)
    task['updatedAt'] = now_iso()
    save_tasks(tasks)

    msg = (
        f'🧭 太子调度升级通知\n'
        f'任务ID: {task_id}\n'
        f'当前状态: {state}\n'
        f'停滞处理: 请你介入协调推进\n'
        f'原因: {reason or "任务超过阈值未推进"}\n'
        f'⚠️ 看板已有任务，请勿重复创建。'
    )
    wake_agent(target, msg)

    return {'ok': True, 'message': f'{task_id} 已升级至{target_label}', 'escalationLevel': next_level}


def handle_scheduler_rollback(task_id, reason=''):
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}
    sched = _ensure_scheduler(task)
    snapshot = sched.get('snapshot') or {}
    snap_state = snapshot.get('state')
    if not snap_state:
        return {'ok': False, 'error': f'任务 {task_id} 无可用回滚快照'}

    old_state = task.get('state', '')
    task['state'] = snap_state
    task['org'] = snapshot.get('org', task.get('org', ''))
    task['now'] = f'↩️ 太子调度自动回滚：{reason or "恢复到上个稳定节点"}'
    task['block'] = '无'
    sched['retryCount'] = 0
    sched['escalationLevel'] = 0
    sched['stallSince'] = None
    sched['lastProgressAt'] = now_iso()
    _scheduler_add_flow(task, f'执行回滚：{old_state} → {snap_state}，原因：{reason or "停滞恢复"}')
    task['updatedAt'] = now_iso()
    save_tasks(tasks)

    if snap_state not in _TERMINAL_STATES:
        dispatch_for_state(task_id, task, snap_state, trigger='taizi-rollback')

    return {'ok': True, 'message': f'{task_id} 已回滚到 {snap_state}'}


def handle_scheduler_scan(threshold_sec=600):
    threshold_sec = max(60, int(threshold_sec or 600))
    tasks = load_tasks()
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    pending_retries = []
    pending_escalates = []
    pending_rollbacks = []
    actions = []
    changed = False

    for task in tasks:
        task_id = task.get('id', '')
        state = task.get('state', '')
        if not task_id or state in _TERMINAL_STATES or task.get('archived'):
            continue
        if state == 'Blocked':
            continue

        sched = _ensure_scheduler(task)
        task_threshold = int(sched.get('stallThresholdSec') or threshold_sec)
        last_progress = _parse_iso(sched.get('lastProgressAt') or task.get('updatedAt'))
        if not last_progress:
            continue
        stalled_sec = max(0, int((now_dt - last_progress).total_seconds()))
        if stalled_sec < task_threshold:
            continue

        if not sched.get('stallSince'):
            sched['stallSince'] = now_iso()
            changed = True

        retry_count = int(sched.get('retryCount') or 0)
        max_retry = max(0, int(sched.get('maxRetry') or 1))
        level = int(sched.get('escalationLevel') or 0)

        if retry_count < max_retry:
            sched['retryCount'] = retry_count + 1
            sched['lastRetryAt'] = now_iso()
            sched['lastDispatchTrigger'] = 'taizi-scan-retry'
            _scheduler_add_flow(task, f'停滞{stalled_sec}秒，触发自动重试第{sched["retryCount"]}次')
            pending_retries.append((task_id, state))
            actions.append({'taskId': task_id, 'action': 'retry', 'stalledSec': stalled_sec})
            changed = True
            continue

        if level < 2:
            next_level = level + 1
            target = 'menxia' if next_level == 1 else 'shangshu'
            target_label = '门下省' if next_level == 1 else '尚书省'
            sched['escalationLevel'] = next_level
            sched['lastEscalatedAt'] = now_iso()
            _scheduler_add_flow(task, f'停滞{stalled_sec}秒，升级至{target_label}协调', to=target_label)
            pending_escalates.append((task_id, state, target, target_label, stalled_sec))
            actions.append({'taskId': task_id, 'action': 'escalate', 'to': target_label, 'stalledSec': stalled_sec})
            changed = True
            continue

        if sched.get('autoRollback', True):
            snapshot = sched.get('snapshot') or {}
            snap_state = snapshot.get('state')
            if snap_state and snap_state != state:
                old_state = state
                task['state'] = snap_state
                task['org'] = snapshot.get('org', task.get('org', ''))
                task['now'] = '↩️ 太子调度自动回滚到稳定节点'
                task['block'] = '无'
                sched['retryCount'] = 0
                sched['escalationLevel'] = 0
                sched['stallSince'] = None
                sched['lastProgressAt'] = now_iso()
                _scheduler_add_flow(task, f'连续停滞，自动回滚：{old_state} → {snap_state}')
                pending_rollbacks.append((task_id, snap_state))
                actions.append({'taskId': task_id, 'action': 'rollback', 'toState': snap_state})
                changed = True

    if changed:
        save_tasks(tasks)

    for task_id, state in pending_retries:
        retry_task = next((t for t in tasks if t.get('id') == task_id), None)
        if retry_task:
            dispatch_for_state(task_id, retry_task, state, trigger='taizi-scan-retry')

    for task_id, state, target, target_label, stalled_sec in pending_escalates:
        msg = (
            f'🧭 太子调度升级通知\n'
            f'任务ID: {task_id}\n'
            f'当前状态: {state}\n'
            f'已停滞: {stalled_sec} 秒\n'
            f'请立即介入协调推进\n'
            f'⚠️ 看板已有任务，请勿重复创建。'
        )
        wake_agent(target, msg)

    for task_id, state in pending_rollbacks:
        rollback_task = next((t for t in tasks if t.get('id') == task_id), None)
        if rollback_task and state not in _TERMINAL_STATES:
            dispatch_for_state(task_id, rollback_task, state, trigger='taizi-auto-rollback')

    return {
        'ok': True,
        'thresholdSec': threshold_sec,
        'actions': actions,
        'count': len(actions),
        'checkedAt': now_iso(),
    }


def _startup_recover_queued_dispatches():
    """服务启动后扫描 lastDispatchStatus=queued 的任务，重新派发。
    解决：kill -9 重启导致派发线程中断、任务永久卡住的问题。"""
    tasks = load_tasks()
    recovered = 0
    for task in tasks:
        task_id = task.get('id', '')
        state = task.get('state', '')
        if not task_id or state in _TERMINAL_STATES or task.get('archived'):
            continue
        sched = task.get('_scheduler') or {}
        if sched.get('lastDispatchStatus') == 'queued':
            log.info(f'🔄 启动恢复: {task_id} 状态={state} 上次派发未完成，重新派发')
            sched['lastDispatchTrigger'] = 'startup-recovery'
            dispatch_for_state(task_id, task, state, trigger='startup-recovery')
            recovered += 1
    if recovered:
        log.info(f'✅ 启动恢复完成: 重新派发 {recovered} 个任务')
    else:
        log.info(f'✅ 启动恢复: 无需恢复')


def handle_repair_flow_order():
    """修复历史任务中首条流转为“皇上->中书省”的错序问题。"""
    tasks = load_tasks()
    fixed = 0
    fixed_ids = []

    for task in tasks:
        task_id = task.get('id', '')
        if not task_id.startswith('JJC-'):
            continue
        flow_log = task.get('flow_log') or []
        if not flow_log:
            continue

        first = flow_log[0]
        if first.get('from') != '皇上' or first.get('to') != '中书省':
            continue

        first['to'] = '太子'
        remark = first.get('remark', '')
        if isinstance(remark, str) and remark.startswith('下旨：'):
            first['remark'] = remark

        if task.get('state') == 'Zhongshu' and task.get('org') == '中书省' and len(flow_log) == 1:
            task['state'] = 'Taizi'
            task['org'] = '太子'
            task['now'] = '等待太子接旨分拣'

        task['updatedAt'] = now_iso()
        fixed += 1
        fixed_ids.append(task_id)

    if fixed:
        save_tasks(tasks)

    return {
        'ok': True,
        'count': fixed,
        'taskIds': fixed_ids[:80],
        'more': max(0, fixed - 80),
        'checkedAt': now_iso(),
    }


def _collect_message_text(msg):
    """收集消息中的可检索文本，用于 task_id/关键词过滤。"""
    parts = []
    for c in msg.get('content', []) or []:
        ctype = c.get('type')
        if ctype == 'text' and c.get('text'):
            parts.append(str(c.get('text', '')))
        elif ctype == 'thinking' and c.get('thinking'):
            parts.append(str(c.get('thinking', '')))
        elif ctype == 'tool_use':
            parts.append(json.dumps(c.get('input', {}), ensure_ascii=False))
    details = msg.get('details') or {}
    for key in ('output', 'stdout', 'stderr', 'message'):
        val = details.get(key)
        if isinstance(val, str) and val:
            parts.append(val)
    return ''.join(parts)


def _parse_activity_entry(item):
    """将 session jsonl 的 message 统一解析成看板活动条目。"""
    msg = item.get('message') or {}
    role = str(msg.get('role', '')).strip().lower()
    ts = item.get('timestamp', '')

    if role == 'assistant':
        text = ''
        thinking = ''
        tool_calls = []
        for c in msg.get('content', []) or []:
            if c.get('type') == 'text' and c.get('text') and not text:
                text = str(c.get('text', '')).strip()
            elif c.get('type') == 'thinking' and c.get('thinking') and not thinking:
                thinking = str(c.get('thinking', '')).strip()[:200]
            elif c.get('type') == 'tool_use':
                tool_calls.append({
                    'name': c.get('name', ''),
                    'input_preview': json.dumps(c.get('input', {}), ensure_ascii=False)[:100]
                })
        if not (text or thinking or tool_calls):
            return None
        entry = {'at': ts, 'kind': 'assistant'}
        if text:
            entry['text'] = text[:300]
        if thinking:
            entry['thinking'] = thinking
        if tool_calls:
            entry['tools'] = tool_calls
        return entry

    if role in ('toolresult', 'tool_result'):
        details = msg.get('details') or {}
        code = details.get('exitCode')
        if code is None:
            code = details.get('code', details.get('status'))
        output = ''
        for c in msg.get('content', []) or []:
            if c.get('type') == 'text' and c.get('text'):
                output = str(c.get('text', '')).strip()[:200]
                break
        if not output:
            for key in ('output', 'stdout', 'stderr', 'message'):
                val = details.get(key)
                if isinstance(val, str) and val.strip():
                    output = val.strip()[:200]
                    break

        entry = {
            'at': ts,
            'kind': 'tool_result',
            'tool': msg.get('toolName', msg.get('name', '')),
            'exitCode': code,
            'output': output,
        }
        duration_ms = details.get('durationMs')
        if isinstance(duration_ms, (int, float)):
            entry['durationMs'] = int(duration_ms)
        return entry

    if role == 'user':
        text = ''
        for c in msg.get('content', []) or []:
            if c.get('type') == 'text' and c.get('text'):
                text = str(c.get('text', '')).strip()
                break
        if not text:
            return None
        return {'at': ts, 'kind': 'user', 'text': text[:200]}

    return None


def get_agent_activity(agent_id, limit=30, task_id=None):
    """从 Agent 的 session jsonl 读取最近活动。
    如果 task_id 不为空，只返回提及该 task_id 的相关条目。
    """
    sessions_dir = OCLAW_HOME / 'agents' / agent_id / 'sessions'
    if not sessions_dir.exists():
        return []

    # 扫描所有 jsonl（按修改时间倒序），优先最新
    jsonl_files = sorted(sessions_dir.glob('*.jsonl'), key=lambda f: f.stat().st_mtime, reverse=True)
    if not jsonl_files:
        return []

    entries = []
    # 如果需要按 task_id 过滤，可能需要扫描多个文件
    files_to_scan = jsonl_files[:3] if task_id else jsonl_files[:1]

    for session_file in files_to_scan:
        try:
            lines = session_file.read_text(errors='ignore').splitlines()
        except Exception:
            continue

        # 正向扫描以保持时间顺序；如果有 task_id，收集提及 task_id 的条目
        for ln in lines:
            try:
                item = json.loads(ln)
            except Exception:
                continue
            msg = item.get('message') or {}
            all_text = _collect_message_text(msg)

            # task_id 过滤：只保留提及 task_id 的条目
            if task_id and task_id not in all_text:
                continue
            entry = _parse_activity_entry(item)
            if entry:
                entries.append(entry)

            if len(entries) >= limit:
                break
        if len(entries) >= limit:
            break

    # 只保留最后 limit 条
    return entries[-limit:]


def _extract_keywords(title):
    """从任务标题中提取有意义的关键词（用于 session 内容匹配）。"""
    stop = {'的', '了', '在', '是', '有', '和', '与', '或', '一个', '一篇', '关于', '进行',
            '写', '做', '请', '把', '给', '用', '要', '需要', '面向', '风格', '包含',
            '出', '个', '不', '可以', '应该', '如何', '怎么', '什么', '这个', '那个'}
    # 提取英文词
    en_words = re.findall(r'[a-zA-Z][\w.-]{1,}', title)
    # 提取 2-4 字中文词组（更短的颗粒度）
    cn_words = re.findall(r'[\u4e00-\u9fff]{2,4}', title)
    all_words = en_words + cn_words
    kws = [w for w in all_words if w not in stop and len(w) >= 2]
    # 去重保序
    seen = set()
    unique = []
    for w in kws:
        if w.lower() not in seen:
            seen.add(w.lower())
            unique.append(w)
    return unique[:8]  # 最多 8 个关键词


def get_agent_activity_by_keywords(agent_id, keywords, limit=20):
    """从 agent session 中按关键词匹配获取活动条目。
    找到包含关键词的 session 文件，只读该文件的活动。
    """
    sessions_dir = OCLAW_HOME / 'agents' / agent_id / 'sessions'
    if not sessions_dir.exists():
        return []

    jsonl_files = sorted(sessions_dir.glob('*.jsonl'), key=lambda f: f.stat().st_mtime, reverse=True)
    if not jsonl_files:
        return []

    # 找到包含关键词的 session 文件
    target_file = None
    for sf in jsonl_files[:5]:
        try:
            content = sf.read_text(errors='ignore')
        except Exception:
            continue
        hits = sum(1 for kw in keywords if kw.lower() in content.lower())
        if hits >= min(2, len(keywords)):
            target_file = sf
            break

    if not target_file:
        return []

    # 解析 session 文件，按 user 消息分割为对话段
    # 找到包含关键词的对话段，只返回该段的活动
    try:
        lines = target_file.read_text(errors='ignore').splitlines()
    except Exception:
        return []

    # 第一遍：找到关键词匹配的 user 消息位置
    user_msg_indices = []  # (line_index, user_text)
    for i, ln in enumerate(lines):
        try:
            item = json.loads(ln)
        except Exception:
            continue
        msg = item.get('message') or {}
        if msg.get('role') == 'user':
            text = ''
            for c in msg.get('content', []):
                if c.get('type') == 'text' and c.get('text'):
                    text += c['text']
            user_msg_indices.append((i, text))

    # 找到与关键词匹配度最高的 user 消息
    best_idx = -1
    best_hits = 0
    for line_idx, utext in user_msg_indices:
        hits = sum(1 for kw in keywords if kw.lower() in utext.lower())
        if hits > best_hits:
            best_hits = hits
            best_idx = line_idx

    # 确定对话段的行范围：从匹配的 user 消息到下一个 user 消息之前
    if best_idx >= 0 and best_hits >= min(2, len(keywords)):
        # 找下一个 user 消息的位置
        next_user_idx = len(lines)
        for line_idx, _ in user_msg_indices:
            if line_idx > best_idx:
                next_user_idx = line_idx
                break
        start_line = best_idx
        end_line = next_user_idx
    else:
        # 没找到匹配的对话段，返回空
        return []

    # 第二遍：只解析对话段内的行
    entries = []
    for ln in lines[start_line:end_line]:
        try:
            item = json.loads(ln)
        except Exception:
            continue
        entry = _parse_activity_entry(item)
        if entry:
            entries.append(entry)

    return entries[-limit:]


def get_agent_latest_segment(agent_id, limit=20):
    """获取 Agent 最新一轮对话段（最后一条 user 消息起的所有内容）。
    用于活跃任务没有精确匹配时，展示 Agent 的实时工作状态。
    """
    sessions_dir = OCLAW_HOME / 'agents' / agent_id / 'sessions'
    if not sessions_dir.exists():
        return []

    jsonl_files = sorted(sessions_dir.glob('*.jsonl'),
                         key=lambda f: f.stat().st_mtime, reverse=True)
    if not jsonl_files:
        return []

    # 读取最新的 session 文件
    target_file = jsonl_files[0]
    try:
        lines = target_file.read_text(errors='ignore').splitlines()
    except Exception:
        return []

    # 找到最后一条 user 消息的行号
    last_user_idx = -1
    for i, ln in enumerate(lines):
        try:
            item = json.loads(ln)
        except Exception:
            continue
        msg = item.get('message') or {}
        if msg.get('role') == 'user':
            last_user_idx = i

    if last_user_idx < 0:
        return []

    # 从最后一条 user 消息开始，解析到文件末尾
    entries = []
    for ln in lines[last_user_idx:]:
        try:
            item = json.loads(ln)
        except Exception:
            continue
        entry = _parse_activity_entry(item)
        if entry:
            entries.append(entry)

    return entries[-limit:]


def _compute_phase_durations(flow_log):
    """从 flow_log 计算每个阶段的停留时长。"""
    if not flow_log or len(flow_log) < 1:
        return []
    phases = []
    for i, fl in enumerate(flow_log):
        start_at = fl.get('at', '')
        to_dept = fl.get('to', '')
        remark = fl.get('remark', '')
        # 下一阶段的起始时间就是本阶段的结束时间
        if i + 1 < len(flow_log):
            end_at = flow_log[i + 1].get('at', '')
            ongoing = False
        else:
            end_at = now_iso()
            ongoing = True
        # 计算时长
        dur_sec = 0
        try:
            from_dt = datetime.datetime.fromisoformat(start_at.replace('Z', '+00:00'))
            to_dt = datetime.datetime.fromisoformat(end_at.replace('Z', '+00:00'))
            dur_sec = max(0, int((to_dt - from_dt).total_seconds()))
        except Exception:
            pass
        # 人类可读时长
        if dur_sec < 60:
            dur_text = f'{dur_sec}秒'
        elif dur_sec < 3600:
            dur_text = f'{dur_sec // 60}分{dur_sec % 60}秒'
        elif dur_sec < 86400:
            h, rem = divmod(dur_sec, 3600)
            dur_text = f'{h}小时{rem // 60}分'
        else:
            d, rem = divmod(dur_sec, 86400)
            dur_text = f'{d}天{rem // 3600}小时'
        phases.append({
            'phase': to_dept,
            'from': start_at,
            'to': end_at,
            'durationSec': dur_sec,
            'durationText': dur_text,
            'ongoing': ongoing,
            'remark': remark,
        })
    return phases


def _compute_todos_summary(todos):
    """计算 todos 完成率汇总。"""
    if not todos:
        return None
    total = len(todos)
    completed = sum(1 for t in todos if t.get('status') == 'completed')
    in_progress = sum(1 for t in todos if t.get('status') == 'in-progress')
    not_started = total - completed - in_progress
    percent = round(completed / total * 100) if total else 0
    return {
        'total': total,
        'completed': completed,
        'inProgress': in_progress,
        'notStarted': not_started,
        'percent': percent,
    }


def _compute_todos_diff(prev_todos, curr_todos):
    """计算两个 todos 快照之间的差异。"""
    prev_map = {str(t.get('id', '')): t for t in (prev_todos or [])}
    curr_map = {str(t.get('id', '')): t for t in (curr_todos or [])}
    changed, added, removed = [], [], []
    for tid, ct in curr_map.items():
        if tid in prev_map:
            pt = prev_map[tid]
            if pt.get('status') != ct.get('status'):
                changed.append({
                    'id': tid, 'title': ct.get('title', ''),
                    'from': pt.get('status', ''), 'to': ct.get('status', ''),
                })
        else:
            added.append({'id': tid, 'title': ct.get('title', '')})
    for tid, pt in prev_map.items():
        if tid not in curr_map:
            removed.append({'id': tid, 'title': pt.get('title', '')})
    if not changed and not added and not removed:
        return None
    return {'changed': changed, 'added': added, 'removed': removed}


def get_task_activity(task_id):
    """获取任务的实时进展数据。
    数据来源：
    1. 任务自身的 now / todos / flow_log 字段（由 Agent 通过 progress 命令主动上报）
    2. Agent session JSONL 中的对话日志（thinking / tool_result / user，用于展示思考过程）

    增强字段:
    - taskMeta: 任务元信息 (title/state/org/output/block/priority/reviewRound/archived)
    - phaseDurations: 各阶段停留时长
    - todosSummary: todos 完成率汇总
    - resourceSummary: Agent 资源消耗汇总 (tokens/cost/elapsed)
    - activity 条目中 progress/todos 保留 state/org 快照
    - activity 中 todos 条目含 diff 字段
    """
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}

    state = task.get('state', '')
    org = task.get('org', '')
    now_text = task.get('now', '')
    todos = task.get('todos', [])
    updated_at = task.get('updatedAt', '')

    # ── 任务元信息 ──
    task_meta = {
        'title': task.get('title', ''),
        'state': state,
        'org': org,
        'output': task.get('output', ''),
        'block': task.get('block', ''),
        'priority': task.get('priority', 'normal'),
        'reviewRound': task.get('review_round', 0),
        'archived': task.get('archived', False),
    }

    # 当前负责 Agent（兼容旧逻辑）
    agent_id = _STATE_AGENT_MAP.get(state)
    if agent_id is None and state in ('Doing', 'Next'):
        agent_id = _ORG_AGENT_MAP.get(org)

    # ── 构建活动条目列表（flow_log + progress_log）──
    activity = []
    flow_log = task.get('flow_log', [])

    # 1. flow_log 转为活动条目
    for fl in flow_log:
        activity.append({
            'at': fl.get('at', ''),
            'kind': 'flow',
            'from': fl.get('from', ''),
            'to': fl.get('to', ''),
            'remark': fl.get('remark', ''),
        })

    progress_log = task.get('progress_log', [])
    related_agents = set()

    # 资源消耗累加
    total_tokens = 0
    total_cost = 0.0
    total_elapsed = 0
    has_resource_data = False

    # 用于 todos diff 计算
    prev_todos_snapshot = None

    if progress_log:
        # 2. 多 Agent 实时进展日志（每条 progress 都保留自己的 todo 快照）
        for pl in progress_log:
            p_at = pl.get('at', '')
            p_agent = pl.get('agent', '')
            p_text = pl.get('text', '')
            p_todos = pl.get('todos', [])
            p_state = pl.get('state', '')
            p_org = pl.get('org', '')
            if p_agent:
                related_agents.add(p_agent)
            # 累加资源消耗
            if pl.get('tokens'):
                total_tokens += pl['tokens']
                has_resource_data = True
            if pl.get('cost'):
                total_cost += pl['cost']
                has_resource_data = True
            if pl.get('elapsed'):
                total_elapsed += pl['elapsed']
                has_resource_data = True
            if p_text:
                entry = {
                    'at': p_at,
                    'kind': 'progress',
                    'text': p_text,
                    'agent': p_agent,
                    'agentLabel': pl.get('agentLabel', ''),
                    'state': p_state,
                    'org': p_org,
                }
                # 单条资源数据
                if pl.get('tokens'):
                    entry['tokens'] = pl['tokens']
                if pl.get('cost'):
                    entry['cost'] = pl['cost']
                if pl.get('elapsed'):
                    entry['elapsed'] = pl['elapsed']
                activity.append(entry)
            if p_todos:
                todos_entry = {
                    'at': p_at,
                    'kind': 'todos',
                    'items': p_todos,
                    'agent': p_agent,
                    'agentLabel': pl.get('agentLabel', ''),
                    'state': p_state,
                    'org': p_org,
                }
                # 计算 diff
                diff = _compute_todos_diff(prev_todos_snapshot, p_todos)
                if diff:
                    todos_entry['diff'] = diff
                activity.append(todos_entry)
                prev_todos_snapshot = p_todos

        # 仅当无法通过状态确定 Agent 时，才回退到最后一次上报的 Agent
        if not agent_id:
            last_pl = progress_log[-1]
            if last_pl.get('agent'):
                agent_id = last_pl.get('agent')
    else:
        # 兼容旧数据：仅使用 now/todos
        if now_text:
            activity.append({
                'at': updated_at,
                'kind': 'progress',
                'text': now_text,
                'agent': agent_id or '',
                'state': state,
                'org': org,
            })
        if todos:
            activity.append({
                'at': updated_at,
                'kind': 'todos',
                'items': todos,
                'agent': agent_id or '',
                'state': state,
                'org': org,
            })

    # 按时间排序，保证流转/进展穿插正确
    activity.sort(key=lambda x: x.get('at', ''))

    if agent_id:
        related_agents.add(agent_id)

    # ── 融合 Agent Session 活动（thinking / tool_result / user）──
    # 从 session JSONL 中提取 Agent 的思考过程和工具调用记录
    try:
        session_entries = []
        # 活跃任务：尝试按 task_id 精确匹配
        if state not in ('Done', 'Cancelled'):
            if agent_id:
                entries = get_agent_activity(agent_id, limit=30, task_id=task_id)
                session_entries.extend(entries)
            # 也从其他相关 Agent 获取
            for ra in related_agents:
                if ra != agent_id:
                    entries = get_agent_activity(ra, limit=20, task_id=task_id)
                    session_entries.extend(entries)
        else:
            # 已完成任务：基于关键词匹配
            title = task.get('title', '')
            keywords = _extract_keywords(title)
            if keywords:
                agents_to_scan = list(related_agents) if related_agents else ([agent_id] if agent_id else [])
                for ra in agents_to_scan[:5]:
                    entries = get_agent_activity_by_keywords(ra, keywords, limit=15)
                    session_entries.extend(entries)
        # 去重（通过 at+kind 去重避免重复）
        existing_keys = {(a.get('at', ''), a.get('kind', '')) for a in activity}
        for se in session_entries:
            key = (se.get('at', ''), se.get('kind', ''))
            if key not in existing_keys:
                activity.append(se)
                existing_keys.add(key)
        # 重新排序
        activity.sort(key=lambda x: x.get('at', ''))
    except Exception as e:
        log.warning(f'Session JSONL 融合失败 (task={task_id}): {e}')

    # ── 阶段耗时统计 ──
    phase_durations = _compute_phase_durations(flow_log)

    # ── Todos 汇总 ──
    todos_summary = _compute_todos_summary(todos)

    # ── 总耗时（首条 flow_log 到最后一条/当前） ──
    total_duration = None
    if flow_log:
        try:
            first_at = datetime.datetime.fromisoformat(flow_log[0].get('at', '').replace('Z', '+00:00'))
            if state in ('Done', 'Cancelled') and len(flow_log) >= 2:
                last_at = datetime.datetime.fromisoformat(flow_log[-1].get('at', '').replace('Z', '+00:00'))
            else:
                last_at = datetime.datetime.now(datetime.timezone.utc)
            dur = max(0, int((last_at - first_at).total_seconds()))
            if dur < 60:
                total_duration = f'{dur}秒'
            elif dur < 3600:
                total_duration = f'{dur // 60}分{dur % 60}秒'
            elif dur < 86400:
                h, rem = divmod(dur, 3600)
                total_duration = f'{h}小时{rem // 60}分'
            else:
                d, rem = divmod(dur, 86400)
                total_duration = f'{d}天{rem // 3600}小时'
        except Exception:
            pass

    result = {
        'ok': True,
        'taskId': task_id,
        'taskMeta': task_meta,
        'agentId': agent_id,
        'agentLabel': _STATE_LABELS.get(state, state),
        'lastActive': updated_at[:19].replace('T', ' ') if updated_at else None,
        'activity': activity,
        'activitySource': 'progress+session',
        'relatedAgents': sorted(list(related_agents)),
        'phaseDurations': phase_durations,
        'totalDuration': total_duration,
    }
    if todos_summary:
        result['todosSummary'] = todos_summary
    if has_resource_data:
        result['resourceSummary'] = {
            'totalTokens': total_tokens,
            'totalCost': round(total_cost, 4),
            'totalElapsedSec': total_elapsed,
        }
    return result


# 状态推进顺序（手动推进用）
_STATE_FLOW = {
    'Pending':  ('Taizi', '皇上', '太子', '待处理旨意转交太子分拣'),
    'Taizi':    ('Zhongshu', '太子', '中书省', '太子分拣完毕，转中书省起草'),
    'Zhongshu': ('Menxia', '中书省', '门下省', '中书省方案提交门下省审议'),
    'Menxia':   ('Assigned', '门下省', '尚书省', '门下省准奏，转尚书省派发'),
    'Assigned': ('Doing', '尚书省', '六部', '尚书省开始派发执行'),
    'Next':     ('Doing', '尚书省', '六部', '待执行任务开始执行'),
    'Doing':    ('Review', '六部', '尚书省', '各部完成，进入汇总'),
    'Review':   ('Done', '尚书省', '太子', '全流程完成，回奏太子转报皇上'),
}
_STATE_LABELS = {
    'Pending': '待处理', 'Taizi': '太子', 'Zhongshu': '中书省', 'Menxia': '门下省',
    'Assigned': '尚书省', 'Next': '待执行', 'Doing': '执行中', 'Review': '审查', 'Done': '完成',
}


def dispatch_for_state(task_id, task, new_state, trigger='state-transition'):
    """推进/审批后自动派发对应 Agent（后台异步，不阻塞响应）。"""
    agent_id = _STATE_AGENT_MAP.get(new_state)
    if agent_id is None and new_state in ('Doing', 'Next'):
        org = task.get('org', '')
        agent_id = _ORG_AGENT_MAP.get(org)
    if not agent_id:
        log.info(f'ℹ️ {task_id} 新状态 {new_state} 无对应 Agent，跳过自动派发')
        return

    _update_task_scheduler(task_id, lambda t, s: (
        s.update({
            'lastDispatchAt': now_iso(),
            'lastDispatchStatus': 'queued',
            'lastDispatchAgent': agent_id,
            'lastDispatchTrigger': trigger,
        }),
        _scheduler_add_flow(t, f'已入队派发：{new_state} → {agent_id}（{trigger}）', to=_STATE_LABELS.get(new_state, new_state))
    ))

    title = task.get('title', '(无标题)')
    target_dept = task.get('targetDept', '')

    # 根据 agent_id 构造针对性消息
    _msgs = {
        'taizi': (
            f'📜 皇上旨意需要你处理\n'
            f'任务ID: {task_id}\n'
            f'旨意: {title}\n'
            f'⚠️ 看板已有此任务，请勿重复创建。直接用 kanban_update.py 更新状态。\n'
            f'请立即转交中书省起草执行方案。'
        ),
        'zhongshu': (
            f'📜 旨意已到中书省，请起草方案\n'
            f'任务ID: {task_id}\n'
            f'旨意: {title}\n'
            f'⚠️ 看板已有此任务记录，请勿重复创建。直接用 kanban_update.py state 更新状态。\n'
            f'请立即起草执行方案，走完完整三省流程（中书起草→门下审议→尚书派发→六部执行）。'
        ),
        'menxia': (
            f'📋 中书省方案提交审议\n'
            f'任务ID: {task_id}\n'
            f'旨意: {title}\n'
            f'⚠️ 看板已有此任务，请勿重复创建。\n'
            f'请审议中书省方案，给出准奏或封驳意见。'
        ),
        'shangshu': (
            f'📮 门下省已准奏，请派发执行\n'
            f'任务ID: {task_id}\n'
            f'旨意: {title}\n'
            f'{"建议派发部门: " + target_dept if target_dept else ""}\n'
            f'⚠️ 看板已有此任务，请勿重复创建。\n'
            f'请分析方案并派发给六部执行。'
        ),
    }
    msg = _msgs.get(agent_id, (
        f'📌 请处理任务\n'
        f'任务ID: {task_id}\n'
        f'旨意: {title}\n'
        f'⚠️ 看板已有此任务，请勿重复创建。直接用 kanban_update.py 更新状态。'
    ))

    def _do_dispatch():
        try:
            if not _check_gateway_alive():
                log.warning(f'⚠️ {task_id} 自动派发跳过: Gateway 未启动')
                _update_task_scheduler(task_id, lambda t, s: s.update({
                    'lastDispatchAt': now_iso(),
                    'lastDispatchStatus': 'gateway-offline',
                    'lastDispatchAgent': agent_id,
                    'lastDispatchTrigger': trigger,
                }))
                return
            # Fix #139: dispatch channel 可配置（默认 feishu，支持 telegram/wecom/signal 等）
            _agent_cfg = read_json(DATA / 'agent_config.json', {})
            _channel = (_agent_cfg.get('dispatchChannel') or 'feishu').strip()
            cmd = ['openclaw', 'agent', '--agent', agent_id, '-m', msg,
                   '--deliver', '--channel', _channel, '--timeout', '300']
            max_retries = 2
            err = ''
            for attempt in range(1, max_retries + 1):
                log.info(f'🔄 自动派发 {task_id} → {agent_id} (第{attempt}次)...')
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=310)
                if result.returncode == 0:
                    log.info(f'✅ {task_id} 自动派发成功 → {agent_id}')
                    _update_task_scheduler(task_id, lambda t, s: (
                        s.update({
                            'lastDispatchAt': now_iso(),
                            'lastDispatchStatus': 'success',
                            'lastDispatchAgent': agent_id,
                            'lastDispatchTrigger': trigger,
                            'lastDispatchError': '',
                        }),
                        _scheduler_add_flow(t, f'派发成功：{agent_id}（{trigger}）', to=t.get('org', ''))
                    ))
                    return
                err = result.stderr[:200] if result.stderr else result.stdout[:200]
                log.warning(f'⚠️ {task_id} 自动派发失败(第{attempt}次): {err}')
                if attempt < max_retries:
                    import time
                    time.sleep(5)
            log.error(f'❌ {task_id} 自动派发最终失败 → {agent_id}')
            _update_task_scheduler(task_id, lambda t, s: (
                s.update({
                    'lastDispatchAt': now_iso(),
                    'lastDispatchStatus': 'failed',
                    'lastDispatchAgent': agent_id,
                    'lastDispatchTrigger': trigger,
                    'lastDispatchError': err,
                }),
                _scheduler_add_flow(t, f'派发失败：{agent_id}（{trigger}）', to=t.get('org', ''))
            ))
        except subprocess.TimeoutExpired:
            log.error(f'❌ {task_id} 自动派发超时 → {agent_id}')
            _update_task_scheduler(task_id, lambda t, s: (
                s.update({
                    'lastDispatchAt': now_iso(),
                    'lastDispatchStatus': 'timeout',
                    'lastDispatchAgent': agent_id,
                    'lastDispatchTrigger': trigger,
                    'lastDispatchError': 'timeout',
                }),
                _scheduler_add_flow(t, f'派发超时：{agent_id}（{trigger}）', to=t.get('org', ''))
            ))
        except Exception as e:
            log.warning(f'⚠️ {task_id} 自动派发异常: {e}')
            _update_task_scheduler(task_id, lambda t, s: (
                s.update({
                    'lastDispatchAt': now_iso(),
                    'lastDispatchStatus': 'error',
                    'lastDispatchAgent': agent_id,
                    'lastDispatchTrigger': trigger,
                    'lastDispatchError': str(e)[:200],
                }),
                _scheduler_add_flow(t, f'派发异常：{agent_id}（{trigger}）', to=t.get('org', ''))
            ))

    threading.Thread(target=_do_dispatch, daemon=True).start()
    log.info(f'🚀 {task_id} 推进后自动派发 → {agent_id}')


def handle_advance_state(task_id, comment=''):
    """手动推进任务到下一阶段（解卡用），推进后自动派发对应 Agent。"""
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}
    cur = task.get('state', '')
    if cur not in _STATE_FLOW:
        return {'ok': False, 'error': f'任务 {task_id} 状态为 {cur}，无法推进'}
    _ensure_scheduler(task)
    _scheduler_snapshot(task, f'advance-before-{cur}')
    next_state, from_dept, to_dept, default_remark = _STATE_FLOW[cur]
    remark = comment or default_remark

    task['state'] = next_state
    task['now'] = f'⬇️ 手动推进：{remark}'
    task.setdefault('flow_log', []).append({
        'at': now_iso(),
        'from': from_dept,
        'to': to_dept,
        'remark': f'⬇️ 手动推进：{remark}'
    })
    _scheduler_mark_progress(task, f'手动推进 {cur} -> {next_state}')
    task['updatedAt'] = now_iso()
    save_tasks(tasks)

    # 🚀 推进后自动派发对应 Agent（Done 状态无需派发）
    if next_state != 'Done':
        dispatch_for_state(task_id, task, next_state)

    from_label = _STATE_LABELS.get(cur, cur)
    to_label = _STATE_LABELS.get(next_state, next_state)
    dispatched = ' (已自动派发 Agent)' if next_state != 'Done' else ''
    return {'ok': True, 'message': f'{task_id} {from_label} → {to_label}{dispatched}'}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # 只记录 4xx/5xx 错误请求
        if args and len(args) >= 1:
            status = str(args[0]) if args else ''
            if status.startswith('4') or status.startswith('5'):
                log.warning(f'{self.client_address[0]} {fmt % args}')

    def handle_error(self):
        pass  # 静默处理连接错误，避免 BrokenPipe 崩溃

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass  # 客户端断开连接，忽略

    def do_OPTIONS(self):
        self.send_response(200)
        cors_headers(self)
        self.end_headers()

    def send_json(self, data, code=200):
        try:
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            cors_headers(self)
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_file(self, path: pathlib.Path, mime='text/html; charset=utf-8'):
        if not path.exists():
            self.send_error(404)
            return
        try:
            body = path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            cors_headers(self)
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _serve_static(self, rel_path):
        """从 dist/ 目录提供静态文件。"""
        safe = rel_path.replace('\\', '/').lstrip('/')
        if '..' in safe:
            self.send_error(403)
            return True
        fp = DIST / safe
        if fp.is_file():
            mime = _MIME_TYPES.get(fp.suffix.lower(), 'application/octet-stream')
            self.send_file(fp, mime)
            return True
        return False

    def do_GET(self):
        p = urlparse(self.path).path.rstrip('/')
        if p in ('', '/dashboard', '/dashboard.html'):
            self.send_file(DIST / 'index.html')
        elif p == '/bingbu':
            # 兵部监控台 - serve 7892的HTML文件
            bingbu_html = pathlib.Path('/Users/luxiangnan/freqtrade_console/兵部监控台.html')
            if bingbu_html.exists():
                self.send_file(bingbu_html)
            else:
                self.send_error(404, 'File not found')
        elif p == '/qintianjian':
            # 钦天监 · 情报与决策中心
            tpl = BASE / 'templates' / 'qintianjian.html'
            if tpl.exists():
                self.send_file(tpl)
            else:
                self.send_error(404, 'qintianjian template not found')
        elif p == '/healthz':
            checks = {'dataDir': DATA.is_dir(), 'tasksReadable': (DATA / 'tasks_source.json').exists()}
            checks['dataWritable'] = os.access(str(DATA), os.WEEK)
            all_ok = all(checks.values())
            self.send_json({'status': 'ok' if all_ok else 'degraded', 'ts': now_iso(), 'checks': checks})
        elif p == '/strategy-params':
            self.send_file(BASE / 'templates' / 'strategy_params.html')
        elif p == '/api/v1/autopilot/config':
            # 代理到 9090 bot，带 auth
            try:
                import requests as _req
                r = _req.get(
                    'http://127.0.0.1:9090/api/v1/autopilot/config',
                    auth=('freqtrade', 'freqtrade'),
                    timeout=5
                )
                self.send_response(r.status_code)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(r.content)
            except Exception as e:
                self.send_error(502, f'Bot unreachable: {e}')
        elif p == '/api/live-status':
            self.send_json(read_json(DATA / 'live_status.json'))
        elif p == '/api/agent-config':
            self.send_json(read_json(DATA / 'agent_config.json'))
        elif p == '/api/model-change-log':
            self.send_json(read_json(DATA / 'model_change_log.json', []))
        elif p == '/api/last-result':
            self.send_json(read_json(DATA / 'last_model_change_result.json', {}))
        elif p == '/api/officials-stats':
            self.send_json(read_json(DATA / 'officials_stats.json', {}))
        elif p == '/api/morning-brief':
            self.send_json(read_json(DATA / 'morning_brief.json', {}))
        elif p == '/api/agent-reports':
            self.send_json(get_agent_reports())
        elif p == '/api/morning-config':
            self.send_json(read_json(DATA / 'morning_brief_config.json', {
                'categories': [
                    {'name': '政治', 'enabled': True},
                    {'name': '军事', 'enabled': True},
                    {'name': '经济', 'enabled': True},
                    {'name': 'AI大模型', 'enabled': True},
                ],
                'keywords': [], 'custom_feeds': [], 'feishu_webhook': '',
            }))
        elif p.startswith('/api/morning-brief/'):
            date = p.split('/')[-1]
            # 标准化日期格式为 YYYYMMDD（兼容 YYYY-MM-DD 输入）
            date_clean = date.replace('-', '')
            if not date_clean.isdigit() or len(date_clean) != 8:
                self.send_json({'ok': False, 'error': f'日期格式无效: {date}，请使用 YYYYMMDD'}, 400)
                return
            self.send_json(read_json(DATA / f'morning_brief_{date_clean}.json', {}))
        elif p == '/api/remote-skills-list':
            self.send_json(get_remote_skills_list())
        elif p.startswith('/api/skill-content/'):
            # /api/skill-content/{agentId}/{skillName}
            parts = p.replace('/api/skill-content/', '').split('/', 1)
            if len(parts) == 2:
                self.send_json(read_skill_content(parts[0], parts[1]))
            else:
                self.send_json({'ok': False, 'error': 'Usage: /api/skill-content/{agentId}/{skillName}'}, 400)
        elif p.startswith('/api/task-activity/'):
            task_id = p.replace('/api/task-activity/', '')
            if not task_id:
                self.send_json({'ok': False, 'error': 'task_id required'}, 400)
            else:
                self.send_json(get_task_activity(task_id))
        elif p.startswith('/api/scheduler-state/'):
            task_id = p.replace('/api/scheduler-state/', '')
            if not task_id:
                self.send_json({'ok': False, 'error': 'task_id required'}, 400)
            else:
                self.send_json(get_scheduler_state(task_id))
        elif p == '/api/agents-status':
            self.send_json(get_agents_status())
        elif p.startswith('/api/agent-activity/'):
            agent_id = p.replace('/api/agent-activity/', '')
            if not agent_id or not _SAFE_NAME_RE.match(agent_id):
                self.send_json({'ok': False, 'error': 'invalid agent_id'}, 400)
            else:
                self.send_json({'ok': True, 'agentId': agent_id, 'activity': get_agent_activity(agent_id)})
        # ── 朝堂议政 ──
        elif p == '/api/court-discuss/list':
            self.send_json({'ok': True, 'sessions': cd_list()})
        elif p == '/api/court-discuss/officials':
            self.send_json({'ok': True, 'officials': CD_PROFILES})
        elif p.startswith('/api/court-discuss/session/'):
            sid = p.replace('/api/court-discuss/session/', '')
            data = cd_get(sid)
            self.send_json(data if data else {'ok': False, 'error': 'session not found'}, 200 if data else 404)
        elif p == '/api/court-discuss/fate':
            self.send_json({'ok': True, 'event': cd_fate()})
        # ── 钦天监数据中枢 ──
        elif p == '/api/qintianjian-data':
            hub_file = pathlib.Path.home() / 'freqtrade/scripts/tianlu_data_hub/data/hub_output.json'
            if hub_file.exists():
                try:
                    with open(hub_file) as f:
                        self.send_json(json.load(f))
                except Exception as e:
                    self.send_json({'error': str(e)}, 500)
            else:
                self.send_json({'error': 'hub data not found'}, 404)
        elif p == '/api/advisor/history':
            hist_file = pathlib.Path.home() / 'freqtrade/scripts/advisor_history.json'
            if hist_file.exists():
                try:
                    with open(hist_file) as f:
                        self.send_json(json.load(f))
                except Exception as e:
                    self.send_json({'records': [], 'error': str(e)}, 200)
            else:
                self.send_json({'records': []}, 200)
        # ── 动态干预系统配置 API ───────────────────────────
        elif p == '/api/intervention/config':
            # 干预参数按类别聚合
            config = {
                # ── L1-L6 情绪干预阈值 ──────────────────
                "sentiment_levels": {
                    "L1": {"label": "量比预警", "trigger": "量比 1.5x~2x", "action": "观察", "urgency": 2},
                    "L2": {"label": "资金流预警", "trigger": "主力资金净流出", "action": "轻仓观察", "urgency": 4},
                    "L3": {"label": "恐慌信号", "trigger": "FG≤35 或 恐慌类新闻", "action": "减仓/冻结", "urgency": 6},
                    "L4": {"label": "黑天鹅预警", "trigger": "FG≤20 或 多类别恐慌", "action": "全市场冻结审批", "urgency": 8},
                    "L5": {"label": "动态止盈优化", "trigger": "杠杆1X~10X分档", "action": "分档止盈", "urgency": 3},
                    "L6": {"label": "OBI外部信号", "trigger": "Gate.io REST ±0.20阈值", "action": "OBI信号入场", "urgency": 5},
                },
                # ── 黑天鹅规则 ─────────────────────────
                "black_swan": {
                    "fg_threshold": 20,
                    "urgency_threshold": 8,
                    "cooldown_hours": 6,
                    "rejected_cooldown_hours": 6,
                },
                # ── 风控阈值 ────────────────────────────
                "risk_params": {
                    "liquidation_alert_pct": 15.0,
                    "var_95_threshold_pct": 3.0,
                    "atr_volatility_multiplier": 2.5,
                    "var_lookback_period": 20,
                    "var_confidence": 0.95,
                    "freeze_cooldown_minutes": 30,
                },
                # ── 干预动作规则 ────────────────────────
                "action_rules": {
                    "inject_long_pair":   {"label": "📈 注入做多信号",  "color": "green",  "requires_approval": True,  "description": "向指定交易对注入做多信号"},
                    "inject_short_pair":  {"label": "📉 注入做空信号",  "color": "orange", "requires_approval": True,  "description": "向指定交易对注入做空信号"},
                    "force_exit_pair":    {"label": "🔴 强制平仓",       "color": "red",    "requires_approval": True,  "description": "强制平掉指定交易对持仓"},
                    "emergency_exit_all": {"label": "🚨 全市场双向强平", "color": "red",    "requires_approval": True,  "description": "双向强平所有持仓"},
                    "freeze_pair":        {"label": "❄️ 冻结指定交易对", "color": "blue",   "requires_approval": True,  "description": "冻结指定交易对，禁止新开仓"},
                    "freeze":            {"label": "❄️ 全市场冻结",     "color": "blue",   "requires_approval": True,  "description": "冻结全市场，禁止所有新开仓"},
                    "black_swan_freeze": {"label": "🚨 黑天鹅紧急接管", "color": "red",    "requires_approval": True, "description": "黑天鹅自动触发，需审批后执行"},
                    "unfreeze":          {"label": "🔥 解冻（保护性）", "color": "green",  "requires_approval": True, "description": "解冻需审批后执行"},
                },
                # ── 飞书卡片颜色配置 ────────────────────
                "card_colors": {
                    "inject_long_pair":   {"header": "green", "button": "#2E7D32", "light_bg": "#E8F5E9"},
                    "inject_short_pair":  {"header": "orange", "button": "#E65100", "light_bg": "#FFF3E0"},
                    "force_exit_pair":   {"header": "red",    "button": "#C62828", "light_bg": "#FFEBEE"},
                    "emergency_exit_all": {"header": "red",    "button": "#B71C1C", "light_bg": "#FFEBEE"},
                    "freeze_pair":       {"header": "blue",   "button": "#1565C0", "light_bg": "#E3F2FD"},
                    "freeze":            {"header": "blue",   "button": "#1565C0", "light_bg": "#E3F2FD"},
                    "black_swan_freeze": {"header": "red",    "button": "#B71C1C", "light_bg": "#FFEBEE"},
                },
                # ── 提案审核时限 ────────────────────────
                "proposal_expiry_minutes": 15,
                "fetch_time": datetime.datetime.now().isoformat(),
            }
            self.send_json(config)

        # ── 钦天监 · 情报与决策中心 API ──────────────────────
        elif p == '/api/qintianjian/market-data':
            try:
                sys.path.insert(0, str(BASE.parent / 'qintianjian'))
                from data_collector import collect_all
                data = collect_all()
                self.send_json(data)
            except Exception as e:
                self.send_json({'error': str(e), 'symbols': {}, 'sentiment': {}, 'positions': [], 'balances': {}})
        elif p == '/api/qintianjian/rules':
            try:
                sys.path.insert(0, str(BASE.parent / 'qintianjian'))
                from rule_engine import run_engine
                result = run_engine(submit=False)
                self.send_json(result)
            except Exception as e:
                self.send_json({'error': str(e), 'triggered': [], 'market_data': {}})
        elif p == '/api/qintianjian/proposals':
            try:
                sys.path.insert(0, str(BASE.parent / 'qintianjian'))
                from rule_engine import get_proposals
                proposals = get_proposals(limit=50)
                self.send_json(proposals)
            except Exception as e:
                self.send_json({'error': str(e)})
        elif p == '/api/qintianjian/run':
            try:
                sys.path.insert(0, str(BASE.parent / 'qintianjian'))
                from rule_engine import run_engine
                result = run_engine(submit=True)
                self.send_json({'ok': True, 'triggered': len(result.get('triggered', [])), 'result': result})
            except Exception as e:
                self.send_json({'ok': False, 'error': str(e)})

        # ── 兵部动态干预系统 API ──────────────────────────────
        elif p == '/api/bingbu/sentiment':
            data = _bingbu_read_json(BINGBU_SENTIMENT_FILE, {})
            if not isinstance(data, dict):
                data = {}
            data['fetch_time'] = datetime.datetime.now().isoformat()
            self.send_json(data)
        elif p == '/api/bingbu/intervention':
            interventions = _bingbu_read_json(BINGBU_INTERVENTION_FILE, [])
            latest = interventions[-1] if interventions and isinstance(interventions, list) else None
            self.send_json({'latest': latest, 'count': len(interventions) if isinstance(interventions, list) else 0})
        elif p == '/api/bingbu/intervention_history':
            interventions = _bingbu_read_json(BINGBU_INTERVENTION_FILE, [])
            if not isinstance(interventions, list):
                interventions = []
            self.send_json({'interventions': interventions, 'intervention_count': len(interventions)})
        elif p == '/api/bingbu/intervention_log':
            interventions = _bingbu_read_json(BINGBU_INTERVENTION_FILE, [])
            if not isinstance(interventions, list):
                interventions = []
            log_lines = []
            for iv in interventions:
                log_lines.append(f"[{iv.get('timestamp','?')}] {iv.get('action','?')}: {iv.get('reason','?')} → {iv.get('result','?')}")
            self.send_json({'log': '\n'.join(log_lines) if log_lines else '暂无干预记录'})
        elif p == '/api/bingbu/freeze_status':
            freeze_file = pathlib.Path.home() / 'edict/data/bingbu_freeze.json'
            if freeze_file.exists():
                import json as _fj
                fd = _fj.loads(freeze_file.read_text())
                self.send_json(fd)
            else:
                self.send_json({'frozen': False, 'frozen_pairs': []})
        elif p == '/api/bingbu/balances':
            # 各 Bot 账户余额（D-2: 统一使用 free USDT，与api_autopilot/monitor_sentiment一致）
            import base64
            _auth = lambda u,p: 'Basic ' + base64.b64encode(f'{u}:{p}'.encode()).decode()
            BOT_CFG = {
                9090: {'url':'http://127.0.0.1:9090','auth':_auth('freqtrade','freqtrade'),'label':'Gate-17656685222','exchange':'Gate.io'},
                9091: {'url':'http://127.0.0.1:9091','auth':_auth('freqtrade','freqtrade'),'label':'Gate-85363904550','exchange':'Gate.io'},
                9092: {'url':'http://127.0.0.1:9092','auth':_auth('freqtrade','freqtrade'),'label':'Gate-15637798222','exchange':'Gate.io'},
                9093: {'url':'http://127.0.0.1:9093','auth':_auth('admin','Xy@06130822'),'label':'OKX-15637798222','exchange':'OKX'},
                9094: {'url':'http://127.0.0.1:9094','auth':_auth('admin','Xy@06130822'),'label':'OKX-BOT85363904550','exchange':'OKX'},
                9095: {'url':'http://127.0.0.1:9095','auth':_auth('admin','Xy@06130822'),'label':'OKX-BOTa44056283','exchange':'OKX'},
                9096: {'url':'http://127.0.0.1:9096','auth':_auth('admin','Xy@06130822'),'label':'OKX-BHB16638759999','exchange':'OKX'},
                9097: {'url':'http://127.0.0.1:9097','auth':_auth('admin','Xy@06130822'),'label':'OKX-17656685222','exchange':'OKX'},
            }
            result = []
            for port, cfg in BOT_CFG.items():
                try:
                    r = requests.get(f"{cfg['url']}/api/v1/balance", headers={"Authorization":cfg["auth"]}, timeout=5)
                    if r.status_code == 200:
                        d = r.json()
                        # D-2: 统一使用 free USDT（OKX SHORT时total为负，改用free之和）
                        total = d.get("total", 0)
                        currencies_data = d.get("currencies", [])
                        # 计算free USDT之和（统一数据源）
                        free_usdt = sum(
                            float(c.get("free", 0))
                            for c in currencies_data
                            if c.get("currency", "").upper() in ("USDT", "USDC")
                        )
                        # OKX SHORT时total为负，直接用free_usdt
                        if total < 0 or free_usdt > 0:
                            total = free_usdt
                        currencies = []
                        for c in currencies_data:
                            free = float(c.get("free", 0))
                            if free > 0 or c.get("currency") in ("USDT","USDC"):
                                currencies.append({"currency": c["currency"], "free": round(free, 4), "balance": round(float(c.get("balance", 0)), 4)})
                        result.append({"port": port, "label": cfg["label"], "exchange": cfg["exchange"], "free_usdt": round(total, 2), "balance": round(total, 2), "currencies": currencies, "online": True})
                    else:
                        result.append({"port": port, "label": cfg["label"], "exchange": cfg["exchange"], "free_usdt": 0, "balance": 0, "currencies": [], "online": False})
                except Exception:
                    result.append({"port": port, "label": cfg["label"], "exchange": cfg["exchange"], "free_usdt": 0, "balance": 0, "currencies": [], "online": False})
            total_all = round(sum(b["free_usdt"] for b in result), 2)
            self.send_json({"balances": result, "total": total_all, "source": "free_usdt"})

        elif p == '/api/bingbu/positions':
            positions = _bingbu_fetch_positions()
            total_pnl = round(sum(p['unrealized_pnl'] for p in positions), 2)
            self.send_json({'positions': positions, 'count': len(positions), 'total_pnl': total_pnl, 'fetched_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

        # ── 机器人统一数据 API ──────────────────────────────
        elif p == '/api/bots/balances':
            # 各 Bot 账户余额（统一格式，供监控面板使用）
            import base64 as _b64
            _mkauth = lambda u, pw: 'Basic ' + _b64.b64encode(f'{u}:{pw}'.encode()).decode()
            BOT_MAP = {
                9090: {'url': 'http://127.0.0.1:9090', 'auth': _mkauth('freqtrade', 'freqtrade'), 'label': 'Gate-17656685222', 'exchange': 'Gate.io'},
                9091: {'url': 'http://127.0.0.1:9091', 'auth': _mkauth('freqtrade', 'freqtrade'), 'label': 'Gate-85363904550', 'exchange': 'Gate.io'},
                9092: {'url': 'http://127.0.0.1:9092', 'auth': _mkauth('freqtrade', 'freqtrade'), 'label': 'Gate-15637798222', 'exchange': 'Gate.io'},
                9093: {'url': 'http://127.0.0.1:9093', 'auth': _mkauth('admin', 'Xy@06130822'), 'label': 'OKX-15637798222', 'exchange': 'OKX'},
                9094: {'url': 'http://127.0.0.1:9094', 'auth': _mkauth('admin', 'Xy@06130822'), 'label': 'OKX-BOT85363904550', 'exchange': 'OKX'},
                9095: {'url': 'http://127.0.0.1:9095', 'auth': _mkauth('admin', 'Xy@06130822'), 'label': 'OKX-BOTa44056283', 'exchange': 'OKX'},
                9096: {'url': 'http://127.0.0.1:9096', 'auth': _mkauth('admin', 'Xy@06130822'), 'label': 'OKX-BHB16638759999', 'exchange': 'OKX'},
                9097: {'url': 'http://127.0.0.1:9097', 'auth': _mkauth('admin', 'Xy@06130822'), 'label': 'OKX-17656685222', 'exchange': 'OKX'},
            }

            def _fetch_one(port, cfg):
                try:
                    r = requests.get(f"{cfg['url']}/api/v1/balance", headers={'Authorization': cfg['auth']}, timeout=3)
                    if r.status_code == 200:
                        d = r.json()
                        total = float(d.get('total', 0) or 0)
                        starting = float(d.get('starting_capital', 0) or 0)
                        currencies_data = d.get('currencies', [])
                        free_usdt = sum(float(c.get('free', 0)) for c in currencies_data if c.get('currency', '').upper() in ('USDT', 'USDC'))
                        if total < 0 or free_usdt > 0:
                            total = free_usdt
                        return {'port': port, 'label': cfg['label'], 'exchange': cfg['exchange'],
                                'total': round(total, 2), 'starting_capital': round(starting, 2),
                                'profit': round(total - starting, 2),
                                'profit_pct': round((total - starting) / starting * 100, 2) if starting > 0 else 0,
                                'online': True}
                except Exception:
                    pass
                return {'port': port, 'label': cfg['label'], 'exchange': cfg['exchange'],
                        'total': 0, 'starting_capital': 0, 'profit': 0, 'profit_pct': 0, 'online': False}

            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(lambda cfg: _fetch_one(cfg[0], cfg[1]), BOT_MAP.items()))
            total_all = round(sum(b['total'] for b in results), 2)
            total_profit = round(sum(b['profit'] for b in results), 2)
            self.send_json({'bots': results, 'total': total_all, 'total_profit': total_profit})

        elif p == '/api/bots/positions':
            positions = _bingbu_fetch_positions()
            total_pnl = round(sum(p['unrealized_pnl'] for p in positions), 2)
            self.send_json({'positions': positions, 'count': len(positions), 'total_pnl': total_pnl})

        elif p == '/api/bingbu/proposals':
            sys.path.insert(0, str(pathlib.Path(__file__).parent))
            from monitor_sentiment import load_proposals
            proposals = load_proposals()
            active = [p for p in proposals if p['status'] == 'pending']
            self.send_json({'proposals': active, 'count': len(active)})

        elif p == '/api/bingbu/unfreeze':
            # GET /api/bingbu/unfreeze → 直接执行解冻（无需审批，保护性操作）
            pair = ''
            freeze_file = pathlib.Path.home() / 'edict/data/bingbu_freeze.json'
            if freeze_file.exists():
                import json as _json
                fd = _json.loads(freeze_file.read_text())
                fd = {'frozen': False, 'frozen_pairs': [], 'timestamp': datetime.datetime.now().isoformat()}
                freeze_file.write_text(_json.dumps(fd, indent=2))
            # 同步清除 force_executed，防止 bingbu_patrol 继续静默跳过
            state_file = pathlib.Path.home() / 'edict/data/bingbu_intervention_state.json'
            if state_file.exists():
                import json as _json2
                try:
                    st = _json2.loads(state_file.read_text())
                except Exception:
                    st = {}
                st['force_executed'] = False
                st['force_executed_at'] = ''
                st['force_executed_alert_id'] = ''
                state_file.write_text(_json2.dumps(st, indent=2))
            sys.path.insert(0, str(pathlib.Path(__file__).parent))
            from monitor_sentiment import load_sentiment, add_intervention as iv_add
            sent = load_sentiment()
            iv_add('unfreeze', '手动解冻（飞书卡片按钮）', sent, 'success', targets=[])
            self.send_json({'ok': True, 'action': 'unfreeze', 'pair': 'global', 'result': 'success'})

        elif p == '/api/bingbu/freeze_pair':
            # GET /api/bingbu/freeze_pair → 提交全市场冻结提案（默认L4）
            sys.path.insert(0, str(pathlib.Path(__file__).parent))
            from monitor_sentiment import create_proposal, load_sentiment
            sent = load_sentiment()
            proposal = create_proposal(
                action='freeze',
                reason='兵部手动干预：全市场冻结（飞书卡片按钮）',
                details={'pair': '', 'level': 'L4'},
                sentiment=sent,
            )
            self.send_json({
                'ok': True,
                'type': 'proposal',
                'message': '已提交飞书审核，等待批准后执行',
                'proposal_id': proposal['id'],
                'code': proposal['code'],
                'expires_at': proposal['expires_at'],
            })

        elif p == '/bingbu/unfreeze':
            # GET /bingbu/unfreeze → 解冻确认页
            sys.path.insert(0, str(pathlib.Path(__file__).parent))
            from monitor_sentiment import load_sentiment, add_intervention as iv_add
            import json as _jsonj
            freeze_file = pathlib.Path.home() / 'edict/data/bingbu_freeze.json'
            if freeze_file.exists():
                fd = _jsonj.loads(freeze_file.read_text())
                fd = {'frozen': False, 'frozen_pairs': [], 'timestamp': datetime.datetime.now().isoformat()}
                freeze_file.write_text(_jsonj.dumps(fd, indent=2))
            # 同步清除 force_executed，防止 bingbu_patrol 继续静默跳过
            state_file = pathlib.Path.home() / 'edict/data/bingbu_intervention_state.json'
            if state_file.exists():
                import json as _jsonj2
                try:
                    st = _jsonj2.loads(state_file.read_text())
                except Exception:
                    st = {}
                st['force_executed'] = False
                st['force_executed_at'] = ''
                st['force_executed_alert_id'] = ''
                state_file.write_text(_jsonj2.dumps(st, indent=2))
            sent = load_sentiment()
            iv_add('unfreeze', '手动解冻（飞书卡片按钮）', sent, 'success', targets=[])
            html = '<html><body style="font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#f0f4f8;"><div style="background:#fff;border-radius:12px;padding:40px;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,0.1);"><div style="font-size:64px;">✅</div><h2 style="margin:16px 0 8px;">已解除冻结</h2><p style="color:#666;margin:0 0 24px;">系统已恢复正常交易。</p><p style="color:#999;font-size:13px;margin:0;">请手动关闭此页面</p></div></body></html>'
            body = html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)
            return

        elif p == '/bingbu/status':
            # GET /bingbu/status → 状态查询页
            interventions = _bingbu_read_json(BINGBU_INTERVENTION_FILE, [])
            latest = interventions[-1] if interventions and isinstance(interventions, list) else None
            lv = latest.get('action', '无') if latest else '无'
            lr = latest.get('reason', '') if latest else ''
            lt = latest.get('timestamp', '') if latest else ''
            html = f'<html><body style="font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#f0f4f8;"><div style="background:#fff;border-radius:12px;padding:40px;max-width:500px;width:90%;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,0.1);"><div style="font-size:48px;">📊</div><h2 style="margin:16px 0 8px;">兵部最新干预</h2><div style="text-align:left;background:#f6f8fa;border-radius:8px;padding:16px;margin:16px 0;"><p><strong>动作：</strong>{lv}</p><p><strong>原因：</strong>{lr[:60]}</p><p><strong>时间：</strong>{lt}</p><p><strong>累计：</strong>{len(interventions)} 条</p></div><p style="color:#999;font-size:13px;margin:0;">请手动关闭此页面</p></div></body></html>'
            body = html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)
            return

        elif p == '/bingbu/freeze':
            # GET /bingbu/freeze → 提交冻结提案确认页
            sys.path.insert(0, str(pathlib.Path(__file__).parent))
            from monitor_sentiment import create_proposal, load_sentiment
            sent = load_sentiment()
            proposal = create_proposal(
                action='freeze',
                reason='兵部手动干预：全市场冻结（飞书卡片按钮）',
                details={'pair': '', 'level': 'L4'},
                sentiment=sent,
            )
            html = f'<html><body style="font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#f0f4f8;"><div style="background:#fff;border-radius:12px;padding:40px;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,0.1);"><div style="font-size:64px;">✅</div><h2 style="margin:16px 0 8px;">冻结提案已提交</h2><p style="color:#666;">请在飞书群中批准执行</p><div style="background:#fff3cd;border-radius:8px;padding:16px;margin:16px 0;font-size:20px;"><strong>审批码：{proposal["code"]}</strong></div><p style="color:#999;font-size:13px;margin:0;">15分钟内有效 · 请手动关闭此页面</p></div></body></html>'
            body = html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)
            return

        # ── 尚书省订单审计专用：直连执行（绕过确认页） ──
        elif p.startswith('/bingbu/exit/') or p.startswith('/bingbu/reverse/'):
            # ⚠️ 已禁用直接执行端点！所有平仓/反手必须经过审批页面
            # 重定向到审批确认页
            proposal_id = p.split('/')[-1].strip()
            action_type = 'force_exit' if p.startswith('/bingbu/exit/') else 'reverse'
            redirect_url = f"https://openclaw.tianlu2026.org/bingbu/approve?code={proposal_id}"
            html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>重定向到审批页面</title>
<meta http-equiv="refresh" content="0;url={redirect_url}">
</head>
<body style="font-family:sans-serif;padding:40px;text-align:center;background:#f0f4f8">
<h2>🔄 正在跳转到审批页面...</h2>
<p>所有平仓和反手操作必须经过审批确认。</p>
<p><a href="{redirect_url}">点击这里跳转</a></p>
<script>window.location="{redirect_url}";</script>
</body></html>"""
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return

        elif p.startswith('/bingbu/approve') or p.startswith('/bingbu/reject'):
            # GET /bingbu/approve?code=XXXXXX&pair=XXX  → 渲染确认页面
            from urllib.parse import parse_qs as _pqs
            qs = parse_qs(urlparse(self.path).query)
            code = (qs.get('code', [''])[0]).strip()
            pair = (qs.get('pair', [''])[0]).strip()
            action_type = 'approve' if '/bingbu/approve' in p else 'reject'
            action_label = '批准' if action_type == 'approve' else '拒绝'
            action_color = 'green' if action_type == 'approve' else 'red'
            # 渲染HTML页面（点击后AJAX POST）
            html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>兵部干预审核 - {action_label}</title>
<style>
  body {{ font-family: -apple-system, sans-serif; display:flex; align-items:center; justify-content:center; height:100vh; margin:0; background:#0d1117; color:#e6edf3; }}
  .card {{ background:#161b22; border:1px solid #30363d; border-radius:12px; padding:40px; max-width:480px; width:90%; text-align:center; }}
  .emoji {{ font-size:64px; margin-bottom:16px; }}
  h1 {{ font-size:22px; margin:0 0 12px; }}
  p {{ color:#7d8590; font-size:14px; margin:0 0 28px; }}
  .code {{ font-family:monospace; font-size:20px; color:#f0883e; background:#f0883e22; padding:8px 16px; border-radius:8px; display:inline-block; margin-bottom:24px; }}
  .pair {{ font-family:monospace; font-size:16px; color:#58a6ff; background:#388bfd22; padding:6px 12px; border-radius:6px; display:inline-block; margin-bottom:8px; }}
  .btn {{ background:{'#238636' if action_type=='approve' else '#da3633'}; color:#fff; border:none; padding:14px 40px; font-size:16px; border-radius:8px; cursor:pointer; width:100%; }}
  .btn:hover {{ opacity:0.9; }}
  .msg {{ margin-top:16px; font-size:13px; color:#7d8590; min-height:20px; }}
</style>
</head>
<body>
<div class="card">
  <div class="emoji">{'✅' if action_type=='approve' else '❌'}</div>
  <h1>兵部干预{action_label}</h1>
  <p>审批码 & 交易对</p>
  <div class="code">{code or '未知'}</div>
  <div class="pair">{'📌 ' + pair if pair else ''}</div>
  <button class="btn" onclick="doAction()">{action_label}执行</button>
  <div class="msg" id="msg"></div>
</div>
<script>
async function doAction() {{
  const btn = document.querySelector('.btn');
  const msg = document.getElementById('msg');
  btn.disabled = true;
  btn.textContent = '处理中...';
  try {{
    const r = await fetch('/api/bingbu/{action_type}', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{code: '{code}', pair: '{pair}'}})
    }});
    const d = await r.json();
    if (d.ok) {{
      msg.innerHTML = '<span style="color:#3fb950">{'✅ 操作成功，已发送报告至飞书群' if action_type=='approve' else '✅ 干预已拒绝'}</span>';
      btn.textContent = '已完成';
    }} else {{
      msg.innerHTML = '<span style="color:#f85149">❌ 失败：' + (d.error||'未知错误') + '</span>';
      btn.disabled = false;
      btn.textContent = '重试';
    }}
  }} catch(e) {{
    msg.innerHTML = '<span style="color:#f85149">❌ 网络错误</span>';
    btn.disabled = false;
    btn.textContent = '重试';
  }}
}}
// 如果有 code 参数，自动提交
if ('{code}') doAction();
</script>
</body>
</html>"""
            body = html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(body))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)
            return

        elif p.startswith('/bingbu/add_position/approve') or p.startswith('/bingbu/add_position/reject'):
            # GET /bingbu/add_position/approve?code=XXXXXX  → 加仓审批确认页
            qs = parse_qs(urlparse(self.path).query)
            code = (qs.get('code', [''])[0]).strip()
            action_type = 'approve' if '/approve' in p else 'reject'
            action_label = '批准加仓' if action_type == 'approve' else '拒绝加仓'
            action_color = 'green' if action_type == 'approve' else 'red'
            html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>加仓审批 - {action_label}</title>
<style>
  body {{ font-family: -apple-system, sans-serif; display:flex; align-items:center; justify-content:center; height:100vh; margin:0; background:#0d1117; color:#e6edf3; }}
  .card {{ background:#161b22; border:1px solid #30363d; border-radius:12px; padding:40px; max-width:480px; width:90%; text-align:center; }}
  .emoji {{ font-size:64px; margin-bottom:16px; }}
  h1 {{ font-size:22px; margin:0 0 12px; }}
  p {{ color:#7d8590; font-size:14px; margin:0 0 28px; }}
  .code {{ font-family:monospace; font-size:20px; color:#f0883e; background:#f0883e22; padding:8px 16px; border-radius:8px; display:inline-block; margin-bottom:24px; }}
  .btn {{ background:{'#238636' if action_type=='approve' else '#da3633'}; color:#fff; border:none; padding:14px 40px; font-size:16px; border-radius:8px; cursor:pointer; width:100%; }}
  .btn:hover {{ opacity:0.9; }}
  .msg {{ margin-top:16px; font-size:13px; color:#7d8590; min-height:20px; }}
</style>
</head>
<body>
<div class="card">
  <div class="emoji">{'📈' if action_type=='approve' else '❌'}</div>
  <h1>{action_label}</h1>
  <p>审批码</p>
  <div class="code">{code or '未知'}</div>
  <button class="btn" onclick="doAction()">{action_label}执行</button>
  <div class="msg" id="msg"></div>
</div>
<script>
async function doAction() {{
  const btn = document.querySelector('.btn');
  const msg = document.getElementById('msg');
  btn.disabled = true;
  btn.textContent = '处理中...';
  try {{
    const r = await fetch('/api/bingbu/add_position/{action_type}', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{code: '{code}'}})
    }});
    const d = await r.json();
    if (d.ok) {{
      msg.innerHTML = '<span style="color:#3fb950">{'✅ 加仓已执行，已发送报告至飞书群' if action_type=='approve' else '✅ 加仓提案已拒绝'}</span>';
      btn.textContent = '已完成';
    }} else {{
      msg.innerHTML = '<span style="color:#f85149">❌ 失败：' + (d.error||'未知错误') + '</span>';
      btn.disabled = false;
      btn.textContent = '重试';
    }}
  }} catch(e) {{
    msg.innerHTML = '<span style="color:#f85149">❌ 网络错误</span>';
    btn.disabled = false;
    btn.textContent = '重试';
  }}
}}
if ('{code}') doAction();
</script>
</body>
</html>"""
            body = html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)
            return

        # ── 钦天监 提案审批 GET 确认页 ────────────────────────
        elif p.startswith('/qintianjian/approve/') or p.startswith('/qintianjian/reject/'):
            proposal_id = p.split('/')[-1]
            action_type = 'approve' if '/qintianjian/approve' in p else 'reject'
            action_label = '批准执行' if action_type == 'approve' else '否决'
            is_approve = action_type == 'approve'
            color_val = '#238636' if is_approve else '#da3633'
            emoji_val = '✅' if is_approve else '❌'
            html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>钦天监 · {action_label}</title>
<style>body{{font-family:-apple-system,'PingFang SC',sans-serif;background:#0a0e1a;color:#c8d6f0;min-height:100vh;display:flex;align-items:center;justify-content:center;margin:0}}
.card{{background:#141e35;border:1px solid #1e2d4a;border-radius:16px;padding:48px;max-width:480px;width:90%;text-align:center}}
.icon{{font-size:64px;margin-bottom:16px}}
.title{{font-size:24px;font-weight:700;margin-bottom:12px;color:{color_val}}}
.body{{font-size:14px;color:#5a7090;margin-bottom:24px;line-height:1.6}}
.proposal-id{{font-size:12px;font-family:monospace;color:#5a7090;background:#1a2540;padding:4px 12px;border-radius:4px;display:inline-block;margin-bottom:24px}}
.actions{{display:flex;gap:10px;justify-content:center}}
.btn{{font-size:13px;padding:8px 20px;border-radius:6px;border:1px solid #1e2d4a;background:#141e35;color:#c8d6f0;cursor:pointer;text-decoration:none}}
.btn-primary{{background:#58a6ff;border-color:#58a6ff;color:#000;font-weight:700}}
#msg{{font-size:13px;margin-top:16px;color:#5a7090;min-height:20px}}
</style></head>
<body>
<div class="card">
  <div class="icon">{emoji_val}</div>
  <div class="title">{action_label}确认</div>
  <div class="body" id="msg">正在处理...</div>
  <div class="proposal-id">{proposal_id}</div>
  <div class="actions">
    <button class="btn btn-primary" id="confirmBtn" onclick="doAction()">{action_label}</button>
    <a href="/qintianjian" class="btn">← 返回</a>
  </div>
</div>
<script>
async function doAction() {{
  const btn = document.getElementById('confirmBtn');
  const msg = document.getElementById('msg');
  btn.disabled = true;
  btn.textContent = '处理中...';
  try {{
    const r = await fetch('{p}', {{method:'POST',headers:{{'Content-Type':'application/json'}},cache:'no-store'}});
    const d = await r.json();
    if (d.ok) {{
      msg.innerHTML = '<span style="color:{color_val}">{emoji_val} 操作完成！飞书通知已发送。<br><span style="color:#5a7090">5秒后自动返回...</span></span>';
      btn.style.display = 'none';
      setTimeout(() => window.location.href = '/qintianjian', 5000);
    }} else {{
      msg.innerHTML = '<span style="color:#ff5252">❌ 失败: ' + (d.error || '未知错误') + '</span>';
      btn.disabled = false;
      btn.textContent = '重试';
    }}
  }} catch(e) {{
    msg.innerHTML = '<span style="color:#ff5252">❌ 网络错误</span>';
    btn.disabled = false;
    btn.textContent = '重试';
  }}
}}
doAction();
</script>
</body></html>"""
            body = html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)
            return

        elif p == '/api/review-action':
            # GET /api/review-action?taskId=...&action=approve|reject&comment=...
            # 供飞书卡片按钮回调使用（飞书 open_url 按钮为 GET 请求）
            qs = parse_qs(urlparse(self.path).query)
            task_id = (qs.get('taskId', [''])[0]).strip()
            action = (qs.get('action', [''])[0]).strip()
            comment = (qs.get('comment', [''])[0]).strip()
            if not task_id or action not in ('approve', 'reject', 'modify'):
                html = '<html><body style="font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#f0f4f8;"><div style="background:#fff;border-radius:12px;padding:40px;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,0.1);"><div style="font-size:48px;">❌</div><h2 style="margin:16px 0 8px;">参数错误</h2><p style="color:#666;margin:0 0 24px;">taskId 或 action 无效</p><p style="color:#999;font-size:13px;margin:0;">请手动关闭此页面</p></div></body></html>'
            else:
                result = handle_review_action(task_id, action, comment)
                ok = result.get('ok', False)
                emoji = '✅' if ok else '❌'
                # 标题根据实际结果动态显示，不要只显示动作名
                if ok:
                    label = '已准奏' if action == 'approve' else ('已封驳' if action == 'reject' else '已退回修改')
                else:
                    label = '操作失败'
                color = '#238636' if ok else '#da3633'
                msg = result.get('message', '') if not ok else ''
                # 尝试读取任务详情
                tasks = load_tasks()
                task = next((t for t in tasks if t.get('id') == task_id), None)
                proposal_info = ''
                if task:
                    params = task.get('params', {})
                    proposal_title = params.get('proposal_title', '')
                    detail = params.get('detail', '')
                    if proposal_title:
                        proposal_info += f'<p style="color:#444;margin:0 0 4px;font-size:13px;text-align:left;"><strong>📝 提案：</strong>{proposal_title}</p>'
                    if detail:
                        detail_lines = detail.replace('\\n', '<br>').replace('\n', '<br>')
                        proposal_info += f'<p style="color:#666;margin:0 0 8px;font-size:12px;text-align:left;padding-left:8px;border-left:3px solid #ddd;">{detail_lines}</p>'
                msg_html = f'<p style="color:#da3633;font-size:13px;margin:8px 0 16px;">{msg}</p>' if msg else ''
                html = f'<!DOCTYPE html><html><head><meta charset="UTF-8"><title>{label}</title></head><body style="margin:0;font-family:-apple-system,sans-serif;background:#f0f4f8;min-height:100vh;display:flex;align-items:center;justify-content:center"><div style="background:#fff;border-radius:16px;padding:40px;max-width:480px;width:90%;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,0.12)"><div style="font-size:72px;margin-bottom:16px">{emoji}</div><h2 style="margin:0 0 8px;color:{color}">{label}</h2><p style="color:#888;margin:0 0 4px;font-size:13px">任务ID：{task_id}</p><p style="color:#888;margin:0 0 16px;font-size:13px">动作：{action}</p>{proposal_info}{msg_html}<hr style="border:none;border-top:1px solid #eee;margin:16px 0"><p style="color:#999;font-size:12px;margin:0">页面将自动关闭</p></div><script>setTimeout(function(){{window.close()}},3000)</script></body></html>'
            body = html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)
            return

        elif self._serve_static(p):
            pass  # 已由 _serve_static 处理 (JS/CSS/图片等)
        else:
            # SPA fallback：非 /api/ 路径返回 index.html
            if not p.startswith('/api/'):
                idx = DIST / 'index.html'
                if idx.exists():
                    self.send_file(idx)
                    return
            self.send_error(404)

    def do_POST(self):
        p = urlparse(self.path).path.rstrip('/')
        length = int(self.headers.get('Content-Length', 0))
        if length > MAX_REQUEST_BODY:
            self.send_json({'ok': False, 'error': f'Request body too large (max {MAX_REQUEST_BODY} bytes)'}, 413)
            return
        raw = self.rfile.read(length) if length else b''
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            self.send_json({'ok': False, 'error': 'invalid JSON'}, 400)
            return

        if p == '/api/morning-config':
            # 字段校验
            if not isinstance(body, dict):
                self.send_json({'ok': False, 'error': '请求体必须是 JSON 对象'}, 400)
                return
            allowed_keys = {'categories', 'keywords', 'custom_feeds', 'feishu_webhook'}
            unknown = set(body.keys()) - allowed_keys
            if unknown:
                self.send_json({'ok': False, 'error': f'未知字段: {", ".join(unknown)}'}, 400)
                return
            if 'categories' in body and not isinstance(body['categories'], list):
                self.send_json({'ok': False, 'error': 'categories 必须是数组'}, 400)
                return
            if 'keywords' in body and not isinstance(body['keywords'], list):
                self.send_json({'ok': False, 'error': 'keywords 必须是数组'}, 400)
                return
            # 飞书 Webhook 校验
            webhook = body.get('feishu_webhook', '').strip()
            if webhook and not validate_url(webhook, allowed_schemes=('https',), allowed_domains=('open.feishu.cn', 'open.larksuite.com')):
                self.send_json({'ok': False, 'error': '飞书 Webhook URL 无效，仅支持 https://open.feishu.cn 或 open.larksuite.com 域名'}, 400)
                return
            cfg_path = DATA / 'morning_brief_config.json'
            cfg_path.write_text(json.dumps(body, ensure_ascii=False, indent=2))
            self.send_json({'ok': True, 'message': '订阅配置已保存'})
            return

        if p == '/api/scheduler-scan':
            threshold_sec = body.get('thresholdSec', 180)
            try:
                result = handle_scheduler_scan(threshold_sec)
                self.send_json(result)
            except Exception as e:
                self.send_json({'ok': False, 'error': f'scheduler scan failed: {e}'}, 500)
            return

        if p == '/api/repair-flow-order':
            try:
                self.send_json(handle_repair_flow_order())
            except Exception as e:
                self.send_json({'ok': False, 'error': f'repair flow order failed: {e}'}, 500)
            return

        if p == '/api/scheduler-retry':
            task_id = body.get('taskId', '').strip()
            reason = body.get('reason', '').strip()
            if not task_id:
                self.send_json({'ok': False, 'error': 'taskId required'}, 400)
                return
            self.send_json(handle_scheduler_retry(task_id, reason))
            return

        if p == '/api/agent-task/create':
            result = handle_agent_task_create(
                title=body.get('title',''),
                dept=body.get('dept','尚书省'),
                official=body.get('official','尚书令'),
                description=body.get('description',''),
                priority=body.get('priority','normal'),
                source_agent=body.get('source_agent',''),
            )
            self.send_json(result)
            return

        if p == '/api/agent-task/update':
            result = handle_agent_task_update(
                task_id=body.get('task_id',''),
                state=body.get('state'),
                output=body.get('output',''),
                now=body.get('now',''),
                remark=body.get('remark',''),
            )
            self.send_json(result)
            return

        if p == '/api/scheduler-escalate':
            task_id = body.get('taskId', '').strip()
            reason = body.get('reason', '').strip()
            if not task_id:
                self.send_json({'ok': False, 'error': 'taskId required'}, 400)
                return
            self.send_json(handle_scheduler_escalate(task_id, reason))
            return

        if p == '/api/scheduler-rollback':
            task_id = body.get('taskId', '').strip()
            reason = body.get('reason', '').strip()
            if not task_id:
                self.send_json({'ok': False, 'error': 'taskId required'}, 400)
                return
            self.send_json(handle_scheduler_rollback(task_id, reason))
            return

        if p == '/api/morning-brief/refresh':
            force = body.get('force', True)  # 从看板手动触发默认强制
            def do_refresh():
                try:
                    cmd = ['python3', str(SCRIPTS / 'fetch_morning_news.py')]
                    if force:
                        cmd.append('--force')
                    subprocess.run(cmd, timeout=120)
                    push_to_feishu()
                except Exception as e:
                    print(f'[refresh error] {e}', file=sys.stderr)
            threading.Thread(target=do_refresh, daemon=True).start()
            self.send_json({'ok': True, 'message': '采集已触发，约30-60秒后刷新'})
            return

        if p == '/api/add-skill':
            agent_id = body.get('agentId', '').strip()
            skill_name = body.get('skillName', body.get('name', '')).strip()
            desc = body.get('description', '').strip() or skill_name
            trigger = body.get('trigger', '').strip()
            if not agent_id or not skill_name:
                self.send_json({'ok': False, 'error': 'agentId and skillName required'}, 400)
                return
            result = add_skill_to_agent(agent_id, skill_name, desc, trigger)
            self.send_json(result)
            return

        if p == '/api/add-remote-skill':
            agent_id = body.get('agentId', '').strip()
            skill_name = body.get('skillName', '').strip()
            source_url = body.get('sourceUrl', '').strip()
            description = body.get('description', '').strip()
            if not agent_id or not skill_name or not source_url:
                self.send_json({'ok': False, 'error': 'agentId, skillName, and sourceUrl required'}, 400)
                return
            result = add_remote_skill(agent_id, skill_name, source_url, description)
            self.send_json(result)
            return

        if p == '/api/remote-skills-list':
            result = get_remote_skills_list()
            self.send_json(result)
            return

        if p == '/api/update-remote-skill':
            agent_id = body.get('agentId', '').strip()
            skill_name = body.get('skillName', '').strip()
            if not agent_id or not skill_name:
                self.send_json({'ok': False, 'error': 'agentId and skillName required'}, 400)
                return
            result = update_remote_skill(agent_id, skill_name)
            self.send_json(result)
            return

        if p == '/api/remove-remote-skill':
            agent_id = body.get('agentId', '').strip()
            skill_name = body.get('skillName', '').strip()
            if not agent_id or not skill_name:
                self.send_json({'ok': False, 'error': 'agentId and skillName required'}, 400)
                return
            result = remove_remote_skill(agent_id, skill_name)
            self.send_json(result)
            return

        if p == '/api/task-action':
            task_id = body.get('taskId', '').strip()
            action = body.get('action', '').strip()  # stop, cancel, resume
            reason = body.get('reason', '').strip() or f'皇上从看板{action}'
            if not task_id or action not in ('stop', 'cancel', 'resume'):
                self.send_json({'ok': False, 'error': 'taskId and action(stop/cancel/resume) required'}, 400)
                return
            result = handle_task_action(task_id, action, reason)
            self.send_json(result)
            return

        if p == '/api/archive-task':
            task_id = body.get('taskId', '').strip() if body.get('taskId') else ''
            archived = body.get('archived', True)
            archive_all = body.get('archiveAllDone', False)
            if not task_id and not archive_all:
                self.send_json({'ok': False, 'error': 'taskId or archiveAllDone required'}, 400)
                return
            result = handle_archive_task(task_id, archived, archive_all)
            self.send_json(result)
            return

        if p == '/api/task-todos':
            task_id = body.get('taskId', '').strip()
            todos = body.get('todos', [])  # [{id, title, status}]
            if not task_id:
                self.send_json({'ok': False, 'error': 'taskId required'}, 400)
                return
            # todos 输入校验
            if not isinstance(todos, list) or len(todos) > 200:
                self.send_json({'ok': False, 'error': 'todos must be a list (max 200 items)'}, 400)
                return
            valid_statuses = {'not-started', 'in-progress', 'completed'}
            for td in todos:
                if not isinstance(td, dict) or 'id' not in td or 'title' not in td:
                    self.send_json({'ok': False, 'error': 'each todo must have id and title'}, 400)
                    return
                if td.get('status', 'not-started') not in valid_statuses:
                    td['status'] = 'not-started'
            result = update_task_todos(task_id, todos)
            self.send_json(result)
            return

        if p == '/api/create-task':
            title = body.get('title', '').strip()
            org = body.get('org', '中书省').strip()
            official = body.get('official', '中书令').strip()
            priority = body.get('priority', 'normal').strip()
            template_id = body.get('templateId', '')
            params = body.get('params', {})
            if not title:
                self.send_json({'ok': False, 'error': 'title required'}, 400)
                return
            target_dept = body.get('targetDept', '').strip()
            result = handle_create_task(title, org, official, priority, template_id, params, target_dept)
            self.send_json(result)
            return

        if p == '/api/register-review-task':
            # POST {taskId, title, fromDept, proposalTitle, detail, extraParams?: object}
            # 供通知发送方提前注册任务，让审批按钮能正确回调
            task_id = body.get('taskId', '').strip()
            title = body.get('title', '').strip()
            from_dept = body.get('fromDept', '').strip() or '中书省'
            proposal_title = body.get('proposalTitle', '').strip()
            detail = body.get('detail', '').strip()
            extra_params = body.get('extraParams', None)
            if not task_id or not title:
                self.send_json({'ok': False, 'error': 'taskId and title required'}, 400)
                return
            result = handle_register_review_task(task_id, title, from_dept, proposal_title, detail, extra_params)
            self.send_json(result)
            return


            task_id = body.get('taskId', '').strip()
            action = body.get('action', '').strip()  # approve, reject, modify
            comment = body.get('comment', '').strip()
            if not task_id or action not in ('approve', 'reject', 'modify'):
                self.send_json({'ok': False, 'error': 'taskId and action(approve/reject/modify) required'}, 400)
                return
            result = handle_review_action(task_id, action, comment)
            self.send_json(result)
            return

        if p == '/api/advance-state':
            task_id = body.get('taskId', '').strip()
            comment = body.get('comment', '').strip()
            if not task_id:
                self.send_json({'ok': False, 'error': 'taskId required'}, 400)
                return
            result = handle_advance_state(task_id, comment)
            self.send_json(result)
            return

        if p == '/api/agent-wake':
            agent_id = body.get('agentId', '').strip()
            message = body.get('message', '').strip()
            if not agent_id:
                self.send_json({'ok': False, 'error': 'agentId required'}, 400)
                return
            result = wake_agent(agent_id, message)
            self.send_json(result)
            return

        if p == '/api/set-model':
            agent_id = body.get('agentId', '').strip()
            model = body.get('model', '').strip()
            if not agent_id or not model:
                self.send_json({'ok': False, 'error': 'agentId and model required'}, 400)
                return

            # Write to pending (atomic)
            pending_path = DATA / 'pending_model_changes.json'
            def update_pending(current):
                current = [x for x in current if x.get('agentId') != agent_id]
                current.append({'agentId': agent_id, 'model': model})
                return current
            atomic_json_update(pending_path, update_pending, [])

            # Async apply
            def apply_async():
                try:
                    subprocess.run(['python3', str(SCRIPTS / 'apply_model_changes.py')], timeout=30)
                    subprocess.run(['python3', str(SCRIPTS / 'sync_agent_config.py')], timeout=10)
                except Exception as e:
                    print(f'[apply error] {e}', file=sys.stderr)

            threading.Thread(target=apply_async, daemon=True).start()
            self.send_json({'ok': True, 'message': f'Queued: {agent_id} → {model}'})

        # Fix #139: 设置派发渠道（feishu/telegram/wecom/signal/tui）
        elif p == '/api/set-dispatch-channel':
            channel = body.get('channel', '').strip()
            allowed = {'feishu', 'telegram', 'wecom', 'signal', 'tui', 'discord', 'slack'}
            if not channel or channel not in allowed:
                self.send_json({'ok': False, 'error': f'channel must be one of: {", ".join(sorted(allowed))}'}, 400)
                return
            def _set_channel(cfg):
                cfg['dispatchChannel'] = channel
                return cfg
            atomic_json_update(DATA / 'agent_config.json', _set_channel, {})
            self.send_json({'ok': True, 'message': f'派发渠道已切换为 {channel}'})

        # ── 朝堂议政 POST ──
        elif p == '/api/court-discuss/start':
            topic = body.get('topic', '').strip()
            officials = body.get('officials', [])
            task_id = body.get('taskId', '').strip()
            if not topic:
                self.send_json({'ok': False, 'error': 'topic required'}, 400)
                return
            if not officials or not isinstance(officials, list):
                self.send_json({'ok': False, 'error': 'officials list required'}, 400)
                return
            # 校验官员 ID
            valid_ids = set(CD_PROFILES.keys())
            officials = [o for o in officials if o in valid_ids]
            if len(officials) < 2:
                self.send_json({'ok': False, 'error': '至少选择2位官员'}, 400)
                return
            self.send_json(cd_create(topic, officials, task_id))

        elif p == '/api/court-discuss/advance':
            sid = body.get('sessionId', '').strip()
            user_msg = body.get('userMessage', '').strip() or None
            decree = body.get('decree', '').strip() or None
            if not sid:
                self.send_json({'ok': False, 'error': 'sessionId required'}, 400)
                return
            self.send_json(cd_advance(sid, user_msg, decree))

        elif p == '/api/court-discuss/conclude':
            sid = body.get('sessionId', '').strip()
            if not sid:
                self.send_json({'ok': False, 'error': 'sessionId required'}, 400)
                return
            self.send_json(cd_conclude(sid))

        elif p == '/api/court-discuss/destroy':
            sid = body.get('sessionId', '').strip()
            if sid:
                cd_destroy(sid)
            self.send_json({'ok': True})
        # ── 钦天监顾问记录 ──
        elif p == '/api/advisor/save':
            hist_file = pathlib.Path.home() / 'freqtrade/scripts/advisor_history.json'
            try:
                records = []
                if hist_file.exists():
                    with open(hist_file) as f:
                        records = json.load(f)
            except Exception:
                records = []
            records.append(body)
            with open(hist_file, 'w') as f:
                json.dump(records, f, indent=2, ensure_ascii=False)
            self.send_json({'ok': True, 'saved': len(records)})

        # ── 兵部精准干预 POST 接口（审核制） ──
        elif p == '/api/bingbu/inject_long_pair':
            # POST { pair: "ETH/USDT", confidence: 80 }
            pair = (body.get('pair') or '').strip()
            if not pair:
                self.send_json({'ok': False, 'error': 'pair required'}, 400)
                return
            confidence = int(body.get('confidence', 80))
            sys.path.insert(0, str(pathlib.Path(__file__).parent))
            from monitor_sentiment import create_proposal, load_sentiment
            sent = load_sentiment()
            proposal = create_proposal(
                action='inject_long_pair',
                reason=f'兵部精准干预：指定{pair}注入做多信号，信心{confidence}（经审核后执行）',
                details={'pair': pair, 'confidence': confidence},
                sentiment=sent,
            )
            self.send_json({
                'ok': True,
                'type': 'proposal',
                'message': '已提交飞书审核，等待批准后执行',
                'proposal_id': proposal['id'],
                'code': proposal['code'],
                'expires_at': proposal['expires_at'],
            })

        elif p == '/api/bingbu/inject_short_pair':
            pair = (body.get('pair') or '').strip()
            if not pair:
                self.send_json({'ok': False, 'error': 'pair required'}, 400)
                return
            confidence = int(body.get('confidence', 80))
            sys.path.insert(0, str(pathlib.Path(__file__).parent))
            from monitor_sentiment import create_proposal, load_sentiment
            sent = load_sentiment()
            proposal = create_proposal(
                action='inject_short_pair',
                reason=f'兵部精准干预：指定{pair}注入做空信号，信心{confidence}（经审核后执行）',
                details={'pair': pair, 'confidence': confidence},
                sentiment=sent,
            )
            self.send_json({
                'ok': True,
                'type': 'proposal',
                'message': '已提交飞书审核，等待批准后执行',
                'proposal_id': proposal['id'],
                'code': proposal['code'],
                'expires_at': proposal['expires_at'],
            })

        elif p == '/api/bingbu/force_exit_pair':
            # POST { pair: "ETH/USDT" }
            pair = (body.get('pair') or '').strip()
            if not pair:
                self.send_json({'ok': False, 'error': 'pair required'}, 400)
                return
            sys.path.insert(0, str(pathlib.Path(__file__).parent))
            from monitor_sentiment import create_proposal, load_sentiment
            sent = load_sentiment()
            proposal = create_proposal(
                action='force_exit_pair',
                reason=f'兵部精准干预：指定交易对{pair}强制平仓（多空全平）',
                details={'pair': pair},
                sentiment=sent,
            )
            self.send_json({
                'ok': True,
                'type': 'proposal',
                'message': '已提交飞书审核，等待批准后执行',
                'proposal_id': proposal['id'],
                'code': proposal['code'],
                'expires_at': proposal['expires_at'],
            })

        elif p == '/api/bingbu/emergency_exit_all':
            sys.path.insert(0, str(pathlib.Path(__file__).parent))
            from monitor_sentiment import create_proposal, load_sentiment
            sent = load_sentiment()
            proposal = create_proposal(
                action='emergency_exit_all',
                reason='兵部精准干预：全市场双向强平（紧急接管）',
                details={},
                sentiment=sent,
            )
            self.send_json({
                'ok': True,
                'type': 'proposal',
                'message': '已提交飞书审核，等待批准后执行',
                'proposal_id': proposal['id'],
                'code': proposal['code'],
                'expires_at': proposal['expires_at'],
            })

        elif p == '/api/bingbu/freeze_pair':
            # POST { pair: "ETH/USDT", level: "L2" } 或 POST {} 全市场冻结
            # level: L1(5min) / L2(15min) / L3(30min) / L4(手动)
            pair = (body.get('pair') or '').strip()
            level = body.get('level', 'L4').upper()
            if level not in ('L1', 'L2', 'L3', 'L4'):
                level = 'L4'
            sys.path.insert(0, str(pathlib.Path(__file__).parent))
            from monitor_sentiment import create_proposal, load_sentiment
            sent = load_sentiment()
            action = 'freeze_pair' if pair else 'freeze'
            LEVEL_LABEL = {'L1': '🟡 L1(5分钟)', 'L2': '🟠 L2(15分钟)', 'L3': '🔴 L3(30分钟)', 'L4': '⚫ L4(手动)'}
            scope = f'冻结交易对 {pair}' if pair else '全市场冻结'
            proposal = create_proposal(
                action=action,
                reason=f'兵部精准干预：{scope} [{LEVEL_LABEL.get(level, level)}]',
                details={'pair': pair, 'level': level},
                sentiment=sent,
            )
            self.send_json({
                'ok': True,
                'type': 'proposal',
                'message': '已提交飞书审核，等待批准后执行',
                'proposal_id': proposal['id'],
                'code': proposal['code'],
                'expires_at': proposal['expires_at'],
            })

        elif p == '/api/bingbu/unfreeze':
            # 解除冻结（飞书通知即可，实际直接执行，冻结是保护性操作）
            pair = (body.get('pair') or '').strip()
            freeze_file = pathlib.Path.home() / 'edict/data/bingbu_freeze.json'
            if freeze_file.exists():
                import json as _json
                fd = _json.loads(freeze_file.read_text())
                if pair:
                    fp = fd.get('frozen_pairs', [])
                    if pair in fp:
                        fp.remove(pair)
                        fd['frozen_pairs'] = fp
                        if not fd.get('frozen') and not fp:
                            fd['frozen'] = False
                else:
                    fd = {'frozen': False, 'frozen_pairs': [], 'timestamp': datetime.datetime.now().isoformat()}
                freeze_file.write_text(_json.dumps(fd, indent=2))
            # 全局解冻时同步清除 force_executed，防止 bingbu_patrol 继续静默
            if not pair:
                state_file = pathlib.Path.home() / 'edict/data/bingbu_intervention_state.json'
                if state_file.exists():
                    import json as _json2
                    try:
                        st = _json2.loads(state_file.read_text())
                    except Exception:
                        st = {}
                    st['force_executed'] = False
                    st['force_executed_at'] = ''
                    st['force_executed_alert_id'] = ''
                    state_file.write_text(_json2.dumps(st, indent=2))
            sys.path.insert(0, str(pathlib.Path(__file__).parent))
            from monitor_sentiment import load_sentiment, add_intervention as iv_add
            sent = load_sentiment()
            pair_suffix = (' ' + pair) if pair else ''
            iv_add('unfreeze', f'解除冻结{pair_suffix}', sent, 'success', targets=[{'pair': pair}] if pair else [])
            self.send_json({'ok': True, 'action': 'unfreeze', 'pair': pair or 'global', 'result': 'success'})

        elif p == '/api/bingbu/approve':
            # POST { code: "BS-SR-...", pair: "DOGE/USDT" } 批准干预提案
            code = (body.get('code') or '').strip()
            pair = (body.get('pair') or '').strip()
            if not code:
                self.send_json({'ok': False, 'error': 'code required'}, 400)
                return
            try:
                sys.path.insert(0, str(pathlib.Path(__file__).parent))
                from monitor_sentiment import approve_proposal
                result = approve_proposal(code, pair)
                if result.get('ok'):
                    self.send_json({**result, 'message': '干预已执行，已发送执行报告至飞书群'})
                else:
                    self.send_json(result, 400)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_json({'ok': False, 'error': f'server error: {e}'}, 500)

        elif p == '/api/bingbu/dca_add':
            # POST { trade_id, amount_pct, pair } → 动态加仓（路由到具体机器人）
            trade_id = str(body.get('trade_id', '')).strip()
            amount_pct = float(body.get('amount_pct', 0))
            pair = (body.get('pair') or '').strip()
            if not trade_id or amount_pct <= 0:
                self.send_json({'error': 'trade_id and amount_pct required'}, 400)
                return
            try:
                # 1. 从各机器人持仓中找到对应的 port
                target_port = None
                target_stake = None
                target_side = None
                target_pair = None
                for port, cfg in BINGBU_FREQTRADE.items():
                    try:
                        r = requests.get(
                            f"{cfg['host']}/api/v1/status",
                            headers={"Authorization": cfg["auth"]},
                            timeout=5,
                        )
                        if r.status_code == 200:
                            for pos in r.json():
                                if str(pos.get('trade_id', '')) == str(trade_id) and pos.get('is_open'):
                                    target_port = port
                                    target_stake = float(pos.get('stake_amount', 0))
                                    target_side = 'short' if pos.get('is_short') else 'long'
                                    target_pair = pos.get('pair', '')
                                    break
                    except Exception:
                        pass
                    if target_port:
                        break

                if not target_port:
                    self.send_json({'error': f'未找到持仓 trade_id={trade_id}，可能已平'}, 404)
                    return

                # 2. 计算追加金额
                add_stake = round(target_stake * amount_pct / 100, 2)
                cfg = BINGBU_FREQTRADE[target_port]

                # 3. 调用 forceenter 追加仓位
                enter_resp = requests.post(
                    f"{cfg['host']}/api/v1/forceenter",
                    headers={"Authorization": cfg["auth"], "Content-Type": "application/json"},
                    json={
                        "pair": target_pair,
                        "side": target_side,
                        "stakeamount": add_stake,
                        "ordertype": "market",
                    },
                    timeout=10,
                )
                if enter_resp.ok:
                    result_data = enter_resp.json()
                    self.send_json({
                        "ok": True,
                        "message": f"加仓成功，约 ${add_stake}",
                        "trade_id": trade_id,
                        "port": target_port,
                        "add_stake": add_stake,
                        "result": result_data,
                    })
                else:
                    err = enter_resp.json().get('error', enter_resp.text)
                    self.send_json({'error': f'加仓失败: {err}'}, 502)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_json({'error': f'server error: {e}'}, 500)

        elif p == '/api/bingbu/reject':
            # POST { code: "123456" } 拒绝干预提案
            code = (body.get('code') or '').strip()
            if not code:
                self.send_json({'ok': False, 'error': 'code required'}, 400)
                return
            try:
                sys.path.insert(0, str(pathlib.Path(__file__).parent))
                from monitor_sentiment import reject_proposal
                result = reject_proposal(code)
                if result.get('ok'):
                    self.send_json({**result, 'message': '干预已拒绝'})
                else:
                    self.send_json(result, 400)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_json({'ok': False, 'error': f'server error: {e}'}, 500)

        elif p == '/api/bingbu/add_position/approve':
            # POST { code: "AP-XXXXXX" } 批准加仓提案
            code = (body.get('code') or '').strip()
            if not code:
                self.send_json({'ok': False, 'error': 'code required'}, 400)
                return
            try:
                import json as _json2
                from pathlib import Path as _path2
                PROPOSALS_FILE = _path2.home() / 'edict/data/add_position_proposals.json'
                proposals = []
                if PROPOSALS_FILE.exists():
                    proposals = _json2.loads(PROPOSALS_FILE.read_text())

                target = None
                for p_item in proposals:
                    if p_item.get('id') == code and p_item.get('status') == 'pending':
                        target = p_item
                        break

                if not target:
                    self.send_json({'ok': False, 'error': f'未找到待审批的加仓提案: {code}'}, 400)
                    return

                # 执行加仓
                sys.path.insert(0, str(pathlib.Path(__file__).parent))
                from monitor_sentiment import _do_add_position
                result = _do_add_position(
                    pair=target['pair'],
                    port=target.get('port'),
                    side=target['side'],
                    stake_pct=target.get('stake_pct', 0.30),
                    leverage=target.get('leverage', 1),
                )

                # 更新提案状态
                for p_item in proposals:
                    if p_item.get('id') == code:
                        p_item['status'] = 'executed'
                        p_item['executed_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        p_item['result'] = result
                        break
                PROPOSALS_FILE.write_text(_json2.dumps(proposals, ensure_ascii=False, indent=2))

                if result.get('success'):
                    # 发飞书执行通知
                    try:
                        details = result.get('details', '')
                        pair_label = target.get('pair', '?')
                        side_label = target.get('side', '?')
                        stake_pct = target.get('stake_pct', 0)
                        port_label = target.get('port', '?')
                        card_payload = {
                            "msg_type": "interactive",
                            "card": {
                                "header": {
                                    "title": {"tag": "plain_text", "content": f"✅ 加仓已执行 · {pair_label}"},
                                    "template": "green"
                                },
                                "elements": [
                                    {"tag": "div", "text": {"tag": "lark_md", "content": f"**交易对：** {pair_label}\n**方向：** {side_label}\n**加仓比例：** {stake_pct*100:.0f}%\n**执行端口：** {port_label}\n**详情：** {details}"}}
                                ]
                            }
                        }
                        import urllib.request as _ur
                        req = _ur.Request(
                            "https://open.feishu.cn/open-apis/bot/v2/hook/e6151d8f-bed3-474f-af25-9a8b130900b0",
                            data=json.dumps(card_payload).encode('utf-8'),
                            headers={"Content-Type": "application/json"},
                        )
                        with _ur.urlopen(req, timeout=10) as _r2:
                            pass
                    except Exception as _nf:
                        print(f"[add_position approve] 飞书通知失败: {_nf}")

                    self.send_json({'ok': True, 'action': 'add_position', 'result': result,
                                   'message': '加仓已执行，已发送执行报告至飞书群'})
                else:
                    self.send_json({'ok': False, 'error': result.get('details', '执行失败')}, 400)
            except Exception as e:
                import traceback; traceback.print_exc()
                self.send_json({'ok': False, 'error': f'server error: {e}'}, 500)

        elif p == '/api/bingbu/add_position/reject':
            # POST { code: "AP-XXXXXX" } 拒绝加仓提案
            code = (body.get('code') or '').strip()
            if not code:
                self.send_json({'ok': False, 'error': 'code required'}, 400)
                return
            try:
                import json as _json2
                from pathlib import Path as _path2
                PROPOSALS_FILE = _path2.home() / 'edict/data/add_position_proposals.json'
                proposals = []
                if PROPOSALS_FILE.exists():
                    proposals = _json2.loads(PROPOSALS_FILE.read_text())

                found = False
                for p_item in proposals:
                    if p_item.get('id') == code and p_item.get('status') == 'pending':
                        p_item['status'] = 'rejected'
                        p_item['rejected_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        found = True
                        break

                if found:
                    PROPOSALS_FILE.write_text(_json2.dumps(proposals, ensure_ascii=False, indent=2))
                    self.send_json({'ok': True, 'message': '加仓提案已拒绝'})
                else:
                    self.send_json({'ok': False, 'error': f'未找到待审批的加仓提案: {code}'}, 400)
            except Exception as e:
                import traceback; traceback.print_exc()
                self.send_json({'ok': False, 'error': f'server error: {e}'}, 500)

        elif p == '/api/bingbu/proposals':
            # GET 当前待审批提案列表
            sys.path.insert(0, str(pathlib.Path(__file__).parent))
            from monitor_sentiment import load_proposals
            proposals = load_proposals()
            active = [p for p in proposals if p['status'] == 'pending']
            self.send_json({'proposals': active, 'count': len(active)})

        elif p == '/api/bingbu/check_sentiment':
            # POST 黑天鹅舆情审核检查
            # 发现黑天鹅则推送审核提案，飞书批准后才执行
            sys.path.insert(0, str(pathlib.Path(__file__).parent))
            from monitor_sentiment import check_sentiment_proposal
            result = check_sentiment_proposal()
            self.send_json(result)

        # ── 钦天监 提案审批 POST ────────────────────────────
        elif p.startswith('/qintianjian/approve/') or p.startswith('/qintianjian/reject/'):
            proposal_id = p.split('/')[-1]
            action_type = 'approve' if '/qintianjian/approve' in p else 'reject'
            try:
                sys.path.insert(0, str(BASE.parent / 'qintianjian'))
                if action_type == 'approve':
                    from rule_engine import approve_proposal
                    result = approve_proposal(proposal_id)
                else:
                    from rule_engine import reject_proposal
                    result = reject_proposal(proposal_id)
                if result.get('ok') and action_type == 'approve':
                    proposal = result.get('proposal', {})
                    action = proposal.get('action', '')
                    rule_id = proposal.get('rule_id', '')
                    sys.path.insert(0, str(pathlib.Path(__file__).parent))
                    action_map = {
                        'freeze': '/api/bingbu/freeze_pair',
                        'force_close': '/api/bingbu/force_exit_pair',
                        'pause_trading': '/api/bingbu/freeze_pair',
                        'force_stop_loss': '/api/bingbu/force_exit_pair',
                    }
                    exec_path = action_map.get(action)
                    if exec_path and rule_id in ('R001','R002','R003','R004'):
                        import requests as _req
                        sent_file = pathlib.Path.home() / 'edict/data/bingbu_sentiment.json'
                        sent = json.loads(sent_file.read_text()) if sent_file.exists() else {}
                        post_data = {
                            'action': 'freeze' if 'freeze' in action else action,
                            'reason': f'钦天监规则触发: {rule_id} {proposal.get("title","")}',
                            'details': {'rule_id': rule_id, 'qintianjian': True, 'proposal_id': proposal_id},
                            'sentiment': sent,
                        }
                        if exec_path == '/api/bingbu/freeze_pair':
                            _req.post('http://127.0.0.1:7891/api/bingbu/freeze_pair', json=post_data, timeout=10)
                        elif exec_path == '/api/bingbu/force_exit_pair':
                            pos = proposal.get('data', {}).get('position', {})
                            pair = pos.get('symbol', '')
                            if pair:
                                _req.post('http://127.0.0.1:7891/api/bingbu/force_exit_pair',
                                          json={'pair': pair, 'reason': post_data['reason'], 'details': post_data['details'], 'sentiment': sent}, timeout=10)
                self.send_json(result)
            except Exception as e:
                import traceback; traceback.print_exc()
                self.send_json({'ok': False, 'error': str(e)}, 500)

        # ── 机器人交易干预 API ──────────────────────────────
        elif p == '/api/bots/force_entry':
            port = int(body.get('port', 0))
            pair = str(body.get('pair', ''))
            side = str(body.get('side', 'long'))
            _auth = lambda u, pw: 'Basic ' + base64.b64encode(f'{u}:{pw}'.encode()).decode()
            BOT_AUTH = {
                9090: ('freqtrade', 'freqtrade'), 9091: ('freqtrade', 'freqtrade'), 9092: ('freqtrade', 'freqtrade'),
                9093: ('admin', 'Xy@06130822'), 9094: ('admin', 'Xy@06130822'),
                9095: ('admin', 'Xy@06130822'), 9096: ('admin', 'Xy@06130822'), 9097: ('admin', 'Xy@06130822'),
            }
            if port not in BOT_AUTH:
                self.send_json({'ok': False, 'error': f'Unknown port {port}'}, 400)
                return
            user, pwd = BOT_AUTH[port]
            try:
                r = requests.post(
                    f'http://127.0.0.1:{port}/api/v1/force_entry',
                    headers={'Authorization': _auth(user, pwd), 'Content-Type': 'application/json'},
                    json={'pair': pair, 'side': side, 'price': None, 'amount': None},
                    timeout=15,
                )
                data = r.json()
                if r.status_code == 200 and data.get('result'):
                    self.send_json({'ok': True, 'trade_id': data.get('trade_id'), 'msg': f'{pair} {side} 开仓成功'})
                else:
                    self.send_json({'ok': False, 'error': data.get('reason') or data.get('msg') or '开仓失败'}, 400)
            except Exception as e:
                self.send_json({'ok': False, 'error': str(e)}, 500)

        elif p == '/api/bots/force_exit':
            port = int(body.get('port', 0))
            trade_id = str(body.get('trade_id', ''))
            _auth = lambda u, pw: 'Basic ' + base64.b64encode(f'{u}:{pw}'.encode()).decode()
            BOT_AUTH = {
                9090: ('freqtrade', 'freqtrade'), 9091: ('freqtrade', 'freqtrade'), 9092: ('freqtrade', 'freqtrade'),
                9093: ('admin', 'Xy@06130822'), 9094: ('admin', 'Xy@06130822'),
                9095: ('admin', 'Xy@06130822'), 9096: ('admin', 'Xy@06130822'), 9097: ('admin', 'Xy@06130822'),
            }
            if port not in BOT_AUTH:
                self.send_json({'ok': False, 'error': f'Unknown port {port}'}, 400)
                return
            user, pwd = BOT_AUTH[port]
            try:
                r = requests.post(
                    f'http://127.0.0.1:{port}/api/v1/force_exit',
                    headers={'Authorization': _auth(user, pwd), 'Content-Type': 'application/json'},
                    json={'tradeid': trade_id, 'ordertype': 'market'},
                    timeout=15,
                )
                data = r.json()
                if r.status_code == 200 and data.get('result'):
                    self.send_json({'ok': True, 'msg': '平仓成功'})
                else:
                    self.send_json({'ok': False, 'error': data.get('reason') or data.get('msg') or '平仓失败'}, 400)
            except Exception as e:
                self.send_json({'ok': False, 'error': str(e)}, 500)

        else:
            self.send_error(404)


def main():
    parser = argparse.ArgumentParser(description='三省六部看板服务器')
    parser.add_argument('--port', type=int, default=7891)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--cors', default=None, help='Allowed CORS origin (default: reflect request Origin header)')
    parser.add_argument('--public-url', default='', help='外网访问基础URL（cloudflared隧道等）')
    args = parser.parse_args()

    global ALLOWED_ORIGIN, BINGBU_PUBLIC_BASE
    # 优先用 --cors 显式指定，否则当有 --public-url 时允许全部 origin
    if args.cors is not None:
        ALLOWED_ORIGIN = args.cors
    elif args.public_url:
        ALLOWED_ORIGIN = '*'
    else:
        ALLOWED_ORIGIN = None
    BINGBU_PUBLIC_BASE = args.public_url.rstrip('/')
    os.environ['BINGBU_PUBLIC_BASE'] = BINGBU_PUBLIC_BASE
    # 写入共享配置文件，供 monitor_sentiment 等独立进程读取
    pub_base_file = pathlib.Path(__file__).parent / "data" / ".public_base_url"
    pub_base_file.parent.mkdir(parents=True, exist_ok=True)
    pub_base_file.write_text(BINGBU_PUBLIC_BASE)

    class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
        """每请求独立线程，彻底消除顺序阻塞"""
        daemon_threads = True
        allow_reuse_address = True

    server = ThreadedHTTPServer((args.host, args.port), Handler)
    log.info(f'三省六部看板启动 → http://{args.host}:{args.port}')
    print(f'   按 Ctrl+C 停止')

    # 启动恢复：重新派发上次被 kill 中断的 queued 任务
    threading.Timer(3.0, _startup_recover_queued_dispatches).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')


if __name__ == '__main__':
    main()
