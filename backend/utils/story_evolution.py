# AI剧情进化引擎
# 根据市场反馈数据，自动调整风格矩阵权重
# 实现：数据收集 → 效果分析 → 权重进化 → A/B测试 → 策略锁定

import os
import json
import statistics
import random
from datetime import datetime
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("AGNES_API_KEY"),
    base_url=os.getenv("AGNES_BASE_URL")
)

EVOLUTION_DIR    = "config/evolution"
EVOLUTION_FILE   = "config/evolution/weights_history.jsonl"
CURRENT_WEIGHTS  = "config/evolution/current_weights.json"
AB_TEST_FILE     = "config/evolution/ab_tests.json"
PERFORMANCE_FILE = "config/evolution/performance_log.jsonl"

# 风格矩阵维度
MATRIX_DIMS = {
    "genre":     ["都市", "玄幻", "悬疑", "爱情"],
    "tone":      ["热血", "治愈", "黑暗", "喜剧"],
    "narrative": ["线性叙事", "插叙", "多视角", "单场景深挖"],
    "pacing":    ["快节奏", "慢节奏", "张弛交替", "悬念递进"]
}

# 进化超参数
EVOLUTION_CONFIG = {
    "min_samples":       5,     # 最少需要N集数据才能进化
    "learning_rate":     0.15,  # 权重调整步长
    "decay_factor":      0.92,  # 历史数据衰减因子（越新越重要）
    "exploration_ratio": 0.20,  # 探索率（随机尝试新组合）
    "ab_test_ratio":     0.30,  # A/B测试流量比例
    "min_weight":        0.05,  # 单个选项最小权重
    "convergence_threshold": 0.01  # 权重变化低于此值视为收敛
}

# ─────────────────────────────────────────────
# 初始化 & 权重管理
# ─────────────────────────────────────────────

def init_weights(ip_id: str) -> dict:
    """初始化均匀权重（各选项等概率）"""
    weights = {}
    for dim, options in MATRIX_DIMS.items():
        n = len(options)
        weights[dim] = {opt: round(1.0/n, 4) for opt in options}
    return weights

def load_current_weights(ip_id: str) -> dict:
    """加载当前进化权重，不存在则初始化"""
    path = _weights_path(ip_id)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    weights = init_weights(ip_id)
    save_current_weights(ip_id, weights)
    return weights

