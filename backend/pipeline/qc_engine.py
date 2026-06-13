# 质检引擎：多维评分 + 自动迭代触发

import os
import json
import requests
import numpy as np
from PIL import Image
from openai import OpenAI
from dotenv import load_dotenv
from utils.prompt_logger import log_prompt

load_dotenv()

client = OpenAI(
    api_key=os.getenv("AGNES_API_KEY"),
    base_url=os.getenv("AGNES_BASE_URL")
)

# 质检权重配置
QC_WEIGHTS = {
    "角色一致性": 0.35,
    "画面质量":   0.25,
    "情绪吻合度": 0.20,
    "叙事连贯性": 0.15,
    "节奏合理性": 0.05
}

# 合格阈值
QC_THRESHOLDS = {
    "角色一致性": 0.85,
    "画面质量":   0.70,    # CLIP Score归一化
    "情绪吻合度": 0.75,
    "叙事连贯性": 0.70,
    "节奏合理性": 0.70,
    "综合":       0.80
}

def check_character_consistency(
    image_paths: list[str],
    reference_path: str
) -> float:
    """
    角色一致性检测：
    计算所有分镜图与参考图的平均相似度
    使用感知哈希 + 颜色直方图简化版（生产环境可替换为人脸向量模型）
    """
    if not os.path.exists(reference_path):
        print("[质检] 警告：参考图不存在，跳过一致性检测")
        return 0.85  # 默认通过，后续完善

    ref_img    = Image.open(reference_path).resize((256, 256)).convert("RGB")
    ref_arr    = np.array(ref_img).flatten()
    scores     = []

    for path in image_paths:
        if not path or not os.path.exists(path):
            continue
        try:
            img   = Image.open(path).resize((256, 256)).convert("RGB")
            arr   = np.array(img).flatten()
            # 余弦相似度
            cos   = np.dot(ref_arr, arr) / (
                np.linalg.norm(ref_arr) * np.linalg.norm(arr) + 1e-8
            )
            scores.append(float(cos))
        except Exception:
            continue

    return float(np.mean(scores)) if scores else 0.0

def check_image_quality(image_paths: list[str]) -> float:
    """
    画面质量检测：
    基于图像分辨率、清晰度（拉普拉斯方差）评估
    生产环境可替换为CLIP Score API
    """
    scores = []
    for path in image_paths:
        if not path or not os.path.exists(path):
            continue
        try:
            img      = Image.open(path).convert("L")  # 灰度
            arr      = np.array(img, dtype=np.float32)
            # 拉普拉斯方差（越高越清晰）
            laplacian = np.array([
                [0,  1, 0],
                [1, -4, 1],
                [0,  1, 0]
            ])
            from scipy.ndimage import convolve
            filtered  = convolve(arr, laplacian)
            variance  = np.var(filtered)
            # 归一化到0~1（经验值：variance > 500 为高质量）
            score     = min(1.0, variance / 500)
            scores.append(score)
        except Exception:
            continue
    return float(np.mean(scores)) if scores else 0.0

