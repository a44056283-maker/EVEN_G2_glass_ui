#!/usr/bin/env python3
import json, pathlib, datetime, logging
from file_lock import atomic_json_write, atomic_json_read
from utils import read_json

log = logging.getLogger('refresh')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s', datefmt='%H:%M:%S')

BASE = pathlib.Path(__file__).parent.parent
DATA = BASE / 'data'
OCLAW_HOME = pathlib.Path.home() / '.openclaw'


def read_work_plan(agent_id: str) -> dict:
    """读取各省代理的工作计划文件"""
    wp_path = OCLAW_HOME / f'workspace-{agent_id}' / 'WORK_PLAN.md'
    rules_path = OCLAW_HOME / f'workspace-{agent_id}' / 'RULES.md'
    
    result = {"workPlan": None, "rules": None, "workPlanExists": False, "rulesExists": False}
    
    if wp_path.exists():
        try:
            content = wp_path.read_text(errors='ignore')
            # 截取前2000字符作为摘要
            result["workPlan"] = content[:2000]
            result["workPlanExists"] = True
            mtime = datetime.datetime.fromtimestamp(wp_path.stat().st_mtime)
            result["workPlanUpdated"] = mtime.strftime('%m-%d %H:%M')
        except Exception:
            pass
    
    if rules_path.exists():
        try:
            content = rules_path.read_text(errors='ignore')
            result["rules"] = content[:1500]
            result["rulesExists"] = True
            mtime = datetime.datetime.fromtimestamp(rules_path.stat().st_mtime)
            result["rulesUpdated"] = mtime.strftime('%m-%d %H:%M')
        except Exception:
            pass
    
    return result


def output_meta(path):
    p = pathlib.Path(path)
    if not p.exists():
        return {"exists": False, "lastModified": None}
    ts = datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
    return {"exists": True, "lastModified": ts}


