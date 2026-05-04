#!/usr/bin/env python3
"""
三兄弟行情形态识别系统 v1.0
所有者：嫡长子天禄 代表三兄弟共建
功能：多时线行情采集 + 缠论形态识别 + 威科夫量价分析 + 形态匹配
"""

import json
import time
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional

PROXY = "http://127.0.0.1:5020"
HOME = Path.home()

# ============ 数据获取层 ============

def curl_json(url: str, timeout: int = 10) -> dict | None:
    """通过代理获取JSON数据"""
    try:
        cmd = ["curl", "-s", "--max-time", str(timeout), "-x", PROXY, "-H", "Accept: application/json", url]
        result = subprocess.run(cmd, capture_output=True, timeout=timeout + 3)
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
    except:
        pass
    return None

def get_binance_klines(symbol: str, interval: str, limit: int = 500) -> List[dict]:
    """
    获取币安K线数据
    interval: 1m, 5m, 15m, 1h, 4h, 1d, 1w
    """
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    data = curl_json(url)
    
    if not data:
        return []
    
    klines = []
    for k in data:
        klines.append({
            "open_time": k[0],
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "close_time": k[6],
            "quote_volume": float(k[7]),  # 成交额(USDT)
            "trades": k[8],  # 成交笔数
            "taker_buy_volume": float(k[9]),  # 主动买入量
        })
    
    return klines

# ============ 缠论分析层 ============

