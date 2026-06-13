# 将草稿转换为标准角色卡JSON并写入文件

import json
import os
import random
from datetime import datetime

def draft_to_card(draft, ip_id: str) -> dict:
    """将CharacterDraft转换为标准角色卡JSON"""
    return {
        "ip_id": ip_id,
        "name": draft.name or f"角色_{ip_id}",
        "created_at": datetime.now().isoformat(),
        "visual": {
            "appearance": draft.appearance,
            "style": draft.art_style,
            "lora_weight": f"models/lora/{ip_id}.safetensors",
            "reference_images": [f"assets/reference/{ip_id}_front.png"],
            "fixed_seed": random.randint(1, 99999),
            "forbidden_visual": draft.forbidden or ""
        },
        "voice": {
            "method": draft.voice_method,
            "design_prompt": draft.voice_prompt,
            "clone_reference": None,
            "voice_id": f"{ip_id}_voice"
        },
        "character": {
            "核心性格": draft.personality,
            "说话习惯": draft.speech_pattern or "",
            "口头禅": draft.catchphrases,
            "喜剧公式": draft.comedy_formula or "",
            "禁忌边界": draft.forbidden or "不表现攻击性/负面情绪"
        },
        "world": {
            "setting": draft.world_setting,
            "genre": draft.genre,
            "tone": draft.tone,
            "pacing": draft.pacing,
            "narrative": draft.narrative
        }
    }

def save_card(card: dict, config_path: str = "config/ip_cards") -> str:
    """写入角色卡JSON文件，返回文件路径"""
    os.makedirs(config_path, exist_ok=True)
    filepath = os.path.join(config_path, f"{card['ip_id']}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(card, f, ensure_ascii=False, indent=2)
    return filepath

def get_next_ip_id(config_path: str = "config/ip_cards") -> str:
    """自动生成下一个IP编号"""
    os.makedirs(config_path, exist_ok=True)
    existing = [f for f in os.listdir(config_path) if f.endswith(".json")]
    return f"ip_{str(len(existing) + 1).zfill(3)}"