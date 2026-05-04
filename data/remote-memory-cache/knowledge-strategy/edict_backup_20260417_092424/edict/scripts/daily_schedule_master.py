#!/usr/bin/env python3
"""
太子每日日程调度系统 v1.0
管理所有子代理的每日任务调度
"""

import subprocess
import json
from pathlib import Path
from datetime import datetime
import sys

HOME = Path.home()
LOGS_DIR = HOME / "edict" / "data" / "logs"
SCRIPTS_DIR = HOME / "edict" / "scripts"
WORKSPACE_ROOT = HOME / ".openclaw" / "workspace-tianlu"
KB_DIR = Path("/Volumes/TianLu_Storage/Knowledge_Strategy_Base")

LOGS_DIR.mkdir(parents=True, exist_ok=True)

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")

def run_script(name, script_path, timeout=60):
    """运行脚本并记录日志"""
    log(f"启动 {name}...")
    try:
        result = subprocess.run(
            ["python3", str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(HOME)
        )
        if result.returncode == 0:
            log(f"✅ {name} 完成")
            return True
        else:
            log(f"⚠️ {name} 退出码: {result.returncode}", "WARN")
            if result.stderr:
                log(f"   错误: {result.stderr[:200]}", "WARN")
            return False
    except subprocess.TimeoutExpired:
        log(f"❌ {name} 超时", "ERROR")
        return False
    except Exception as e:
        log(f"❌ {name} 异常: {e}", "ERROR")
        return False

# ============ 各子代理的每日任务 ============

def agent_tasks():
    """子代理每日任务"""
    tasks = {}
    
    # 尚书省 - 信号汇总
    tasks["尚书省"] = [
        ("兵部量化分析", SCRIPTS_DIR / "bingbu_quant.py"),
        ("钦天监情绪分析", SCRIPTS_DIR / "qintian_sentiment.py"),
        ("刑部风控检查", SCRIPTS_DIR / "xingbu_risk_check.py"),
        ("尚书省信号汇总", SCRIPTS_DIR / "shangshu_signal.py"),
    ]
    
    # 户部 - 执行
    tasks["户部"] = [
        ("ATR止盈检查", SCRIPTS_DIR / "hubu_atr_check.py"),
        ("执行报告", SCRIPTS_DIR / "hubu_execution_report.py"),
    ]
    
    # 兵部 - 量化
    tasks["兵部"] = [
        ("波动率扫描", SCRIPTS_DIR / "bingbu_volatility_scan.py"),
        ("多时线分析", SCRIPTS_DIR / "bingbu_multitimeframe.py"),
    ]
    
    # 刑部 - 风控
    tasks["刑部"] = [
        ("杠杆审计", SCRIPTS_DIR / "xingbu_leverage_audit.py"),
        ("VaR计算", SCRIPTS_DIR / "xingbu_var_calc.py"),
    ]
    
    # 钦天监 - 情绪
    tasks["钦天监"] = [
        ("情绪扫描", SCRIPTS_DIR / "qintian_sentiment_scan.py"),
        ("FOMO检测", SCRIPTS_DIR / "qintian_fomo_detect.py"),
    ]
    
    # 工部 - 运维
    tasks["工部"] = [
        ("健康检查", SCRIPTS_DIR / "gongbu_health_check.py"),
        ("日志清理", SCRIPTS_DIR / "gongbu_log_cleanup.py"),
    ]
    
    return tasks

def run_daily_schedule():
    """执行每日日程"""
    log("=" * 50)
    log("太子每日日程调度开始")
    log("=" * 50)
    
    hour = datetime.now().hour
    minute = datetime.now().minute
    ts = f"{hour:02d}:{minute:02d}"
    
    results = {}
    
    # 根据时间执行对应任务
    if "06:00" <= ts <= "06:30":
        # 06:00 晨间准备
        log("执行 06:00 晨间准备...")
        run_script("信号白名单清洗", SCRIPTS_DIR / "scheduler_morning_wash.py", timeout=120)
        
    elif "08:00" <= ts <= "08:30":
        # 08:00 舆情监控
        log("执行 08:00 舆情监控...")
        run_script("舆情监控", SCRIPTS_DIR / "monitor_sentiment.py", timeout=120)
        
    elif "09:00" <= ts <= "09:30":
        # 09:00 各子代理日报
        log("执行 09:00 各子代理日报...")
        
        # 尚书省调度
        shangshu_path = SCRIPTS_DIR / "daily_agent_report.py"
        if shangshu_path.exists():
            result = run_script("尚书省汇总", shangshu_path, timeout=180)
            results["尚书省"] = result
        
        # 各子代理独立报告
        for agent, agent_scripts in agent_tasks().items():
            log(f"执行 {agent} 任务...")
            agent_results = []
            for name, script in agent_scripts:
                if script.exists():
                    r = run_script(f"{agent}_{name}", script, timeout=60)
                    agent_results.append(r)
            results[agent] = all(agent_results) if agent_results else False
        
        # 太子综合汇报
        taizi_path = SCRIPTS_DIR / "taizi_daily_report.py"
        if taizi_path.exists():
            run_script("太子综合汇报", taizi_path, timeout=120)
        
    elif "10:00" <= ts <= "10:30":
        # 10:00 太子向父亲汇报
        log("执行 10:00 太子汇报...")
        run_script("太子日报", SCRIPTS_DIR / "taizi_daily_report.py", timeout=120)
        
    elif "14:00" <= ts <= "14:30":
        # 14:00 每日学习
        log("执行 14:00 每日学习...")
        run_script("天下要闻生成", SCRIPTS_DIR / "daily_briefing.py", timeout=120)
        # 学习内容整理
        learn_script = HOME / "edict" / "scripts" / "daily_learning.py"
        if learn_script.exists():
            run_script("每日学习整理", learn_script, timeout=180)
        
    elif "18:00" <= ts <= "18:30":
        # 18:00 暮间复盘
        log("执行 18:00 暮间复盘...")
        run_script("每日交易复盘", SCRIPTS_DIR / "daily_trade_summary.py", timeout=120)
        # 纠错自检
        reflect_script = HOME / "edict" / "scripts" / "daily_self_reflection.py"
        if reflect_script.exists():
            run_script("暮间自检", reflect_script, timeout=120)
        
    elif "22:00" <= ts <= "22:30":
        # 22:00 夜间进化
        log("执行 22:00 夜间进化...")
        # 太子夜间进化报告
        run_script("夜间进化报告", SCRIPTS_DIR / "taizi_jjc_report.py", timeout=180)
        # 知识库更新
        kb_update_script = HOME / "edict" / "scripts" / "knowledge_base_update.py"
        if kb_update_script.exists():
            run_script("知识库更新", kb_update_script, timeout=300)
    
    else:
        log(f"当前时间 {ts} 无定时任务", "INFO")
    
    # 汇总结果
    log("=" * 50)
    log("每日日程执行汇总")
    log("=" * 50)
    success = sum(1 for v in results.values() if v)
    total = len(results)
    for agent, result in results.items():
        icon = "✅" if result else "❌"
        log(f"  {icon} {agent}")
    log(f"完成: {success}/{total}")
    
    # 保存执行记录
    save_record(results)

def save_record(results):
    """保存执行记录"""
    record = {
        "timestamp": datetime.now().isoformat(),
        "results": results
    }
    record_file = LOGS_DIR / "daily_schedule_record.json"
    records = []
    if record_file.exists():
        try:
            records = json.loads(record_file.read_text())
        except:
            pass
    records.append(record)
    # 只保留最近30条
    records = records[-30:]
    record_file.write_text(json.dumps(records, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 手动指定时间执行特定任务
        task = sys.argv[1]
        if task == "morning":
            run_script("晨间准备", SCRIPTS_DIR / "scheduler_morning_wash.py")
        elif task == "sentiment":
            run_script("舆情监控", SCRIPTS_DIR / "monitor_sentiment.py")
        elif task == "daily":
            run_daily_schedule()
        elif task == "learning":
            run_script("每日学习", SCRIPTS_DIR / "daily_briefing.py")
        elif task == "evening":
            run_script("暮间复盘", SCRIPTS_DIR / "daily_trade_summary.py")
        elif task == "night":
            run_script("夜间进化", SCRIPTS_DIR / "taizi_jjc_report.py")
    else:
        run_daily_schedule()