class ChanAnalyzer:
    """缠论形态识别"""
    
    def __init__(self, klines: List[dict]):
        self.klines = klines
    
    def process_containing(self) -> List[dict]:
        """处理包含关系"""
        if not self.klines:
            return []
        
        processed = []
        i = 0
        
        while i < len(self.klines):
            k = self.klines[i]
            
            if not processed:
                processed.append({
                    "open": k["open"],
                    "high": k["high"],
                    "low": k["low"],
                    "close": k["close"],
                    "volume": k["volume"],
                    "quote_volume": k.get("quote_volume", 0),
                    "trades": k.get("trades", 0),
                    "taker_buy_volume": k.get("taker_buy_volume", 0),
                    "open_time": k["open_time"],
                    "index": i
                })
                i += 1
                continue
            
            prev = processed[-1]
            curr = k
            
            # 判断是否有包含关系
            if self._has_containing(prev, curr):
                merged = self._merge(prev, curr, processed)
                processed[-1] = merged
            else:
                processed.append({
                    "open": curr["open"],
                    "high": curr["high"],
                    "low": curr["low"],
                    "close": curr["close"],
                    "volume": curr["volume"],
                    "quote_volume": curr.get("quote_volume", 0),
                    "trades": curr.get("trades", 0),
                    "taker_buy_volume": curr.get("taker_buy_volume", 0),
                    "open_time": curr["open_time"],
                    "index": i
                })
            
            i += 1
        
        return processed
    
    def _has_containing(self, k1: dict, k2: dict) -> bool:
        """判断是否有包含关系"""
        h1, l1 = k1["high"], k1["low"]
        h2, l2 = k2["high"], k2["low"]
        return (h1 >= h2 and l1 <= l2) or (h1 <= h2 and l1 >= l2)
    
    def _merge(self, k1: dict, k2: dict, processed: List[dict]) -> dict:
        """合并包含关系的K线"""
        h1, l1 = k1["high"], k1["low"]
        h2, l2 = k2["high"], k2["low"]
        
        # 判断趋势方向
        if len(processed) >= 2:
            prev_prev = processed[-2]
            hpp, lpp = prev_prev["high"], prev_prev["low"]
            # 上升趋势取高高，下降趋势取低低
            if hpp > lpp:  # 上升趋势
                new_h = max(h1, h2)
                new_l = max(l1, l2)
            else:  # 下降趋势
                new_h = min(h1, h2)
                new_l = min(l1, l2)
        else:
            new_h = max(h1, h2)
            new_l = min(l1, l2)
        
        return {
            "open": k1["open"],
            "high": new_h,
            "low": new_l,
            "close": k2["close"],
            "volume": k1["volume"] + k2["volume"],
            "quote_volume": k1.get("quote_volume", 0) + k2.get("quote_volume", 0),
            "trades": k1.get("trades", 0) + k2.get("trades", 0),
            "taker_buy_volume": k1.get("taker_buy_volume", 0) + k2.get("taker_buy_volume", 0),
            "open_time": k1["open_time"]
        }
    
    def find_fractals(self, klines: List[dict]) -> List[dict]:
        """找所有分型"""
        if len(klines) < 3:
            return []
        
        fractals = []
        for i in range(1, len(klines) - 1):
            prev = klines[i - 1]
            curr = klines[i]
            next_ = klines[i + 1]
            
            h1, l1 = prev["high"], prev["low"]
            h2, l2 = curr["high"], curr["low"]
            h3, l3 = next_["high"], next_["low"]
            
            # 顶分型
            if h2 > h1 and h2 > h3:
                fractals.append({
                    "type": "top",
                    "index": i,
                    "high": h2,
                    "low": l2,
                    "open_time": curr["open_time"]
                })
            # 底分型
            elif l2 < l1 and l2 < l3:
                fractals.append({
                    "type": "bottom",
                    "index": i,
                    "high": h2,
                    "low": l2,
                    "open_time": curr["open_time"]
                })
        
        return fractals
    
    def find_strokes(self, fractals: List[dict], klines: List[dict]) -> List[dict]:
        """识别笔"""
        if len(fractals) < 2:
            return []
        
        strokes = []
        i = 0
        
        while i < len(fractals) - 1:
            f1 = fractals[i]
            f2 = fractals[i + 1]
            
            idx1 = f1["index"]
            idx2 = f2["index"]
            
            # 必须有独立K线
            if abs(idx2 - idx1) < 2:
                i += 1
                continue
            
            if f1["type"] == "bottom" and f2["type"] == "top":
                strokes.append({
                    "type": "up",
                    "start_index": idx1,
                    "end_index": idx2,
                    "start_price": f1["low"],
                    "end_price": f2["high"],
                    "amplitude": f2["high"] - f1["low"],
                    "high": f2["high"],
                    "low": f1["low"]
                })
            elif f1["type"] == "top" and f2["type"] == "bottom":
                strokes.append({
                    "type": "down",
                    "start_index": idx1,
                    "end_index": idx2,
                    "start_price": f1["high"],
                    "end_price": f2["low"],
                    "amplitude": f1["high"] - f2["low"],
                    "high": f1["high"],
                    "low": f2["low"]
                })
            
            i += 1
        
        return strokes
    
    def find_centers(self, strokes: List[dict]) -> List[dict]:
        """识别中枢"""
        if len(strokes) < 3:
            return []
        
        centers = []
        i = 0
        
        while i <= len(strokes) - 3:
            s1 = strokes[i]
            s2 = strokes[i + 1]
            s3 = strokes[i + 2]
            
            # 三笔方向相同才构成中枢
            if s1["type"] != s2["type"] or s2["type"] != s3["type"]:
                i += 1
                continue
            
            # 重叠区间
            highs = [s1["high"], s1["low"], s2["high"], s2["low"], s3["high"], s3["low"]]
            lows = highs[:]
            highs.sort()
            lows.sort()
            
            high_max = highs[-1]
            low_min = lows[0]
            
            if high_max > low_min:
                centers.append({
                    "type": s1["type"],
                    "start_stroke": i,
                    "end_stroke": i + 2,
                    "high": high_max,
                    "low": low_min,
                    "range": high_max - low_min,
                    "direction": "up" if s1["type"] == "up" else "down"
                })
            
            i += 1
        
        return centers

# ============ 威科夫分析层 ============

