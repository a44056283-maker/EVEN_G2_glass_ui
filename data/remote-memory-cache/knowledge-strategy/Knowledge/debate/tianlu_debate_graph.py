#!/usr/bin/env python3
"""
TianluDebateGraph - Task 1 (P0)
辩论架构 - 四角色辩论决策机制

角色:
- TechAnalyst: 技术面分析
- RiskAnalyst: 风险分析  
- DebateAgent: 辩论发起者
- JudgeAgent: 最终裁决者

使用:
    python3 tianlu_debate_graph.py "BTC/USDT是否应该做多"
"""

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DEBATE_DIR = Path.home() / ".openclaw/workspace-tianlu/Knowledge/debate"
DEBATE_GRAPH_FILE = DEBATE_DIR / "TianluDebateGraph.json"
CONFIDENCE_FILE = DEBATE_DIR / "confidence_calibration.json"
SHADOW_LOG_FILE = DEBATE_DIR / "shadow_mode_log.json"

# 辩论角色系统提示
ROLE_PROMPTS = {
    "TechAnalyst": """你是技术分析师，专注于价格行为和技术指标。
当前关注:
- 趋势: MA、MACD、趋势线
- 动量: RSI、KDJ、成交量
- 支撑阻力: 布林带、斐波那契

你的职责: 提出技术面的买入/卖出理由""",
    
    "RiskAnalyst": """你是风险分析师，专注于风险控制和资金管理。
当前关注:
- 仓位大小和杠杆倍数
- 止损止盈设置
- 相关性风险和最大回撤
- 风险收益比

你的职责: 识别风险，提出风险调整建议""",
    
    "DebateAgent": """你是辩论主持人，负责组织多空双方的辩论。
规则:
1. 提出核心问题
2. 让TechAnalyst和RiskAnalyst充分表达
3. 识别双方论点的矛盾点
4. 推进辩论直到有明确结论

你的职责: 主持辩论，找出决策关键点""",
    
    "JudgeAgent": """你是裁判，负责综合所有意见给出最终决策。
决策选项:
- STRONG_BUY: 强烈建议做多
- BUY: 建议做多
- HOLD: 观望
- SELL: 建议做空
- STRONG_SELL: 强烈建议做空

你的职责: 基于辩论结果，给出最终裁决和置信度"""
}


class DebateArgument:
    """辩论论点"""
    def __init__(self, role: str, content: str, supporting: bool = True):
        self.role = role
        self.content = content
        self.supporting = supporting  # True=支持行动, False=反对行动
        self.evidence_strength = 0.5  # 证据强度
        self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "role": self.role,
            "content": self.content,
            "supporting": self.supporting,
            "evidence_strength": self.evidence_strength,
            "timestamp": self.timestamp
        }