def main():
    # 使用 officials_stats.json（与 sync_officials_stats.py 统一）
    officials_data = read_json(DATA / 'officials_stats.json', {})
    officials = officials_data.get('officials', []) if isinstance(officials_data, dict) else officials_data
    # 任务源优先：tasks_source.json（可对接外部系统同步写入）
    tasks = atomic_json_read(DATA / 'tasks_source.json', [])
    if not tasks:
        tasks = read_json(DATA / 'tasks.json', [])

    sync_status = read_json(DATA / 'sync_status.json', {})

    org_map = {}
    for o in officials:
        label = o.get('label', o.get('name', ''))
        if label:
            org_map[label] = label
        # 附加各省工作计划和规则
        agent_id = o.get('id', '')
        if agent_id:
            wp_data = read_work_plan(agent_id)
            o['workPlan'] = wp_data.get('workPlan')
            o['workPlanExists'] = wp_data.get('workPlanExists', False)
            o['workPlanUpdated'] = wp_data.get('workPlanUpdated')
            o['rules'] = wp_data.get('rules')
            o['rulesExists'] = wp_data.get('rulesExists', False)
            o['rulesUpdated'] = wp_data.get('rulesUpdated')

        # 量化交易分工模块（硬编码，由主session维护写入一次）
        _dept_mods = {
            'zaochao': {'modules': [
                {'name': 'K线形态识别', 'skill': 'K线形态', 'status': 'monitoring'},
                {'name': '支撑压力位', 'skill': '支撑压力', 'status': 'monitoring'},
                {'name': '资金流向', 'skill': '资金流', 'status': 'monitoring'},
                {'name': '时间周期', 'skill': '时间周期', 'status': 'monitoring'},
                {'name': '新闻流', 'skill': '新闻流', 'status': 'monitoring'},
            ]},
            'zhongshu': {'modules': [
                {'name': 'Polymarket因子回测', 'skill': 'polymarket-backtesting', 'status': 'active'},
                {'name': '波动率分析', 'skill': 'fsi-lseg-option-vol-analysis', 'status': 'active'},
                {'name': '市场筛选', 'skill': 'fsi-er-cmd-screen', 'status': 'active'},
                {'name': '策略信号L1/L2/L4', 'skill': 'V6.5策略', 'status': 'monitoring'},
            ]},
            'menxia': {'modules': [
                {'name': '策略审核', 'skill': 'V6.5策略', 'status': 'review'},
                {'name': '执行监察', 'skill': '工部记录', 'status': 'review'},
                {'name': '风险评估', 'skill': 'P0/P1/P2', 'status': 'review'},
            ]},
            'shangshu': {'modules': [
                {'name': '旨意接收', 'skill': '皇上下旨', 'status': 'active'},
                {'name': '任务派发', 'skill': '六部分工', 'status': 'active'},
                {'name': '进度跟踪', 'skill': '看板监控', 'status': 'active'},
            ]},
            'hubu': {'modules': [
                {'name': 'BTC持仓监控', 'bot': '9090/9091/9092', 'status': 'monitoring'},
                {'name': 'ETH持仓监控', 'bot': '9090/9093', 'status': 'monitoring'},
                {'name': '保证金率', 'bot': '9092', 'status': 'monitoring'},
                {'name': '28定律止损', 'bot': 'ALL', 'status': 'monitoring'},
            ]},
            'libu': {'modules': [
                {'name': 'SOL走势监控', 'bot': '9090/9091', 'status': 'monitoring'},
                {'name': '舆情监控', 'skill': '新闻流', 'status': 'monitoring'},
                {'name': 'Polymarket情绪', 'skill': 'polymarket', 'status': 'monitoring'},
            ]},
            'bingbu': {'modules': [
                {'name': '高波动币种', 'bot': '9090', 'status': 'monitoring'},
                {'name': '8x杠杆专项', 'bot': '9092', 'status': 'monitoring'},
                {'name': 'DOGE监控', 'bot': '9093', 'status': 'monitoring'},
            ]},
            'xingbu': {'modules': [
                {'name': 'Polymarket因子', 'skill': 'polymarket-backtesting', 'status': 'research'},
                {'name': '波动率结构', 'skill': 'fsi-lseg-option-vol-analysis', 'status': 'research'},
                {'name': '跨市场分析', 'skill': 'cross-market', 'status': 'research'},
            ]},
            'gongbu': {'modules': [
                {'name': '9090运维', 'bot': '9090 Gate.io', 'status': 'monitoring'},
                {'name': '9091运维', 'bot': '9091 Gate.io', 'status': 'monitoring'},
                {'name': '9092运维', 'bot': '9092 Gate.io 8x', 'status': 'monitoring'},
                {'name': '9093运维', 'bot': '9093 OKX', 'status': 'monitoring'},
                {'name': '9094运维', 'bot': '9094 OKX', 'status': 'monitoring'},
                {'name': '9095运维', 'bot': '9095 OKX', 'status': 'monitoring'},
                {'name': '9096运维', 'bot': '9096 OKX', 'status': 'monitoring'},
                {'name': '9097运维', 'bot': '9097 OKX', 'status': 'monitoring'},
            ]},
            'libu_hr': {'modules': [
                {'name': '模型配置', 'model': 'MiniMax-M2.7-highspeed', 'status': 'admin'},
                {'name': '技能库', 'count': '100+', 'status': 'admin'},
                {'name': '任务调度', 'status': 'admin'},
            ]},
            'taizi': {'modules': [
                {'name': '日交易日报', 'freq': '每日16:00', 'status': 'compiling'},
                {'name': '旨意分拣', 'status': 'active'},
                {'name': '调度协调', 'status': 'active'},
            ]},
        }
        if agent_id in _dept_mods:
            o['deptModules'] = _dept_mods[agent_id]

    now_ts = datetime.datetime.now(datetime.timezone.utc)
    for t in tasks:
        t['org'] = t.get('org') or org_map.get(t.get('official', ''), '')
        t['outputMeta'] = output_meta(t.get('output', ''))

        # 心跳时效检测：对 Doing/Assigned 状态的任务标注活跃度
        if t.get('state') in ('Doing', 'Assigned', 'Review'):
            updated_raw = t.get('updatedAt') or t.get('sourceMeta', {}).get('updatedAt')
            age_sec = None
            if updated_raw:
                try:
                    if isinstance(updated_raw, (int, float)):
                        updated_dt = datetime.datetime.fromtimestamp(updated_raw / 1000, tz=datetime.timezone.utc)
                    else:
                        updated_dt = datetime.datetime.fromisoformat(str(updated_raw).replace('Z', '+00:00'))
                    age_sec = (now_ts - updated_dt).total_seconds()
                except Exception:
                    pass
            if age_sec is None:
                t['heartbeat'] = {'status': 'unknown', 'label': '⚪ 未知', 'ageSec': None}
            elif age_sec < 180:
                t['heartbeat'] = {'status': 'active', 'label': f'🟢 活跃 {int(age_sec//60)}分钟前', 'ageSec': int(age_sec)}
            elif age_sec < 600:
                t['heartbeat'] = {'status': 'warn', 'label': f'🟡 可能停滞 {int(age_sec//60)}分钟前', 'ageSec': int(age_sec)}
            else:
                t['heartbeat'] = {'status': 'stalled', 'label': f'🔴 已停滞 {int(age_sec//60)}分钟', 'ageSec': int(age_sec)}
        else:
            t['heartbeat'] = None

    today_str = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')
    def _is_today_done(t):
        if t.get('state') != 'Done':
            return False
        ua = t.get('updatedAt', '')
        if isinstance(ua, str) and ua[:10] == today_str:
            return True
        # fallback: outputMeta lastModified
        lm = t.get('outputMeta', {}).get('lastModified', '')
        if isinstance(lm, str) and lm[:10] == today_str:
            return True
        return False
    today_done = sum(1 for t in tasks if _is_today_done(t))
    total_done = sum(1 for t in tasks if t.get('state') == 'Done')
    in_progress = sum(1 for t in tasks if t.get('state') in ['Doing', 'Review', 'Next', 'Blocked'])
    blocked = sum(1 for t in tasks if t.get('state') == 'Blocked')
    total_count = len(tasks)
    archived_count = sum(1 for t in tasks if t.get('archived'))
    active_count = total_count - archived_count

    # ── 自动清理：Review状态且已完成的任务 → Done ──
    auto_done_count = 0
    for t in tasks:
        if t.get('state') == 'Review':
            now = t.get('now', '')
            # 判断"已完成"特征：包含"已完成"、"已生成"、"已更新"、"提案路径"等关键词
            done_keywords = ['已完成', '已生成', '已更新', '提案路径', '已写入', '已保存']
            if now and any(kw in now for kw in done_keywords):
                t['state'] = 'Done'
                t['archived'] = True
                auto_done_count += 1
    if auto_done_count > 0:
        log.info(f"[auto-cleanup] {auto_done_count} 个Review任务已自动推进为Done")

    history = []
    for t in tasks:
            lm = t.get('outputMeta', {}).get('lastModified')
            history.append({
                'at': lm or '未知',
                'official': t.get('official'),
                'task': t.get('title'),
                'out': t.get('output'),
                'qa': '通过' if t.get('outputMeta', {}).get('exists') else '待补成果'
            })

    payload = {
        'generatedAt': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'taskSource': 'tasks_source.json' if (DATA / 'tasks_source.json').exists() else 'tasks.json',
        'officials': officials,
        'tasks': tasks,
        'history': history,
        'activeCount': active_count,
        'archivedCount': archived_count,
        'totalCount': total_count,
        'metrics': {
            'officialCount': len(officials),
            'todayDone': today_done,
            'totalDone': total_done,
            'inProgress': in_progress,
            'blocked': blocked
        },
        'syncStatus': sync_status,
        'health': {
            'syncOk': bool(sync_status.get('ok', False)),
            'syncLatencyMs': sync_status.get('durationMs'),
            'missingFieldCount': len(sync_status.get('missingFields', {})),
        }
    }

    atomic_json_write(DATA / 'live_status.json', payload)
    log.info(f'updated live_status.json ({len(tasks)} tasks)')


if __name__ == '__main__':
    main()
