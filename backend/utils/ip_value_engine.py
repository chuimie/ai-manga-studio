# IP价值判断引擎
# 三层过滤：自动初筛 → 人工复审 → 市场验证 → 立项决策

import os
import json
import hashlib
from datetime import datetime
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("AGNES_API_KEY"),
    base_url=os.getenv("AGNES_BASE_URL")
)

IP_VALUE_FILE   = "config/ip_value_status.json"
FEEDBACK_DIR    = "logs/market_feedback"
DECISION_LOG    = "logs/ip_decisions.jsonl"

# ─────────────────────────────────────────────
# 评分维度定义
# ─────────────────────────────────────────────

# 自动初筛权重
AUTO_WEIGHTS = {
    "角色辨识度":   0.30,  # 角色外貌/性格是否足够独特
    "喜剧密度":     0.25,  # 每集笑点/冲突密度
    "情绪曲线":     0.20,  # 情绪起伏是否有张力
    "记忆锚点":     0.15,  # 有无令人印象深刻的口头禅/行为
    "系列延展性":   0.10   # 是否能持续生产不重复内容
}

# 市场验证权重
MARKET_WEIGHTS = {
    "完播率":     0.35,
    "互动率":     0.30,  # 点赞+评论+分享
    "回访率":     0.20,  # 看完第1集后是否看第2集
    "情感共鸣度": 0.15   # 评论情感倾向分析
}

# 立项阈值
THRESHOLDS = {
    "auto_pass":      0.75,   # 自动初筛通过
    "market_pass":    0.70,   # 市场验证通过
    "incubate":       0.72,   # 综合分 → 正式立项
    "observe":        0.60,   # 观察区（人工判断）
    "abandon":        0.50    # 低于此分 → 建议放弃
}

# ─────────────────────────────────────────────
# Layer 1：自动初筛
# ─────────────────────────────────────────────

def auto_screen(ip_id: str) -> dict:
    """
    自动初筛：基于IP角色卡 + 前5集质检报告评估IP潜力
    返回初筛报告
    """
    ip_card  = _load_ip_card(ip_id)
    qc_data  = _load_recent_qc(ip_id, limit=5)

    prompt = f"""
你是一个漫剧IP商业价值评估专家。
根据以下IP信息，从5个维度评估IP的商业潜力。

【IP信息】
名称：{ip_card['name']}
性格：{', '.join(ip_card['character']['核心性格'])}
说话习惯：{ip_card['character']['说话习惯']}
口头禅：{', '.join(ip_card['character']['口头禅'])}
喜剧公式：{ip_card['character']['喜剧公式']}
世界观：{ip_card['world']['setting']}
基调：{ip_card['world']['tone']}

【前{len(qc_data)}集质检平均分】
综合得分：{sum(q['weighted_score'] for q in qc_data)/len(qc_data):.3f if qc_data else 'N/A'}

【评估维度】（每项0~1分）
1. 角色辨识度：角色外貌/性格是否足够独特，在同类中能否被记住
2. 喜剧密度：喜剧公式是否高效，每分钟笑点预期密度
3. 情绪曲线：角色的情绪变化是否有张力，能否产生共鸣
4. 记忆锚点：口头禅/行为标签是否有传播潜力
5. 系列延展性：能否持续创作100集以上不重复

返回严格JSON：
{{
  "scores": {{
    "角色辨识度": 0~1,
    "喜剧密度": 0~1,
    "情绪曲线": 0~1,
    "记忆锚点": 0~1,
    "系列延展性": 0~1
  }},
  "strengths": ["优势1", "优势2"],
  "weaknesses": ["劣势1", "劣势2"],
  "comparable_ips": ["类似成功案例1", "类似成功案例2"],
  "summary": "50字以内的综合评价"
}}
"""

    response = client.chat.completions.create(
        model=os.getenv("AGNES_TEXT_MODEL"),
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.4
    )
    result = json.loads(response.choices[0].message.content)
    scores = result.get("scores", {})

    # 加权计算
    weighted = sum(
        scores.get(k, 0) * w
        for k, w in AUTO_WEIGHTS.items()
    )

    passed   = weighted >= THRESHOLDS["auto_pass"]

    report = {
        "layer":        "auto_screen",
        "ip_id":        ip_id,
        "ip_name":      ip_card["name"],
        "scores":       {k: round(v, 3) for k, v in scores.items()},
        "weighted_score": round(weighted, 3),
        "passed":       passed,
        "strengths":    result.get("strengths", []),
        "weaknesses":   result.get("weaknesses", []),
        "comparable_ips": result.get("comparable_ips", []),
        "summary":      result.get("summary", ""),
        "evaluated_at": datetime.now().isoformat(),
        "qc_avg":       round(
            sum(q['weighted_score'] for q in qc_data)/len(qc_data), 3
        ) if qc_data else None
    }

    _update_ip_value_status(ip_id, "auto_screened", report)
    _log_decision(ip_id, "auto_screen", passed, weighted, report["summary"])
    return report

