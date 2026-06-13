# 内容分发助手
# 根据剧集内容，自动生成各平台适配的发布素材

import os
import json
from datetime import datetime
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("AGNES_API_KEY"),
    base_url=os.getenv("AGNES_BASE_URL")
)

DIST_DIR = "../exports/distribution"

# 平台配置
PLATFORM_CONFIGS = {
    "抖音": {
        "title_max":    15,
        "desc_max":     100,
        "hashtag_count": 5,
        "tone":         "口语化、接地气、有梗",
        "cta":          "关注不迷路，每天更新！"
    },
    "B站": {
        "title_max":    80,
        "desc_max":     500,
        "hashtag_count": 8,
        "tone":         "二次元友好、专业感、有情怀",
        "cta":          "三连支持！每天2集持续更新中~"
    },
    "小红书": {
        "title_max":    20,
        "desc_max":     200,
        "hashtag_count": 10,
        "tone":         "可爱、生活化、情感共鸣",
        "cta":          "收藏这个系列！萌到我了🥺"
    },
    "微博": {
        "title_max":    0,    # 微博无标题
        "desc_max":     140,
        "hashtag_count": 3,
        "tone":         "简短有力、话题感强",
        "cta":          "转发给朋友一起看！"
    },
    "YouTube": {
        "title_max":    100,
        "desc_max":     1000,
        "hashtag_count": 5,
        "tone":         "International friendly, engaging",
        "cta":          "Subscribe for daily episodes!"
    }
}

def generate_distribution_package(
    ep_id: str,
    platforms: list = None
) -> dict:
    """
    为指定剧集生成全平台发布素材包
    platforms: 目标平台列表，None则生成全部
    """
    script    = _load_script(ep_id)
    if not script:
        raise ValueError(f"找不到剧集脚本：{ep_id}")

    ip_id     = script.get("ip_id", "")
    ip_card   = _load_ip_card(ip_id)
    ep_num    = script.get("episode_num", 1)
    ep_title  = script.get("episode_title", f"第{ep_num}集")

    target_platforms = platforms or list(PLATFORM_CONFIGS.keys())
    results   = {}

    for platform in target_platforms:
        config = PLATFORM_CONFIGS.get(platform, {})
        copy   = _generate_platform_copy(
            script, ip_card, ep_title, platform, config
        )
        results[platform] = copy

    # 生成通用素材
    common = _generate_common_assets(script, ip_card, ep_title)

    package = {
        "ep_id":      ep_id,
        "ip_id":      ip_id,
        "ip_name":    ip_card.get("name", ""),
        "ep_title":   ep_title,
        "ep_num":     ep_num,
        "platforms":  results,
        "common":     common,
        "generated_at": datetime.now().isoformat()
    }

    # 保存到本地
    _save_distribution_package(ep_id, package)
    return package