class TianluDebateGraph:
    """辩论图谱"""
    
    def __init__(self):
        self.debate_dir = DEBATE_DIR
        self.debate_dir.mkdir(parents=True, exist_ok=True)
        self.graph = self._load_graph()
        self.confidence = self._load_confidence()
        self.shadow_log = self._load_shadow_log()
        self.shadow_mode = True  # 默认Shadow Mode收集数据
    
    def _load_graph(self) -> Dict:
        if DEBATE_GRAPH_FILE.exists():
            with open(DEBATE_GRAPH_FILE) as f:
                return json.load(f)
        return {
            "topics": {},
            "decision_patterns": [],
            "last_updated": None
        }
    
    def _load_confidence(self) -> Dict:
        if CONFIDENCE_FILE.exists():
            with open(CONFIDENCE_FILE) as f:
                return json.load(f)
        return {
            "thresholds": {
                "STRONG_BUY": 0.8,
                "BUY": 0.6,
                "HOLD": 0.4,
                "SELL": 0.6,
                "STRONG_SELL": 0.8
            },
            "evidence_weights": {
                "TechAnalyst": 0.4,
                "RiskAnalyst": 0.4,
                "DebateAgent": 0.1,
                "JudgeAgent": 0.1
            },
            "calibration_data": []  # 真实决策数据用于校准
        }
    
    def _load_shadow_log(self) -> List[Dict]:
        if SHADOW_LOG_FILE.exists():
            with open(SHADOW_LOG_FILE) as f:
                return json.load(f)
        return []
    
    def _save_graph(self) -> None:
        self.graph["last_updated"] = datetime.now(timezone.utc).isoformat()
        with open(DEBATE_GRAPH_FILE, 'w') as f:
            json.dump(self.graph, f, ensure_ascii=False, indent=2)
    
    def _save_confidence(self) -> None:
        with open(CONFIDENCE_FILE, 'w') as f:
            json.dump(self.confidence, f, ensure_ascii=False, indent=2)
    
    def _save_shadow_log(self) -> None:
        with open(SHADOW_LOG_FILE, 'w') as f:
            json.dump(self.shadow_log, f, ensure_ascii=False, indent=2)
    
    def add_argument(self, topic: str, argument: DebateArgument) -> None:
        """添加论点到图谱"""
        if topic not in self.graph["topics"]:
            self.graph["topics"][topic] = {
                "arguments": [],
                "decisions": [],
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        
        self.graph["topics"][topic]["arguments"].append(argument.to_dict())
        self._save_graph()
    
    def add_decision(self, topic: str, decision: str, confidence: float, 
                     reasoning: str) -> None:
        """记录决策"""
        if topic not in self.graph["topics"]:
            self.graph["topics"][topic] = {"arguments": [], "decisions": []}
        
        decision_record = {
            "decision": decision,
            "confidence": confidence,
            "reasoning": reasoning,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self.graph["topics"][topic]["decisions"].append(decision_record)
        
        # Shadow Mode: 记录用于后续校准
        if self.shadow_mode:
            self.shadow_log.append({
                "topic": topic,
                "decision": decision,
                "confidence": confidence,
                "reasoning": reasoning,
                "timestamp": decision_record["timestamp"]
            })
            self._save_shadow_log()
        
        self._save_graph()
    
    def log_outcome(self, topic: str, actual_result: str, 
                    profit_loss: float) -> None:
        """记录实际结果，用于置信度校准"""
        # 找到对应决策
        for decision in reversed(self.graph["topics"].get(topic, {}).get("decisions", [])):
            if "actual_result" not in decision:
                decision["actual_result"] = actual_result
                decision["profit_loss"] = profit_loss
                decision["outcome_timestamp"] = datetime.now(timezone.utc).isoformat()
                
                # 更新校准数据
                self.confidence["calibration_data"].append({
                    "topic": topic,
                    "decision": decision["decision"],
                    "confidence": decision["confidence"],
                    "actual_result": actual_result,
                    "profit_loss": profit_loss,
                    "timestamp": decision["outcome_timestamp"]
                })
                
                self._save_graph()
                self._save_confidence()
                
                # 计算校准偏差
                if profit_loss > 0 and decision["confidence"] < 0.6:
                    print(f"⚠️ 置信度偏低但盈利: 决策={decision['decision']}, "
                          f"置信度={decision['confidence']}, 盈亏={profit_loss}")
                elif profit_loss < 0 and decision["confidence"] > 0.7:
                    print(f"⚠️ 置信度偏高但亏损: 决策={decision['decision']}, "
                          f"置信度={decision['confidence']}, 盈亏={profit_loss}")
                
                break
    
    def calibrate_thresholds(self) -> Dict:
        """基于历史数据校准阈值"""
        if len(self.confidence["calibration_data"]) < 10:
            return {"status": "数据不足", "samples": len(self.confidence["calibration_data"])}
        
        # 分析校准数据
        correct_high_conf = 0  # 高置信度且正确
        wrong_high_conf = 0    # 高置信度但错误
        correct_low_conf = 0   # 低置信度但正确
        wrong_low_conf = 0     # 低置信度且错误
        
        for record in self.confidence["calibration_data"]:
            conf = record["confidence"]
            is_profit = record["profit_loss"] > 0
            
            if conf >= 0.7:
                if is_profit:
                    correct_high_conf += 1
                else:
                    wrong_high_conf += 1
            else:
                if is_profit:
                    correct_low_conf += 1
                else:
                    wrong_low_conf += 1
        
        # 调整权重
        total = len(self.confidence["calibration_data"])
        accuracy = sum(1 for r in self.confidence["calibration_data"] 
                      if r["profit_loss"] > 0) / total
        
        # 如果高置信度决策准确率低，提高阈值
        if correct_high_conf + wrong_high_conf > 0:
            high_conf_accuracy = correct_high_conf / (correct_high_conf + wrong_high_conf)
            if high_conf_accuracy < 0.6:
                self.confidence["thresholds"]["STRONG_BUY"] *= 1.1
                self.confidence["thresholds"]["STRONG_SELL"] *= 1.1
                print(f"⚠️ 提高阈值: 高置信度准确率仅 {high_conf_accuracy:.1%}")
        
        self._save_confidence()
        
        return {
            "total_samples": total,
            "overall_accuracy": accuracy,
            "thresholds": self.confidence["thresholds"],
            "calibration_data_count": len(self.confidence["calibration_data"])
        }
    
    def run_debate(self, topic: str, context: Dict = None) -> Dict:
        """运行辩论并返回决策"""
        print(f"\n🏛️ 开始辩论: {topic}")
        print("=" * 60)
        
        arguments = []
        
        # 1. TechAnalyst 提出技术面观点
        print(f"\n📊 TechAnalyst 分析:")
        tech_bullish, tech_bearish = self._analyze_technical(topic, context)
        for arg in tech_bullish:
            arguments.append(DebateArgument("TechAnalyst", arg, supporting=True))
            print(f"   🟢 {arg}")
        for arg in tech_bearish:
            arguments.append(DebateArgument("TechAnalyst", arg, supporting=False))
            print(f"   🔴 {arg}")
        
        # 2. RiskAnalyst 提出风险观点
        print(f"\n⚖️ RiskAnalyst 分析:")
        risk_bullish, risk_bearish = self._analyze_risk(topic, context)
        for arg in risk_bullish:
            arguments.append(DebateArgument("RiskAnalyst", arg, supporting=True))
            print(f"   🟢 {arg}")
        for arg in risk_bearish:
            arguments.append(DebateArgument("RiskAnalyst", arg, supporting=False))
            print(f"   🔴 {arg}")
        
        # 3. DebateAgent 总结辩论
        print(f"\n🎤 DebateAgent 主持:")
        debate_summary = self._summarize_debate(topic, arguments)
        print(f"   {debate_summary}")
        
        # 4. JudgeAgent 给出裁决
        print(f"\n⚖️ JudgeAgent 裁决:")
        decision, confidence, reasoning = self._make_judgment(topic, arguments, context)
        print(f"   决策: {decision}")
        print(f"   置信度: {confidence:.2%}")
        print(f"   理由: {reasoning}")
        
        # 记录辩论结果
        self.add_decision(topic, decision, confidence, reasoning)
        
        return {
            "topic": topic,
            "decision": decision,
            "confidence": confidence,
            "reasoning": reasoning,
            "arguments": [a.to_dict() for a in arguments],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def _analyze_technical(self, topic: str, context: Dict = None) -> Tuple[List[str], List[str]]:
        """技术分析"""
        bullish = []
        bearish = []
        
        # 模拟技术分析（实际应接入真实数据）
        if context:
            price = context.get("price", 0)
            rsi = context.get("rsi", 50)
            vol = context.get("volume", 1.0)
            
            if rsi < 30:
                bullish.append(f"RSI超卖({rsi}), 反弹概率高")
            elif rsi > 70:
                bearish.append(f"RSI超买({rsi}), 回调风险大")
            
            if vol > 2.0:
                bullish.append(f"成交量放大({vol:.1f}x), 趋势确认")
            
            if price > context.get("ma20", price * 1.1):
                bullish.append("价格站稳MA20上方")
            elif price < context.get("ma20", price * 0.9):
                bearish.append("价格跌破MA20")
        
        return bullish, bearish
    
    def _analyze_risk(self, topic: str, context: Dict = None) -> Tuple[List[str], List[str]]:
        """风险分析"""
        bullish = []
        bearish = []
        
        if context:
            leverage = context.get("leverage", 1)
            position_size = context.get("position_size", 0.1)
            
            if leverage > 5:
                bearish.append(f"高杠杆({leverage}x), 爆仓风险大")
            
            if position_size > 0.2:
                bearish.append(f"仓位过大({position_size:.0%}), 风险暴露高")
            
            if leverage <= 3 and position_size <= 0.1:
                bullish.append(f"轻仓低杠杆({leverage}x, {position_size:.0%}), 风险可控")
        
        return bullish, bearish
    
    def _summarize_debate(self, topic: str, arguments: List[DebateArgument]) -> str:
        """辩论总结"""
        supporting = [a for a in arguments if a.supporting]
        opposing = [a for a in arguments if not a.supporting]
        
        return (f"技术面{len(supporting)}个支持, {len(opposing)}个反对. "
                f"关键分歧点待裁决.")
    
    def _make_judgment(self, topic: str, arguments: List[DebateArgument],
                       context: Dict = None) -> Tuple[str, float, str]:
        """裁决"""
        weights = self.confidence["evidence_weights"]
        
        # 计算加权重
        supporting_score = 0
        opposing_score = 0
        
        for arg in arguments:
            weight = weights.get(arg.role, 0.25)
            if arg.supporting:
                supporting_score += weight * arg.evidence_strength
            else:
                opposing_score += weight * arg.evidence_strength
        
        # 归一化
        total = supporting_score + opposing_score
        if total > 0:
            support_ratio = supporting_score / total
        else:
            support_ratio = 0.5
        
        # 考虑shadow mode的置信度
        base_confidence = self.confidence["thresholds"]
        
        # 裁决
        if support_ratio > base_confidence["STRONG_BUY"]:
            decision = "STRONG_BUY"
            confidence = support_ratio
        elif support_ratio > base_confidence["BUY"]:
            decision = "BUY"
            confidence = support_ratio
        elif support_ratio < base_confidence["STRONG_SELL"]:
            decision = "STRONG_SELL"
            confidence = 1 - support_ratio
        elif support_ratio < base_confidence["SELL"]:
            decision = "SELL"
            confidence = 1 - support_ratio
        else:
            decision = "HOLD"
            confidence = 1 - abs(support_ratio - 0.5) * 2
        
        reasoning = f"多空比分 {support_ratio:.2%}, 置信度 {confidence:.2%}"
        
        return decision, confidence, reasoning


def main():
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else "BTC/USDT 做多评估"
    
    graph = TianluDebateGraph()
    
    # 示例context（实际应从市场数据获取）
    context = {
        "price": 65000,
        "rsi": 35,
        "volume": 2.5,
        "ma20": 64000,
        "leverage": 3,
        "position_size": 0.1
    }
    
    result = graph.run_debate(topic, context)
    
    print("\n" + "=" * 60)
    print("📋 最终决策报告")
    print("=" * 60)
    print(f"主题: {result['topic']}")
    print(f"决策: {result['decision']}")
    print(f"置信度: {result['confidence']:.2%}")
    print(f"理由: {result['reasoning']}")


if __name__ == "__main__":
    main()