# ─────────────────────────────────────────────
# Layer 2：人工复审
# ─────────────────────────────────────────────

def submit_human_review(
    ip_id: str,
    reviewer_scores: dict,  # {"角色魅力":0.8, "商业潜力":0.9, ...}
    comments: str,
    decision: str           # "pass" / "reject" / "observe"
) -> dict:
    """
    提交人工复审结果
    reviewer_scores 维度：角色魅力 / 商业潜力 / 内容质量 / 受众匹配
    """
    ip_card  = _load_ip_card(ip_id)
    weighted = sum(reviewer_scores.values()) / len(reviewer_scores) \
               if reviewer_scores else 0

    report = {
        "layer":          "human_review",
        "ip_id":          ip_id,
        "ip_name":        ip_card["name"],
        "reviewer_scores": reviewer_scores,
        "weighted_score": round(weighted, 3),
        "comments":       comments,
        "decision":       decision,  # pass/reject/observe
        "reviewed_at":    datetime.now().isoformat()
    }

    _update_ip_value_status(ip_id, "human_reviewed", report)
    _log_decision(ip_id, "human_review", decision == "pass", weighted, comments)
    return report

# ─────────────────────────────────────────────
# Layer 3：市场验证
# ─────────────────────────────────────────────

def submit_market_data(
    ip_id: str,
    platform: str,          # 投放平台
    sample_episodes: int,   # 投放集数
    raw_metrics: dict       # 原始数据
) -> dict:
    """
    提交市场验证数据
    raw_metrics 示例：
    {
      "total_views": 10000,
      "avg_completion_rate": 0.72,   # 完播率
      "like_count": 850,
      "comment_count": 120,
      "share_count": 200,
      "return_viewers": 0.45,        # 回访率
      "comments_sample": ["太萌了", "求更新", ...]
    }
    """
    ip_card  = _load_ip_card(ip_id)

    # 计算互动率
    total_views = raw_metrics.get("total_views", 1)
    interaction_rate = (
        raw_metrics.get("like_count", 0) +
        raw_metrics.get("comment_count", 0) +
        raw_metrics.get("share_count", 0)
    ) / total_views if total_views > 0 else 0

    # 分析评论情感倾向
    sentiment_score = _analyze_comment_sentiment(
        raw_metrics.get("comments_sample", []),
        ip_card["name"]
    )

    # 标准化各维度
    normalized = {
        "完播率":     min(1.0, raw_metrics.get("avg_completion_rate", 0)),
        "互动率":     min(1.0, interaction_rate * 10),  # 10%互动率=满分
        "回访率":     min(1.0, raw_metrics.get("return_viewers", 0)),
        "情感共鸣度": sentiment_score
    }

    weighted = sum(
        normalized.get(k, 0) * w
        for k, w in MARKET_WEIGHTS.items()
    )

    passed   = weighted >= THRESHOLDS["market_pass"]

    # 生成市场洞察
    insights = _generate_market_insights(ip_id, ip_card, raw_metrics, normalized)

    report = {
        "layer":            "market_validation",
        "ip_id":            ip_id,
        "ip_name":          ip_card["name"],
        "platform":         platform,
        "sample_episodes":  sample_episodes,
        "raw_metrics":      raw_metrics,
        "normalized_scores": {k: round(v, 3) for k, v in normalized.items()},
        "weighted_score":   round(weighted, 3),
        "passed":           passed,
        "insights":         insights,
        "validated_at":     datetime.now().isoformat()
    }

    # 存储原始数据
    os.makedirs(FEEDBACK_DIR, exist_ok=True)
    fb_path = os.path.join(
        FEEDBACK_DIR,
        f"{ip_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(fb_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    _update_ip_value_status(ip_id, "market_validated", report)
    _log_decision(ip_id, "market_validation", passed, weighted, insights[:100])
    return report

def _analyze_comment_sentiment(comments: list, ip_name: str) -> float:
    """分析用户评论情感倾向，返回0~1分"""
    if not comments:
        return 0.5

    sample   = comments[:20]
    prompt   = f"""
分析以下针对漫剧角色「{ip_name}」的用户评论的情感倾向。
评论列表：{json.dumps(sample, ensure_ascii=False)}
返回JSON：{{"sentiment_score": 0~1, "positive_ratio": 0~1, "summary": "简短总结"}}
"""
    try:
        resp   = client.chat.completions.create(
            model=os.getenv("AGNES_TEXT_MODEL"),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        result = json.loads(resp.choices[0].message.content)
        return float(result.get("sentiment_score", 0.5))
    except Exception:
        return 0.5

def _generate_market_insights(
    ip_id: str,
    ip_card: dict,
    metrics: dict,
    normalized: dict
) -> str:
    """用LLM生成市场洞察建议"""
    prompt = f"""
角色「{ip_card['name']}」的市场验证数据如下：
完播率：{normalized.get('完播率', 0):.1%}
互动率：{normalized.get('互动率', 0):.1%}
回访率：{normalized.get('回访率', 0):.1%}
情感共鸣：{normalized.get('情感共鸣度', 0):.1%}
总播放量：{metrics.get('total_views', 0)}

请给出3条具体的优化建议和1条核心结论（不超过100字）。
返回JSON：{{"conclusion": "核心结论", "suggestions": ["建议1","建议2","建议3"]}}
"""
    try:
        resp   = client.chat.completions.create(
            model=os.getenv("AGNES_TEXT_MODEL"),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.6
        )
        result = json.loads(resp.choices[0].message.content)
        return result.get("conclusion", "") + " | " + \
               " / ".join(result.get("suggestions", []))
    except Exception:
        return "市场数据已记录，请人工分析"

# ─────────────────────────────────────────────
# Layer 4：综合立项决策
# ─────────────────────────────────────────────

def make_incubation_decision(ip_id: str) -> dict:
    """
    综合三层评估，输出最终立项决策
    """
    status  = get_ip_value_status(ip_id)
    ip_card = _load_ip_card(ip_id)

    auto_score   = status.get("auto_screen",        {}).get("weighted_score", 0)
    human_score  = status.get("human_review",       {}).get("weighted_score", 0)
    market_score = status.get("market_validation",  {}).get("weighted_score", 0)

    # 人工复审结论
    human_decision = status.get("human_review", {}).get("decision", "pending")

    # 综合加权（市场验证权重最高）
    if market_score > 0:
        composite = auto_score * 0.25 + human_score * 0.30 + market_score * 0.45
    elif human_score > 0:
        composite = auto_score * 0.40 + human_score * 0.60
    else:
        composite = auto_score

    # 决策规则
    if human_decision == "reject":
        decision = "ABANDON"
        reason   = "人工复审否决"
    elif composite >= THRESHOLDS["incubate"] and human_decision == "pass":
        decision = "INCUBATE"
        reason   = f"综合分{composite:.2f}，三层验证通过"
    elif composite >= THRESHOLDS["observe"]:
        decision = "OBSERVE"
        reason   = f"综合分{composite:.2f}，建议继续观察"
    else:
        decision = "ABANDON"
        reason   = f"综合分{composite:.2f}，低于立项门槛"

    report = {
        "ip_id":          ip_id,
        "ip_name":        ip_card["name"],
        "auto_score":     round(auto_score,   3),
        "human_score":    round(human_score,  3),
        "market_score":   round(market_score, 3),
        "composite_score":round(composite,    3),
        "decision":       decision,   # INCUBATE / OBSERVE / ABANDON
        "reason":         reason,
        "decided_at":     datetime.now().isoformat(),
        "next_actions":   _get_next_actions(decision)
    }

    _update_ip_value_status(ip_id, "decided", report)
    _log_decision(ip_id, "final_decision", decision == "INCUBATE",
                  composite, reason)
    return report

def _get_next_actions(decision: str) -> list:
    ACTIONS = {
        "INCUBATE": [
            "进行版权登记备案",
            "规划IP延伸内容（周边/衍生品/联名）",
            "制定商业授权方案",
            "扩大生产规模至每日4集"
        ],
        "OBSERVE": [
            "继续生产20集，积累更多市场数据",
            "尝试调整风格矩阵（题材/基调）",
            "优化口头禅和喜剧公式",
            "在不同平台进行A/B测试"
        ],
        "ABANDON": [
            "停止该IP生产，释放算力资源",
            "提取可复用的角色设定元素",
            "分析失败原因，改进下一个IP",
            "考虑角色卡根本性重设计"
        ]
    }
    return ACTIONS.get(decision, [])

# ─────────────────────────────────────────────
# 状态管理工具
# ─────────────────────────────────────────────

def get_ip_value_status(ip_id: str = None) -> dict:
    if not os.path.exists(IP_VALUE_FILE):
        return {} if ip_id else {}
    with open(IP_VALUE_FILE, encoding="utf-8") as f:
        all_status = json.load(f)
    return all_status.get(ip_id, {}) if ip_id else all_status

def _update_ip_value_status(ip_id: str, layer: str, data: dict):
    all_status = {}
    if os.path.exists(IP_VALUE_FILE):
        with open(IP_VALUE_FILE, encoding="utf-8") as f:
            all_status = json.load(f)

    if ip_id not in all_status:
        all_status[ip_id] = {}

    all_status[ip_id][layer.replace("_screened","_screen")
                          .replace("_reviewed","_review")
                          .replace("_validated","_validation")] = data
    all_status[ip_id]["updated_at"] = datetime.now().isoformat()

    os.makedirs(os.path.dirname(IP_VALUE_FILE), exist_ok=True)
    with open(IP_VALUE_FILE, "w", encoding="utf-8") as f:
        json.dump(all_status, f, ensure_ascii=False, indent=2)

def _log_decision(
    ip_id: str, layer: str,
    passed: bool, score: float, reason: str
):
    os.makedirs(os.path.dirname(DECISION_LOG), exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "ip_id":     ip_id,
        "layer":     layer,
        "passed":    passed,
        "score":     round(score, 3),
        "reason":    reason[:200]
    }
    with open(DECISION_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def get_decision_log(ip_id: str = None, limit: int = 50) -> list:
    if not os.path.exists(DECISION_LOG):
        return []
    logs = []
    with open(DECISION_LOG, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if ip_id and entry.get("ip_id") != ip_id:
                    continue
                logs.append(entry)
            except Exception:
                continue
    return list(reversed(logs))[:limit]

def _load_ip_card(ip_id: str) -> dict:
    with open(f"config/ip_cards/{ip_id}.json", encoding="utf-8") as f:
        return json.load(f)

def _load_recent_qc(ip_id: str, limit: int = 5) -> list:
    qc_dir = "../qc_reports"
    if not os.path.exists(qc_dir):
        return []
    reports = []
    for fname in sorted(os.listdir(qc_dir), reverse=True):
        if not fname.startswith(ip_id) or not fname.endswith("_qc.json"):
            continue
        with open(os.path.join(qc_dir, fname), encoding="utf-8") as f:
            reports.append(json.load(f))
        if len(reports) >= limit:
            break
    return reports