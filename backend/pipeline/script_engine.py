# 剧本引擎：根据IP角色卡生成结构化分镜脚本

import json
import os
import sys
import random
from openai import OpenAI
from dotenv import load_dotenv
from utils.prompt_logger import log_prompt

sys.path.append("utils")
from story_evolution import sample_style_combo, load_current_weights

load_dotenv()

client = OpenAI(
    api_key=os.getenv("AGNES_API_KEY"),
    base_url=os.getenv("AGNES_BASE_URL")
)

# 分镜时长协议
FRAME_DURATION = {
    "对话格": (3, 5),
    "动作格": (4, 6),
    "留白格": (1, 2),
    "场景切换": (0.5, 0.5)
}

def load_ip_card(ip_id: str) -> dict:
    path = f"config/ip_cards/{ip_id}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def load_style_matrix() -> dict:
    with open("config/style_matrix.json", encoding="utf-8") as f:
        return json.load(f)

def load_emotion_map() -> dict:
    with open("config/emotion_tts_map.json", encoding="utf-8") as f:
        return json.load(f)

def build_script_prompt(ip_card: dict, episode_theme: str = None) -> str:
    """构建剧本生成Prompt"""
    char = ip_card["character"]
    world = ip_card["world"]

    # 随机注入风格变量，防止同质化
    matrix = load_style_matrix()
    random_narrative = random.choice(matrix["narrative"])

    theme = episode_theme or "随机日常事件"

    return f"""
你是一个漫剧剧本生成器。根据以下角色信息，生成一集完整的动态漫剧分镜脚本。

【角色信息】
姓名：{ip_card['name']}
性格：{', '.join(char['核心性格'])}
说话习惯：{char['说话习惯']}
口头禅：{', '.join(char['口头禅'])}
喜剧公式：{char['喜剧公式']}
世界观：{world['setting']}
基调：{world['tone']}
节奏：{world['pacing']}
叙事结构：{random_narrative}
本集主题：{theme}

【生成要求】
- 总时长：约120秒（2分钟）
- 分镜数量：20~30格
- 每格必须包含：场景描述、台词、情绪标签、分镜类型、时长
- 节奏要快，每格信息密度高
- 结尾必须呼应喜剧公式：翻车→完全不反思→下一个轮回
- 禁止出现：{char['禁忌边界']}

【输出格式】严格JSON：
{{
  "episode_title": "集名",
  "total_duration": 预估总秒数,
  "theme": "本集主题",
  "frames": [
    {{
      "frame_id": 1,
      "frame_type": "对话格/动作格/留白格/场景切换",
      "scene": "场景描述（用于图像生成的视觉Prompt）",
      "character_state": "角色当前状态/动作/表情",
      "dialogue": "台词（无台词填null）",
      "emotion_tag": "情绪标签（从：愤怒/悲伤/兴奋/恐惧/平静/讽刺/迷茫/自信/委屈/紧张 中选）",
      "camera": "运镜指令（推近/拉远/跟随/固定/特写）",
      "duration": 时长秒数
    }}
  ]
}}
"""

def generate_script(ip_id: str, episode_num: int,
                    theme: str = None,
                    force_combo: dict = None) -> dict:
    """
    force_combo：强制指定风格组合（A/B测试时使用）
    不传则由进化引擎自动采样
    """
    ip_card = load_ip_card(ip_id)

    # ▼ 进化感知：从权重中采样风格组合
    if force_combo:
        style_combo = force_combo
    else:
        style_combo = sample_style_combo(ip_id)

    print(f"[剧本引擎] 风格组合：{style_combo}")

    prompt = build_script_prompt(ip_card, theme, style_combo)

    # Prompt审计
    log_prompt(
        engine="script", stage="generate_script",
        prompt=prompt, ip_id=ip_id, episode_num=episode_num,
        model=os.getenv("AGNES_TEXT_MODEL"),
        extra={"theme": theme, "style_combo": style_combo}
    )

    response = client.chat.completions.create(
        model=os.getenv("AGNES_TEXT_MODEL"),
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.85
    )
    result = json.loads(response.choices[0].message.content)
    result["ip_id"]        = ip_id
    result["episode_num"]  = episode_num
    result["ip_name"]      = ip_card["name"]
    result["style_combo"]  = style_combo   # ← 保存本集风格组合

    total = sum(f["duration"] for f in result["frames"])
    result["actual_duration"] = total

    save_script(result, ip_id, episode_num)
    return result

def build_script_prompt(ip_card: dict, theme: str,
                         style_combo: dict) -> str:
    """将进化权重选出的风格组合注入Prompt"""
    char  = ip_card["character"]
    world = ip_card["world"]

    return f"""
你是一个漫剧剧本生成器。根据以下角色信息，生成一集完整的动态漫剧分镜脚本。

【角色信息】
姓名：{ip_card['name']}
性格：{', '.join(char['核心性格'])}
说话习惯：{char['说话习惯']}
口头禅：{', '.join(char['口头禅'])}
喜剧公式：{char['喜剧公式']}
世界观：{world['setting']}

【本集风格参数（进化引擎选定）】
题材：{style_combo.get('genre',  world.get('genre','都市'))}
基调：{style_combo.get('tone',   world.get('tone','喜剧'))}
叙事结构：{style_combo.get('narrative','单场景深挖')}
节奏：{style_combo.get('pacing',  world.get('pacing','快节奏'))}
本集主题：{theme or '随机日常事件'}

【生成要求】
- 总时长：约120秒
- 分镜数量：20~30格
- 禁止出现：{char['禁忌边界']}

【输出格式】严格JSON（结构同前）
"""

def save_script(script: dict, ip_id: str, episode_num: int):
    ep_id  = f"{ip_id}_ep{str(episode_num).zfill(3)}"
    outdir = f"../assets/episodes/{ep_id}"
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "script.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)
    print(f"[剧本引擎] 脚本已保存：{path}")