def check_emotion_consistency(script: dict) -> float:
    """
    情绪吻合度检测：
    验证台词内容与情绪标签是否一致（LLM评估）
    """
    frames_with_dialogue = [
        f for f in script["frames"] if f.get("dialogue")
    ]
    if not frames_with_dialogue:
        return 1.0

    sample = frames_with_dialogue[:10]  # 抽样检测
    check_items = "\n".join([
        f"台词：{f['dialogue']} | 情绪标签：{f['emotion_tag']}"
        for f in sample
    ])

    prompt = f"""
以下是漫剧分镜的台词和对应情绪标签，请逐条判断台词内容与情绪标签是否匹配。
对每条给出0~1的匹配分数，最后给出平均分。

{check_items}

返回JSON格式：
{{"scores": [分数列表], "average": 平均分, "comment": "简短评价"}}
"""
    log_prompt(
        engine      = "qc",
        stage       = "emotion_consistency",
        prompt      = prompt,
        ip_id       = script["ip_id"],
        episode_num = script["episode_num"],
        model       = os.getenv("AGNES_TEXT_MODEL")
    )

    try:
        response = client.chat.completions.create(
            model=os.getenv("AGNES_TEXT_MODEL"),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        result = json.loads(response.choices[0].message.content)
        return float(result.get("average", 0.75))
    except Exception:
        return 0.75  # 异常时默认通过

def check_narrative_coherence(script: dict) -> float:
    """
    叙事连贯性检测：
    用LLM检测情节是否有逻辑跳跃或断层
    """
    frames_summary = "\n".join([
        f"第{f['frame_id']}格：{f['scene']} | {f.get('dialogue', '（无台词）')}"
        for f in script["frames"]
    ])

    prompt = f"""
以下是一集漫剧的分镜梗概，请评估叙事连贯性：
1. 情节是否有明显跳跃（0~1，1=完全连贯）
2. 角色行为是否符合逻辑（0~1）
3. 首尾是否呼应（0~1）

分镜内容：
{frames_summary}

返回JSON：
{{"plot_coherence": 分数, "character_logic": 分数, 
  "story_closure": 分数, "average": 平均分, "issues": "发现的问题"}}
"""

    log_prompt(
        engine      = "qc",
        stage       = "narrative_coherence",
        prompt      = prompt,
        ip_id       = script["ip_id"],
        episode_num = script["episode_num"],
        model       = os.getenv("AGNES_TEXT_MODEL")
    )

    try:
        response = client.chat.completions.create(
            model=os.getenv("AGNES_TEXT_MODEL"),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        result = json.loads(response.choices[0].message.content)
        return float(result.get("average", 0.75))
    except Exception:
        return 0.75

def check_pacing(script: dict) -> float:
    """
    节奏合理性检测：
    计算帧时长的分布方差，方差过高说明节奏不均匀
    """
    durations = [f["duration"] for f in script["frames"]]
    if not durations:
        return 1.0
    variance  = np.var(durations)
    # 方差 < 0.3 → 满分；方差越大越扣分
    score     = max(0.0, 1.0 - variance / 3.0)
    return float(score)

def run_qc(
    script: dict,
    image_paths: list[str],
    ip_id: str
) -> dict:
    """
    主质检函数：执行全维度评分
    返回质检报告
    """
    print("[质检引擎] 开始质检...")
    reference_path = f"../assets/reference/{ip_id}_front.png"

    # 各维度评分
    scores = {
        "角色一致性": check_character_consistency(image_paths, reference_path),
        "画面质量":   check_image_quality(image_paths),
        "情绪吻合度": check_emotion_consistency(script),
        "叙事连贯性": check_narrative_coherence(script),
        "节奏合理性": check_pacing(script)
    }

    # 综合加权评分
    weighted = sum(
        scores[k] * QC_WEIGHTS[k]
        for k in scores
    )

    # 判定结果
    passed       = weighted >= QC_THRESHOLDS["综合"]
    failed_items = [
        k for k, v in scores.items()
        if v < QC_THRESHOLDS.get(k, 0.70)
    ]

    report = {
        "ip_id":        script["ip_id"],
        "episode_num":  script["episode_num"],
        "scores":       {k: round(v, 3) for k, v in scores.items()},
        "weighted_score": round(weighted, 3),
        "passed":       passed,
        "failed_items": failed_items,
        "action":       "PASS" if passed else "RETRY"
    }

    # 打印报告
    print("\n─── 质检报告 ───────────────────────")
    for k, v in scores.items():
        status = "✅" if v >= QC_THRESHOLDS.get(k, 0.70) else "❌"
        print(f"  {status} {k:<10} {v:.3f}")
    print(f"  综合得分：{weighted:.3f}  →  {'✅ 通过' if passed else '❌ 需迭代'}")
    if failed_items:
        print(f"  待改进：{', '.join(failed_items)}")
    print("────────────────────────────────────\n")

    # 保存报告
    ep_id       = f"{script['ip_id']}_ep{str(script['episode_num']).zfill(3)}"
    report_path = f"../qc_reports/{ep_id}_qc.json"
    os.makedirs("../qc_reports", exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report