def _generate_platform_copy(
    script: dict, ip_card: dict,
    ep_title: str, platform: str, config: dict
) -> dict:
    """为特定平台生成发布文案"""

    # 提取剧集精华
    frames      = script.get("frames", [])
    dialogues   = [
        f["dialogue"] for f in frames
        if f.get("dialogue")
    ][:5]
    key_scene   = frames[len(frames)//2].get("scene", "") if frames else ""

    prompt = f"""
你是一个{platform}平台的内容运营专家。
根据以下漫剧信息，生成一套完整的{platform}发布素材。

【角色信息】
角色名：{ip_card.get('name', '')}
性格：{', '.join(ip_card.get('character',{}).get('核心性格',[]))}
口头禅：{', '.join(ip_card.get('character',{}).get('口头禅',[]))}

【本集信息】
标题：{ep_title}
主题：{script.get('theme', '')}
精彩台词片段：{' | '.join(dialogues[:3])}
关键场景：{key_scene}

【平台要求】
文案风格：{config.get('tone', '自然')}
标题字数：{"无标题" if not config.get('title_max') else f"≤{config['title_max']}字"}
正文字数：≤{config.get('desc_max', 200)}字
话题标签：{config.get('hashtag_count', 5)}个
行动引导：{config.get('cta', '点赞关注')}

请生成：
1. 标题（{"微博无需标题，跳过" if platform=="微博" else f"≤{config.get('title_max',20)}字，吸引点击"}）
2. 正文文案（≤{config.get('desc_max',200)}字）
3. 话题标签（{config.get('hashtag_count',5)}个，含#号）
4. 评论区置顶回复（引导互动）
5. 最佳发布时间建议

返回JSON：
{{
  "title":      "标题（微博留空）",
  "body":       "正文文案",
  "hashtags":   ["#话题1", "#话题2"],
  "pinned_comment": "置顶评论",
  "best_post_time": "建议时间段",
  "emoji_style": "适合此平台的emoji用法说明"
}}
"""

    response = client.chat.completions.create(
        model=os.getenv("AGNES_TEXT_MODEL"),
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.8
    )
    result = json.loads(response.choices[0].message.content)
    result["platform"] = platform
    result["char_count"] = {
        "title": len(result.get("title", "")),
        "body":  len(result.get("body",  ""))
    }
    return result

def _generate_common_assets(
    script: dict, ip_card: dict, ep_title: str
) -> dict:
    """生成平台无关的通用素材"""

    frames    = script.get("frames", [])
    dialogues = [f["dialogue"] for f in frames if f.get("dialogue")]

    prompt = f"""
根据以下漫剧信息，生成通用传播素材。

角色：{ip_card.get('name','')}，{', '.join(ip_card.get('character',{}).get('核心性格',[]))}
本集标题：{ep_title}
核心台词：{' | '.join(dialogues[:5])}
口头禅：{', '.join(ip_card.get('character',{}).get('口头禅',[]))}

请生成：
1. 3条最适合截图配字的台词（配上角色名）
2. 1段50字以内的系列简介（用于各平台主页介绍）
3. 5个通用话题标签（中文）
4. 1个系列Slogan（≤15字，朗朗上口）
5. 3条适合私信/群发的种草话术

返回JSON：
{{
  "quote_cards": [
    {{"dialogue": "台词", "character": "角色名", "emotion": "情绪"}},
  ],
  "series_intro": "系列简介",
  "universal_tags": ["标签1"],
  "slogan": "系列Slogan",
  "word_of_mouth": ["种草话术1", "话术2", "话术3"]
}}
"""

    response = client.chat.completions.create(
        model=os.getenv("AGNES_TEXT_MODEL"),
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.85
    )
    return json.loads(response.choices[0].message.content)

def _save_distribution_package(ep_id: str, package: dict):
    os.makedirs(DIST_DIR, exist_ok=True)
    path = os.path.join(DIST_DIR, f"{ep_id}_dist.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(package, f, ensure_ascii=False, indent=2)

def get_distribution_history(ip_id: str = None) -> list:
    """获取分发历史"""
    if not os.path.exists(DIST_DIR):
        return []
    results = []
    for fname in sorted(os.listdir(DIST_DIR), reverse=True):
        if not fname.endswith("_dist.json"):
            continue
        path = os.path.join(DIST_DIR, fname)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if ip_id and data.get("ip_id") != ip_id:
            continue
        results.append({
            "ep_id":      data.get("ep_id"),
            "ip_id":      data.get("ip_id"),
            "ip_name":    data.get("ip_name"),
            "ep_title":   data.get("ep_title"),
            "platforms":  list(data.get("platforms", {}).keys()),
            "generated_at": data.get("generated_at")
        })
    return results

def _load_script(ep_id: str) -> Optional[dict]:
    path = f"../assets/episodes/{ep_id}/script.json"
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def _load_ip_card(ip_id: str) -> dict:
    path = f"config/ip_cards/{ip_id}.json"
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)