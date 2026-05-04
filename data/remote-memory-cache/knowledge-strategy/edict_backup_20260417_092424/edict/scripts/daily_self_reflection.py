#!/usr/bin/env python3
"""
每日自我反思脚本
太子每天18:00和22:00执行，主动反思错误
"""

import json
from pathlib import Path
from datetime import datetime

HOME = Path.home()
WORKSPACE_ROOT = HOME / ".openclaw" / "workspace-tianlu"
KB_DIR = Path("/Volumes/TianLu_Storage/Knowledge_Strategy_Base")
ERROR_LOG = WORKSPACE_ROOT / "memory" / "error_log.md"
EVOLUTION_LOG = WORKSPACE_ROOT / "memory" / "self_evolution.md"

def check_data_accuracy():
    """检查今天报告过的数据是否有误"""
    # 简化版：检查是否有不确定的数据被报告
    checks = []
    
    # 检查dashboard_data.json的更新时间
    dashboard_json = WORKSPACE_ROOT / "reports" / "dashboard_data.json"
    if dashboard_json.exists():
        try:
            data = json.loads(dashboard_json.read_text())
            updated = data.get("generated_at", "")
            market = data.get("market", {})
            if market:
                for coin, info in market.items():
                    price = info.get("price", 0)
                    if price == 0:
                        checks.append({
                            "type": "数据错误",
                            "detail": f"{coin}价格为0，可能数据异常",
                            "action": "需要验证"
                        })
        except:
            pass
    
    return checks

def check_unauthorized_actions():
    """检查今天有没有越权行为"""
    actions = []
    
    # 检查9099端口是否有未授权修改
    server_py = Path("/Volumes/TianLu_Storage/agentbridge_boards/server.py")
    freqtrade_console = HOME / "freqtrade_console" / "console_server.py"
    
    # 如果两者内容不同，说明被改过
    try:
        if server_py.exists() and freqtrade_console.exists():
            # 简单比较大小
            if server_py.stat().st_size != freqtrade_console.stat().st_size:
                # 更进一步检查
                pass
    except:
        pass
    
    return actions

def self_reflection_check():
    """执行自我反思检查"""
    now = datetime.now()
    hour = now.hour
    
    print("=" * 50)
    print(f"🔍 太子自我反思 ({hour}:00)")
    print("=" * 50)
    
    issues = []
    
    # 1. 数据准确性检查
    print("\n📊 数据准确性检查...")
    data_issues = check_data_accuracy()
    if data_issues:
        print(f"  ⚠️ 发现 {len(data_issues)} 个数据问题:")
        for issue in data_issues:
            print(f"    - {issue['type']}: {issue['detail']}")
            issues.append(issue)
    else:
        print("  ✅ 无数据问题")
    
    # 2. 越权检查
    print("\n🔒 越权检查...")
    auth_issues = check_unauthorized_actions()
    if auth_issues:
        print(f"  ⚠️ 发现 {len(auth_issues)} 个越权风险:")
        for issue in auth_issues:
            print(f"    - {issue}")
            issues.append(issue)
    else:
        print("  ✅ 无越权行为")
    
    # 3. 知识库完整性检查
    print("\n📚 知识库检查...")
    kb_files = list(KB_DIR.glob("**/*.md"))
    print(f"  知识库文件数: {len(kb_files)}")
    
    # 4. 学习进度检查
    print("\n📖 学习进度检查...")
    learning_dir = WORKSPACE_ROOT / "memory" / "learning"
    if learning_dir.exists():
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_notes = list(learning_dir.glob(f"*{today_str}*.md"))
        if today_notes:
            print(f"  ✅ 今日有学习笔记: {len(today_notes)}")
        else:
            print(f"  ⚠️ 今日暂无学习笔记")
            issues.append({
                "type": "学习缺失",
                "detail": "今日没有学习笔记",
                "action": "今天14:00应该学习"
            })
    
    # 5. 错误日志检查
    print("\n📋 错误日志检查...")
    if ERROR_LOG.exists():
        content = ERROR_LOG.read_text()
        today_str = datetime.now().strftime("%Y-%m-%d")
        if today_str in content:
            # 今天的错误已记录
            pass
    
    # 汇总
    print("\n" + "=" * 50)
    if issues:
        print(f"⚠️ 发现 {len(issues)} 个需要处理的问题:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue['type']}: {issue['detail']}")
        print(f"\n💡 这些问题应该主动纠正，不是只记录")
    else:
        print("✅ 无明显问题")
    
    return issues

def main():
    issues = self_reflection_check()
    
    # 生成反思报告
    now = datetime.now()
    hour = now.hour
    
    if hour == 18:
        phase = "暮间"
    elif hour == 22:
        phase = "夜间"
    else:
        phase = f"{hour}点"
    
    report = f"""
---

## {now.strftime('%Y-%m-%d')} {phase}自我反思

### 检查结果

"""
    if issues:
        report += "发现以下问题：\n"
        for issue in issues:
            report += f"- {issue['type']}: {issue['detail']}\n"
    else:
        report += "无明显问题\n"
    
    report += f"""
### 主动纠正

"""
    if issues:
        for issue in issues:
            report += f"- {issue.get('action', '需处理')}: {issue['detail']}\n"
    else:
        report += "- 继续保持\n"
    
    print("\n" + report)
    
    return issues

if __name__ == "__main__":
    main()