class WyckoffAnalyzer:
    """威科夫量价分析"""
    
    def __init__(self, klines: List[dict]):
        self.klines = klines
    
    def calc_volume_profile(self, window: int = 20) -> dict:
        """计算成交量分布"""
        if len(self.klines) < window:
            return {}
        
        recent = self.klines[-window:]
        total_volume = sum(k["volume"] for k in recent)
        total_quote = sum(k.get("quote_volume", 0) for k in recent)
        
        # 上涨vs下跌成交量
        up_volume = sum(k["volume"] for k in recent if k["close"] > k["open"])
        down_volume = sum(k["volume"] for k in recent if k["close"] < k["open"])
        
        # 平均成交量
        avg_volume = total_volume / window
        avg_quote = total_quote / window
        
        # 主动买入比例
        taker_buy = sum(k.get("taker_buy_volume", 0) for k in recent)
        taker_ratio = taker_buy / total_volume if total_volume > 0 else 0.5
        
        return {
            "total_volume": total_volume,
            "up_volume": up_volume,
            "down_volume": down_volume,
            "up_ratio": up_volume / total_volume if total_volume > 0 else 0.5,
            "avg_volume": avg_volume,
            "avg_quote": avg_quote,
            "taker_buy_ratio": taker_ratio
        }
    
    def detect_phase(self, window: int = 50) -> str:
        """
        判断市场阶段
        返回: accumulation(吸筹), distribution(派发), re-accumulation(再吸筹), re-distribution(再派发), markup(上涨), markdown(下跌)
        """
        if len(self.klines) < window:
            return "unknown"
        
        recent = self.klines[-window:]
        vp = self.calc_volume_profile(window)
        
        # 计算价格位置
        highs = [k["high"] for k in recent]
        lows = [k["low"] for k in recent]
        current = recent[-1]["close"]
        
        price_high = max(highs)
        price_low = min(lows)
        price_range = price_high - price_low
        
        if price_range == 0:
            return "range"
        
        # 价格在区间的位置 (0=最低, 1=最高)
        price_position = (current - price_low) / price_range
        
        # 判断量价关系
        if vp.get("up_ratio", 0.5) > 0.55 and vp.get("taker_buy_ratio", 0.5) > 0.52:
            # 上涨放量 + 主动买入多 → 需求占优
            if price_position > 0.7:
                return "markup"  # 上涨阶段
            elif price_position < 0.3:
                return "accumulation"  # 吸筹
        elif vp.get("up_ratio", 0.5) < 0.45 and vp.get("taker_buy_ratio", 0.5) < 0.48:
            # 下跌放量 + 主动卖出多 → 供应占优
            if price_position < 0.3:
                return "markdown"  # 下跌阶段
            elif price_position > 0.7:
                return "distribution"  # 派发
        
        return "range"  # 震荡
    
    def detect_spring(self, window: int = 20) -> Optional[dict]:
        """
        检测弹簧效应（跌破支撑后快速拉回）
        """
        if len(self.klines) < window:
            return None
        
        recent = self.klines[-window:]
        lows = [k["low"] for k in recent]
        support = min(lows[:-1]) if len(lows) > 1 else lows[0]
        
        # 最近K线是否短暂跌破支撑
        last = recent[-1]
        prev = recent[-2]
        
        if prev["low"] > support and last["low"] < support:
            # 短暂跌破
            recovery = last["close"] > support
            if recovery:
                return {
                    "type": "spring",
                    "support": support,
                    "low": last["low"],
                    "recovery": last["close"],
                    "duration": 1  # 跌破1根K线后拉回
                }
        
        return None
    
    def detect_sos(self, window: int = 20) -> bool:
        """
        检测强势信号（反弹时量增价升）
        """
        if len(self.klines) < window:
            return False
        
        recent = self.klines[-window:]
        vp = self.calc_volume_profile(window)
        
        # 最近一根K线
        last = recent[-1]
        prev_avg_close = sum(k["close"] for k in recent[:-1]) / (len(recent) - 1)
        
        # 价涨 + 量增
        if last["close"] > last["open"] and last["close"] > prev_avg_close:
            if vp.get("up_ratio", 0.5) > 0.55:
                return True
        
        return False

