# 多IP对比分析引擎
# 横向对比所有IP的生产数据、质检分、市场表现

import os
import json
import statistics
from datetime import datetime
from typing import Optional

def get_all_ip_analytics() -> list:
    """
    汇总所有IP的完整分析数据
    返回可直接用于前端图表的结构化数据
    """
    cards_dir = "config/ip_cards"
    if not os.path.exists(cards_dir):
        return []

    analytics = []
    for fname in os.listdir(cards_dir):
        if not fname.endswith(".json"):
            continue
        ip_id = fname.replace(".json", "")
        analytics.append(get_ip_analytics(ip_id))

    # 按综合得分降序
    analytics.sort(
        key=lambda x: x.get("composite_score", 0),
        reverse=True
    )
    return analytics

def get_ip_analytics(ip_id: str) -> dict:
    """获取单个IP的完整分析数据"""
    ip_card   = _load_ip_card(ip_id)
    qc_data   = _load_all_qc(ip_id)
    value_data= _load_value_status(ip_id)
    ep_count  = _count_episodes(ip_id)

    # QC维度平均分
    qc_avg_dims = {}
    if qc_data:
        dim_keys = ["角色一致性","画面质量","情绪吻合度","叙事连贯性","节奏合理性"]
        for k in dim_keys:
            vals = [
                q.get("scores", {}).get(k, 0)
                for q in qc_data
                if q.get("scores", {}).get(k) is not None
            ]
            qc_avg_dims[k] = round(
                statistics.mean(vals) if vals else 0, 3
            )

    qc_overall    = round(
        statistics.mean([q.get("weighted_score",0) for q in qc_data])
        if qc_data else 0, 3
    )
    qc_pass_rate  = round(
        len([q for q in qc_data if q.get("passed")]) / len(qc_data)
        if qc_data else 0, 3
    )
    qc_trend      = _calc_trend([q.get("weighted_score",0) for q in qc_data])

    # 价值评估分
    auto_score   = value_data.get("auto_screen",      {}).get("weighted_score", 0)
    human_score  = value_data.get("human_review",     {}).get("weighted_score", 0)
    market_score = value_data.get("market_validation",{}).get("weighted_score", 0)
    decision     = value_data.get("decided",          {}).get("decision", "PENDING")
    composite    = value_data.get("decided",          {}).get("composite_score", 0)

    # 生产效率
    lora_exists  = os.path.exists(f"../models/lora/{ip_id}.safetensors")
    cost_total   = ep_count * 0.77

    return {
        "ip_id":       ip_id,
        "ip_name":     ip_card.get("name", ip_id),
        "genre":       ip_card.get("world",{}).get("genre", ""),
        "tone":        ip_card.get("world",{}).get("tone",  ""),
        "pacing":      ip_card.get("world",{}).get("pacing",""),
        "created_at":  ip_card.get("created_at", ""),
        "lora_ready":  lora_exists,

        # 生产数据
        "production": {
            "episode_count": ep_count,
            "cost_usd":      round(cost_total, 2),
            "cost_cny":      round(cost_total * 7.2, 2)
        },

        # 质检数据
        "qc": {
            "overall":    qc_overall,
            "pass_rate":  qc_pass_rate,
            "dimensions": qc_avg_dims,
            "trend":      qc_trend,       # "up"/"down"/"stable"
            "total_reviews": len(qc_data)
        },

        # 价值评估
        "value": {
            "auto_score":    auto_score,
            "human_score":   human_score,
            "market_score":  market_score,
            "composite":     composite,
            "decision":      decision
        },

        # 综合得分（用于排名）
        "composite_score": composite or qc_overall
    }

def get_comparison_report(ip_ids: list) -> dict:
    """
    生成指定IP列表的横向对比报告
    """
    analytics = [get_ip_analytics(ip_id) for ip_id in ip_ids]

    # 各维度最佳IP
    best = {
        "qc_overall":   _find_best(analytics, "qc.overall"),
        "pass_rate":    _find_best(analytics, "qc.pass_rate"),
        "episode_count":_find_best(analytics, "production.episode_count"),
        "market_score": _find_best(analytics, "value.market_score"),
        "composite":    _find_best(analytics, "composite_score")
    }

    # 雷达图数据（5维度标准化）
    radar_data = []
    for a in analytics:
        radar_data.append({
            "ip_id":   a["ip_id"],
            "ip_name": a["ip_name"],
            "values":  [
                a["qc"]["overall"],
                a["qc"]["pass_rate"],
                a["value"]["auto_score"],
                a["value"]["market_score"] or 0,
                min(1.0, a["production"]["episode_count"] / 30)  # 归一化
            ],
            "labels": ["质检均分","通过率","IP潜力","市场表现","生产规模"]
        })

    return {
        "analytics":    analytics,
        "best":         best,
        "radar_data":   radar_data,
        "generated_at": datetime.now().isoformat()
    }

def _calc_trend(scores: list) -> str:
    """计算质检分趋势"""
    if len(scores) < 3:
        return "stable"
    recent = scores[-3:]
    if recent[-1] > recent[0] + 0.02:
        return "up"
    elif recent[-1] < recent[0] - 0.02:
        return "down"
    return "stable"

def _find_best(analytics: list, key_path: str) -> Optional[str]:
    """找到某指标最高的IP"""
    best_val = -1
    best_ip  = None
    for a in analytics:
        val = a
        for k in key_path.split("."):
            val = val.get(k, 0) if isinstance(val, dict) else 0
        if isinstance(val, (int, float)) and val > best_val:
            best_val = val
            best_ip  = a["ip_id"]
    return best_ip

def _load_ip_card(ip_id: str) -> dict:
    path = f"config/ip_cards/{ip_id}.json"
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def _load_all_qc(ip_id: str) -> list:
    qc_dir = "../qc_reports"
    reports = []
    if not os.path.exists(qc_dir):
        return []
    for fname in sorted(os.listdir(qc_dir)):
        if fname.startswith(ip_id) and fname.endswith("_qc.json"):
            with open(os.path.join(qc_dir, fname), encoding="utf-8") as f:
                reports.append(json.load(f))
    return reports

def _load_value_status(ip_id: str) -> dict:
    path = "config/ip_value_status.json"
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f).get(ip_id, {})

def _count_episodes(ip_id: str) -> int:
    ep_base = "../assets/episodes"
    if not os.path.exists(ep_base):
        return 0
    return len([
        d for d in os.listdir(ep_base)
        if d.startswith(ip_id) and
           os.path.isdir(os.path.join(ep_base, d))
    ])