def save_current_weights(ip_id: str, weights: dict,
                          reason: str = "manual"):
    """保存当前权重，并写入历史记录"""
    os.makedirs(EVOLUTION_DIR, exist_ok=True)

    # 写入当前权重
    path = _weights_path(ip_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(weights, f, ensure_ascii=False, indent=2)

    # 写入历史
    entry = {
        "timestamp": datetime.now().isoformat(),
        "ip_id":     ip_id,
        "reason":    reason,
        "weights":   weights
    }
    with open(EVOLUTION_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def _weights_path(ip_id: str) -> str:
    os.makedirs(EVOLUTION_DIR, exist_ok=True)
    return os.path.join(EVOLUTION_DIR, f"weights_{ip_id}.json")

# ─────────────────────────────────────────────
# 性能数据收集
# ─────────────────────────────────────────────

def log_episode_performance(
    ip_id:       str,
    ep_id:       str,
    style_combo: dict,   # 本集使用的风格组合
    metrics:     dict    # 市场表现数据
):
    """
    记录单集的风格组合与市场表现
    style_combo: {"genre":"都市","tone":"喜剧","narrative":"单场景深挖","pacing":"快节奏"}
    metrics:     {"completion_rate":0.72,"interaction_rate":0.08,"return_rate":0.45,"qc_score":0.83}
    """
    os.makedirs(EVOLUTION_DIR, exist_ok=True)

    # 计算综合得分
    composite = _calc_composite_score(metrics)

    entry = {
        "timestamp":   datetime.now().isoformat(),
        "ip_id":       ip_id,
        "ep_id":       ep_id,
        "style_combo": style_combo,
        "metrics":     metrics,
        "composite":   round(composite, 4)
    }

    with open(PERFORMANCE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return composite

def _calc_composite_score(metrics: dict) -> float:
    """计算综合表现分（0~1）"""
    weights = {
        "completion_rate":  0.35,
        "interaction_rate": 0.30,
        "return_rate":      0.20,
        "qc_score":         0.15
    }
    score = 0.0
    for k, w in weights.items():
        val = metrics.get(k, 0)
        # interaction_rate归一化（5%=满分）
        if k == "interaction_rate":
            val = min(1.0, val / 0.05)
        score += float(val) * w
    return min(1.0, score)

def load_performance_data(ip_id: str,
                           limit: int = 100) -> list:
    """加载指定IP的历史表现数据"""
    if not os.path.exists(PERFORMANCE_FILE):
        return []
    records = []
    with open(PERFORMANCE_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if entry.get("ip_id") == ip_id:
                    records.append(entry)
            except Exception:
                continue
    # 返回最新N条，越新权重越高
    return records[-limit:]

# ─────────────────────────────────────────────
# 核心进化算法
# ─────────────────────────────────────────────

def evolve_weights(ip_id: str) -> dict:
    """
    主进化函数：
    分析历史表现 → 计算维度贡献 → 更新权重 → 返回新权重
    """
    records  = load_performance_data(ip_id)
    config   = EVOLUTION_CONFIG

    if len(records) < config["min_samples"]:
        return {
            "status":  "insufficient_data",
            "message": f"需要至少{config['min_samples']}集数据，"
                       f"当前{len(records)}集",
            "weights": load_current_weights(ip_id)
        }

    current_weights = load_current_weights(ip_id)
    new_weights     = {dim: dict(opts)
                       for dim, opts in current_weights.items()}

    # 各维度各选项的加权平均得分
    dim_scores = {dim: {opt: [] for opt in opts}
                  for dim, opts in MATRIX_DIMS.items()}

    # 带时间衰减的得分统计
    n = len(records)
    for i, record in enumerate(records):
        decay  = config["decay_factor"] ** (n - 1 - i)
        combo  = record.get("style_combo", {})
        score  = record.get("composite", 0)

        for dim in MATRIX_DIMS:
            opt = combo.get(dim)
            if opt and opt in dim_scores[dim]:
                dim_scores[dim][opt].append(score * decay)

    # 计算每个维度的新权重
    changes = {}
    for dim in MATRIX_DIMS:
        opt_scores   = {}
        for opt in MATRIX_DIMS[dim]:
            vals = dim_scores[dim][opt]
            opt_scores[opt] = statistics.mean(vals) if vals else 0.0

        # 软max归一化（保留探索空间）
        total = sum(opt_scores.values())
        if total > 0:
            softmax = {opt: v/total for opt, v in opt_scores.items()}
        else:
            softmax = {opt: 1.0/len(MATRIX_DIMS[dim])
                       for opt in MATRIX_DIMS[dim]}

        # 混合更新：学习率插值 + 最小权重约束
        old_w   = current_weights.get(dim, {})
        new_dim = {}
        for opt in MATRIX_DIMS[dim]:
            old   = old_w.get(opt, 1.0/len(MATRIX_DIMS[dim]))
            target= softmax.get(opt, old)
            updated = old + config["learning_rate"] * (target - old)
            new_dim[opt] = max(config["min_weight"], updated)

        # 重归一化
        s = sum(new_dim.values())
        new_weights[dim] = {
            opt: round(v/s, 4) for opt, v in new_dim.items()
        }

        # 计算变化量
        changes[dim] = {
            opt: round(new_weights[dim][opt] - old_w.get(opt,0), 4)
            for opt in MATRIX_DIMS[dim]
        }

    # 判断是否收敛
    max_change = max(
        abs(v)
        for dim_c in changes.values()
        for v in dim_c.values()
    )
    converged  = max_change < config["convergence_threshold"]

    save_current_weights(ip_id, new_weights, reason="auto_evolution")

    return {
        "status":          "evolved",
        "ip_id":           ip_id,
        "samples_used":    len(records),
        "new_weights":     new_weights,
        "changes":         changes,
        "max_change":      round(max_change, 4),
        "converged":       converged,
        "evolved_at":      datetime.now().isoformat()
    }

def get_insights(ip_id: str) -> dict:
    """
    用LLM分析进化数据，生成人可读的策略洞察
    """
    records = load_performance_data(ip_id, limit=20)
    weights = load_current_weights(ip_id)

    if not records:
        return {"insights": "暂无足够数据生成洞察"}

    # 找出表现最好/最差的集
    sorted_recs = sorted(records, key=lambda r: r.get("composite",0))
    best  = sorted_recs[-3:]
    worst = sorted_recs[:3]

    prompt = f"""
你是一个漫剧内容策略分析师。
分析以下IP的风格进化数据，给出3条可执行的策略建议。

【当前最高权重风格组合】
题材：{max(weights.get('genre',{}), key=weights.get('genre',{}).get)}
基调：{max(weights.get('tone',{}),  key=weights.get('tone',{}).get)}
叙事：{max(weights.get('narrative',{}),key=weights.get('narrative',{}).get)}
节奏：{max(weights.get('pacing',{}),key=weights.get('pacing',{}).get)}

【表现最好的3集风格组合】
{json.dumps([r['style_combo'] for r in best], ensure_ascii=False)}
综合分：{[round(r['composite'],3) for r in best]}

【表现最差的3集风格组合】
{json.dumps([r['style_combo'] for r in worst], ensure_ascii=False)}
综合分：{[round(r['composite'],3) for r in worst]}

返回JSON：
{{
  "top_combo":   "当前最优风格组合描述（20字以内）",
  "insights":    ["洞察1","洞察2","洞察3"],
  "suggestions": ["建议1","建议2","建议3"],
  "avoid":       ["应避免的风格组合1","组合2"]
}}
"""
    try:
        resp   = client.chat.completions.create(
            model=os.getenv("AGNES_TEXT_MODEL"),
            messages=[{"role":"user","content":prompt}],
            response_format={"type":"json_object"},
            temperature=0.5
        )
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return {"insights": "分析失败，请检查API配置"}

# ─────────────────────────────────────────────
# 进化感知的风格选择器
# ─────────────────────────────────────────────

def sample_style_combo(ip_id:     str,
                        force_explore: bool = False) -> dict:
    """
    根据当前权重，采样下一集的风格组合
    使用ε-greedy策略：以exploration_ratio概率随机探索
    """
    weights = load_current_weights(ip_id)
    config  = EVOLUTION_CONFIG
    combo   = {}

    for dim, options in MATRIX_DIMS.items():
        dim_weights = weights.get(dim, {})
        opts        = list(MATRIX_DIMS[dim])
        w_list      = [dim_weights.get(o, 1.0/len(opts)) for o in opts]

        if force_explore or random.random() < config["exploration_ratio"]:
            # 探索：均匀随机选择
            combo[dim] = random.choice(opts)
        else:
            # 利用：按权重加权采样
            total = sum(w_list)
            probs = [w/total for w in w_list]
            r     = random.random()
            cum   = 0.0
            for opt, p in zip(opts, probs):
                cum += p
                if r <= cum:
                    combo[dim] = opt
                    break
            else:
                combo[dim] = opts[-1]

    return combo

# ─────────────────────────────────────────────
# A/B 测试框架
# ─────────────────────────────────────────────

def create_ab_test(
    ip_id:       str,
    test_name:   str,
    variant_a:   dict,   # 对照组风格配置
    variant_b:   dict,   # 实验组风格配置
    episodes_per_variant: int = 5
) -> dict:
    """创建A/B测试"""
    os.makedirs(EVOLUTION_DIR, exist_ok=True)

    test = {
        "test_id":   f"ab_{ip_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "ip_id":     ip_id,
        "test_name": test_name,
        "status":    "running",
        "variant_a": {"config": variant_a, "episodes": [], "scores": []},
        "variant_b": {"config": variant_b, "episodes": [], "scores": []},
        "target_episodes": episodes_per_variant,
        "created_at":      datetime.now().isoformat(),
        "concluded_at":    None,
        "winner":          None
    }

    tests = _load_ab_tests()
    tests[test["test_id"]] = test
    _save_ab_tests(tests)
    return test

def record_ab_result(
    test_id:  str,
    variant:  str,    # "a" 或 "b"
    ep_id:    str,
    score:    float
):
    """记录A/B测试单集结果"""
    tests = _load_ab_tests()
    if test_id not in tests:
        return

    test = tests[test_id]
    key  = f"variant_{variant}"
    test[key]["episodes"].append(ep_id)
    test[key]["scores"].append(score)

    # 判断是否达到目标集数
    a_done = len(test["variant_a"]["scores"]) >= test["target_episodes"]
    b_done = len(test["variant_b"]["scores"]) >= test["target_episodes"]

    if a_done and b_done:
        # 得出结论
        avg_a  = statistics.mean(test["variant_a"]["scores"])
        avg_b  = statistics.mean(test["variant_b"]["scores"])
        winner = "a" if avg_a >= avg_b else "b"

        test["status"]       = "concluded"
        test["winner"]       = winner
        test["avg_a"]        = round(avg_a, 4)
        test["avg_b"]        = round(avg_b, 4)
        test["concluded_at"] = datetime.now().isoformat()

    _save_ab_tests(tests)

def conclude_ab_test(test_id: str) -> dict:
    """
    强制结束A/B测试，将胜出方的风格写入权重
    """
    tests = _load_ab_tests()
    if test_id not in tests:
        return {"error": "测试不存在"}

    test   = tests[test_id]
    ip_id  = test["ip_id"]
    winner = test.get("winner")

    if not winner:
        # 手动触发结论
        a_s = test["variant_a"]["scores"]
        b_s = test["variant_b"]["scores"]
        avg_a = statistics.mean(a_s) if a_s else 0
        avg_b = statistics.mean(b_s) if b_s else 0
        winner = "a" if avg_a >= avg_b else "b"
        test["winner"] = winner
        test["avg_a"]  = round(avg_a, 4)
        test["avg_b"]  = round(avg_b, 4)

    # 将胜出配置注入权重提升
    winning_config = test[f"variant_{winner}"]["config"]
    weights        = load_current_weights(ip_id)

    for dim, opt in winning_config.items():
        if dim in weights and opt in weights[dim]:
            # 将胜出选项权重提升10%
            weights[dim][opt] = min(
                0.7,
                weights[dim][opt] + 0.10
            )
            # 重归一化
            total = sum(weights[dim].values())
            weights[dim] = {
                k: round(v/total, 4)
                for k, v in weights[dim].items()
            }

    save_current_weights(ip_id, weights, reason=f"ab_test_winner_{test_id}")

    test["status"]       = "concluded"
    test["concluded_at"] = datetime.now().isoformat()
    _save_ab_tests(tests)

    return {
        "test_id": test_id,
        "winner":  winner,
        "config":  winning_config,
        "weights_updated": True
    }

def get_ab_tests(ip_id: str = None) -> list:
    tests = _load_ab_tests()
    result = list(tests.values())
    if ip_id:
        result = [t for t in result if t.get("ip_id") == ip_id]
    return sorted(result, key=lambda t: t.get("created_at",""),
                  reverse=True)

def _load_ab_tests() -> dict:
    if not os.path.exists(AB_TEST_FILE):
        return {}
    with open(AB_TEST_FILE, encoding="utf-8") as f:
        return json.load(f)

def _save_ab_tests(tests: dict):
    os.makedirs(EVOLUTION_DIR, exist_ok=True)
    with open(AB_TEST_FILE, "w", encoding="utf-8") as f:
        json.dump(tests, f, ensure_ascii=False, indent=2)

# ─────────────────────────────────────────────
# 进化历史查询
# ─────────────────────────────────────────────

def get_evolution_history(ip_id: str,
                           limit: int = 20) -> list:
    """获取权重进化历史"""
    if not os.path.exists(EVOLUTION_FILE):
        return []
    records = []
    with open(EVOLUTION_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if entry.get("ip_id") == ip_id:
                    records.append(entry)
            except Exception:
                continue
    return list(reversed(records))[:limit]

def get_performance_summary(ip_id: str) -> dict:
    """获取表现数据摘要（用于仪表盘展示）"""
    records = load_performance_data(ip_id)
    if not records:
        return {"total": 0}

    scores = [r["composite"] for r in records]
    return {
        "total":        len(records),
        "avg_score":    round(statistics.mean(scores), 4),
        "best_score":   round(max(scores), 4),
        "worst_score":  round(min(scores), 4),
        "trend":        _calc_trend(scores),
        "best_combo":   _find_best_combo(records),
        "worst_combo":  _find_worst_combo(records)
    }

def _calc_trend(scores: list) -> str:
    if len(scores) < 3:
        return "stable"
    recent = scores[-5:]
    if recent[-1] > recent[0] + 0.03:
        return "up"
    elif recent[-1] < recent[0] - 0.03:
        return "down"
    return "stable"

def _find_best_combo(records: list) -> dict:
    if not records:
        return {}
    best = max(records, key=lambda r: r.get("composite", 0))
    return best.get("style_combo", {})

def _find_worst_combo(records: list) -> dict:
    if not records:
        return {}
    worst = min(records, key=lambda r: r.get("composite", 0))
    return worst.get("style_combo", {})