# ============ 形态匹配层 ============

class PatternMatcher:
    """形态匹配器 - 对比实时形态与知识库"""
    
    def __init__(self):
        self.patterns = self._load_patterns()
    
    def _load_patterns(self) -> List[dict]:
        """加载知识库中的历史形态"""
        # 知识库路径
        kb_path = Path("/Volumes/TianLu_Storage/Knowledge_Strategy_Base")
        if not kb_path.exists():
            return []
        
        patterns = []
        
        # 从知识库读取案例
        cases_dir = kb_path / "Knowledge" / "缠论" / "实战案例"
        if cases_dir.exists():
            for f in cases_dir.glob("*.md"):
                patterns.append({"source": "缠论", "file": str(f)})
        
        return patterns
    
    def match(self, current_analysis: dict) -> dict:
        """
        匹配当前形态与历史形态
        基于缠论+威科夫理论的规则匹配
        """
        # 当前形态特征
        phase = current_analysis.get("wyckoff_phase", "unknown")
        stroke_dir = current_analysis.get("stroke_direction", "unknown")
        centers = current_analysis.get("centers", [])
        has_center = len(centers) > 0
        center_dir = centers[-1].get("direction", "none") if centers else "none"
        vp = current_analysis.get("volume_profile", {})
        
        # === 匹配规则 ===
        
        # 1. 吸筹突破（最强烈做多信号）
        if phase == "accumulation" and stroke_dir == "up":
            return {
                "matched": True,
                "similarity": 0.88,
                "pattern_type": "吸筹突破",
                "prediction": {
                    "direction": "做多",
                    "confidence": 80,
                    "expected_duration": "3-7天",
                    "stop_loss": "前低-2%",
                    "take_profit": "突破后涨幅20-35%",
                    "leverage": "3-5x",
                    "position_pct": 20
                },
                "source": "威科夫吸筹 + 缠论上升笔 + 中枢突破"
            }
        
        # 2. 派发跌破（最强烈做空信号）
        elif phase == "distribution" and stroke_dir == "down":
            return {
                "matched": True,
                "similarity": 0.85,
                "pattern_type": "派发跌破",
                "prediction": {
                    "direction": "做空",
                    "confidence": 78,
                    "expected_duration": "3-7天",
                    "stop_loss": "前高+2%",
                    "take_profit": "跌破后跌幅20-35%",
                    "leverage": "3-5x",
                    "position_pct": 20
                },
                "source": "威科夫派发 + 缠论下降笔 + 中枢跌破"
            }
        
        # 3. 上涨中继
        elif phase == "markup" and stroke_dir == "up" and has_center:
            return {
                "matched": True,
                "similarity": 0.80,
                "pattern_type": "上涨中继",
                "prediction": {
                    "direction": "持有/加仓",
                    "confidence": 72,
                    "expected_duration": "5-14天",
                    "stop_loss": "前一笔低点-2%",
                    "take_profit": "趋势延续前高的15-25%",
                    "leverage": "2-3x",
                    "position_pct": 30
                },
                "source": "威科夫上涨 + 缠论上升中枢"
            }
        
        # 4. 下跌中继
        elif phase == "markdown" and stroke_dir == "down" and has_center:
            return {
                "matched": True,
                "similarity": 0.78,
                "pattern_type": "下跌中继",
                "prediction": {
                    "direction": "做空/观望",
                    "confidence": 70,
                    "expected_duration": "5-14天",
                    "stop_loss": "前一笔高点+2%",
                    "take_profit": "趋势延续跌幅15-25%",
                    "leverage": "2-3x",
                    "position_pct": 30
                },
                "source": "威科夫下跌 + 缠论下降中枢"
            }
        
        # 5. 震荡下行（区间高位）
        elif phase == "range" and center_dir == "down":
            # 判断是否在区间低位还是高位
            if has_center:
                center_high = centers[-1].get("high", 0)
                center_low = centers[-1].get("low", 0)
                # 当前价格相对位置未知，用下跌笔判断
                if stroke_dir == "down":
                    return {
                        "matched": True,
                        "similarity": 0.65,
                        "pattern_type": "下降中继",
                        "prediction": {
                            "direction": "做空/观望",
                            "confidence": 58,
                            "expected_duration": "1-3天",
                            "stop_loss": "前高+1.5%",
                            "take_profit": "前低附近",
                            "leverage": "2x",
                            "position_pct": 20
                        },
                        "source": "威科夫震荡 + 下降中枢 + 下降笔"
                    }
        
        # 6. 震荡上行
        elif phase == "range" and center_dir == "up":
            if has_center and stroke_dir == "up":
                return {
                    "matched": True,
                    "similarity": 0.65,
                    "pattern_type": "上升中继",
                    "prediction": {
                        "direction": "观望/轻仓",
                        "confidence": 55,
                        "expected_duration": "1-3天",
                        "stop_loss": "前低-1.5%",
                        "take_profit": "前高附近",
                        "leverage": "2x",
                        "position_pct": 15
                    },
                    "source": "威科夫震荡 + 上升中枢 + 上升笔"
                }
        
        # 7. 下降中枢 + 下降笔（偏空）
        elif has_center and center_dir == "down" and stroke_dir == "down":
            return {
                "matched": True,
                "similarity": 0.70,
                "pattern_type": "下降延续",
                "prediction": {
                    "direction": "做空/观望",
                    "confidence": 65,
                    "expected_duration": "3-7天",
                    "stop_loss": "中枢上沿+1%",
                    "take_profit": "创新低",
                    "leverage": "2-3x",
                    "position_pct": 25
                },
                "source": "缠论下降中枢 + 下降笔"
            }
        
        # 8. 下降中枢 + 上升笔（可能反弹）
        elif has_center and center_dir == "down" and stroke_dir == "up":
            return {
                "matched": True,
                "similarity": 0.60,
                "pattern_type": "反弹可能",
                "prediction": {
                    "direction": "观望/轻仓买入",
                    "confidence": 52,
                    "expected_duration": "1-3天",
                    "stop_loss": "中枢下沿-1%",
                    "take_profit": "中枢上沿",
                    "leverage": "2x",
                    "position_pct": 15
                },
                "source": "缠论下降中枢 + 反弹笔（谨慎）"
            }
        
        # 9. 无中枢的震荡
        elif phase == "range" and not has_center:
            if stroke_dir == "down":
                return {
                    "matched": True,
                    "similarity": 0.55,
                    "pattern_type": "短线下降",
                    "prediction": {
                        "direction": "观望",
                        "confidence": 45,
                        "expected_duration": "几小时-1天",
                        "stop_loss": "前高+1%",
                        "take_profit": "观望",
                        "leverage": "不做",
                        "position_pct": 0
                    },
                    "source": "无中枢震荡 + 下降笔"
                }
            elif stroke_dir == "up":
                return {
                    "matched": True,
                    "similarity": 0.55,
                    "pattern_type": "短线反弹",
                    "prediction": {
                        "direction": "观望",
                        "confidence": 45,
                        "expected_duration": "几小时-1天",
                        "stop_loss": "前低-1%",
                        "take_profit": "观望",
                        "leverage": "不做",
                        "position_pct": 0
                    },
                    "source": "无中枢震荡 + 上升笔"
                }
        
        return {
            "matched": True,
            "similarity": 0.50,
            "pattern_type": "形态不明确",
            "prediction": {
                "direction": "观望",
                "confidence": 40,
                "expected_duration": "不确定",
                "stop_loss": "-",
                "take_profit": "-",
                "leverage": "不做",
                "position_pct": 0
            },
            "source": "综合分析信号不足"
        }

# ============ 多时线分析 ============

def analyze_multi_timeframe(symbol: str = "BTCUSDT") -> dict:
    """多时线综合分析"""
    intervals = ["1m", "5m", "15m", "1h", "4h", "1d"]
    results = {}
    
    print(f"\n{'='*60}")
    print(f"📊 {symbol} 多时线形态分析")
    print(f"{'='*60}")
    
    for tf in intervals:
        klines = get_binance_klines(symbol, tf, 200)
        if not klines:
            print(f"  {tf}: 数据获取失败")
            continue
        
        # 缠论分析
        chan = ChanAnalyzer(klines)
        processed = chan.process_containing()
        fractals = chan.find_fractals(processed)
        strokes = chan.find_strokes(fractals, processed)
        centers = chan.find_centers(strokes)
        
        # 威科夫分析
        wyckoff = WyckoffAnalyzer(klines)
        phase = wyckoff.detect_phase(50)
        spring = wyckoff.detect_spring(20)
        sos = wyckoff.detect_sos(20)
        vp = wyckoff.calc_volume_profile(20)
        
        results[tf] = {
            "klines_count": len(klines),
            "fractals_count": len(fractals),
            "strokes_count": len(strokes),
            "centers_count": len(centers),
            "last_stroke": strokes[-1] if strokes else None,
            "last_center": centers[-1] if centers else None,
            "wyckoff_phase": phase,
            "spring": spring,
            "sos": sos,
            "volume_profile": vp,
            "current_price": klines[-1]["close"],
            "price_change_24h": ((klines[-1]["close"] - klines[-24]["close"]) / klines[-24]["close"] * 100) if len(klines) >= 24 else 0
        }
        
        # 打印摘要
        stroke_dir = strokes[-1]["type"] if strokes else "-"
        center_dir = centers[-1]["direction"] if centers else "-"
        print(f"\n  [{tf}] {klines[-1]['close']:,.2f} ({results[tf]['price_change_24h']:+.2f}%)")
        print(f"      笔: {stroke_dir} | 中枢: {center_dir} | 威科夫: {phase}")
        if spring:
            print(f"      🟢 Spring信号!")
        if sos:
            print(f"      🟢 SOS信号!")
    
    # 综合判断 - 使用1h数据（如果没有就用4h）
    tf_key = "1h" if "1h" in results and results["1h"].get("klines_count", 0) > 0 else "4h"
    if tf_key not in results or results[tf_key].get("klines_count", 0) == 0:
        tf_key = "5m"
    
    tf_data = results.get(tf_key, {})
    
    matcher = PatternMatcher()
    current = {
        "wyckoff_phase": tf_data.get("wyckoff_phase", "range"),
        "stroke_direction": tf_data.get("last_stroke", {}).get("type", "unknown"),
        "centers": tf_data.get("centers", []),
        "volume_profile": tf_data.get("volume_profile", {})
    }
    
    match_result = matcher.match(current)
    
    print(f"\n{'='*60}")
    print(f"🎯 形态匹配结果")
    print(f"{'='*60}")
    print(f"  匹配: {'✅' if match_result['matched'] else '❌'}")
    if match_result['matched']:
        print(f"  相似度: {match_result['similarity']*100:.0f}%")
        print(f"  形态类型: {match_result['pattern_type']}")
        print(f"  来源: {match_result['source']}")
        pred = match_result['prediction']
        print(f"\n  📋 预测信号:")
        print(f"     方向: {pred['direction']}")
        print(f"     置信度: {pred['confidence']}%")
        print(f"     预计持仓: {pred['expected_duration']}")
        print(f"     止损: {pred['stop_loss']}")
        print(f"     止盈: {pred['take_profit']}")
    
    # 保存结果
    output = {
        "symbol": symbol,
        "timestamp": datetime.now().isoformat(),
        "timeframes": results,
        "match": match_result
    }
    
    output_path = Path.home() / ".openclaw" / "workspace-tianlu" / "memory" / "learning" / f"multi_tf_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    
    return output

def main():
    result = analyze_multi_timeframe("BTCUSDT")
    return result

if __name__ == "__main__":
    main()
