# 配音引擎：根据分镜脚本生成角色配音音频
# 使用 MiMo Chat Completions API（OpenAI 兼容格式）

import os
import json
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

MIMO_API_KEY  = os.getenv("MIMO_API_KEY")
MIMO_BASE_URL = os.getenv("MIMO_BASE_URL")  # https://api.xiaomimimo.com/v1

HEADERS = {
    "Authorization": f"Bearer {MIMO_API_KEY}",
    "Content-Type":  "application/json"
}


# ── 内置音色列表（按 IP 卡语音语言/性别匹配） ──
BUILTIN_VOICES = {
    "zh_female": ["冰糖", "茉莉", "苏打"],
    "zh_male":   ["白桦"],
    "en_female": ["Mia", "Chloe"],
    "en_male":   ["Milo", "Dean"]
}
DEFAULT_VOICE = "mimo_default"


def load_ip_card(ip_id: str) -> dict:
    with open(f"config/ip_cards/{ip_id}.json", encoding="utf-8") as f:
        return json.load(f)


def load_emotion_map() -> dict:
    with open("config/emotion_tts_map.json", encoding="utf-8") as f:
        return json.load(f)


def _pick_voice(ip_card: dict) -> str:
    """从 IP 卡语音配置中选择合适的预置音色"""
    voice_config = ip_card.get("voice", {})
    preferred = voice_config.get("voice_id", "")
    if preferred and preferred not in ("custom", "default"):
        return preferred

    lang = voice_config.get("language", "zh")
    gender = voice_config.get("gender", "female")
    key = f"{lang}_{gender}"
    pool = BUILTIN_VOICES.get(key, BUILTIN_VOICES["zh_female"])
    return pool[0] if pool else DEFAULT_VOICE


def _build_messages(dialogue: str, style: str, tags: list[str]) -> list[dict]:
    """构建 Chat Completions messages"""
    # user 消息：语气/风格指令
    style_prompt = f"用{style}的语气朗读" if style else "自然朗读"

    # assistant 消息：待合成的文本 + 音频标签
    tagged = dialogue
    if tags:
        tag_str = "".join([f"<{t}>" for t in tags])
        tagged = f"{tag_str}{dialogue}"

    return [
        {"role": "user",     "content": style_prompt},
        {"role": "assistant", "content": tagged}
    ]


def generate_frame_audio(
    frame: dict,
    ip_card: dict,
    emotion_map: dict,
    output_path: str
) -> str | None:
    """
    生成单帧配音
    无台词帧返回 None（留白/场景切换格）
    """
    dialogue = frame.get("dialogue")
    if not dialogue:
        return None

    emotion_tag = frame.get("emotion_tag", "平静")
    emotion_cfg = emotion_map.get(emotion_tag, {"style": "平和自然", "tags": []})

    voice = _pick_voice(ip_card)
    messages = _build_messages(dialogue, emotion_cfg["style"], emotion_cfg["tags"])

    payload = {
        "model": "mimo-v2.5-tts",
        "messages": messages,
        "audio": {"format": "mp3", "voice": voice}
    }

    response = requests.post(
        f"{MIMO_BASE_URL}/chat/completions",
        json=payload,
        headers=HEADERS,
        timeout=60
    )
    response.raise_for_status()
    result = response.json()

    audio_b64 = result["choices"][0]["message"]["audio"]["data"]
    audio_data = base64.b64decode(audio_b64)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(audio_data)

    return output_path


def ensure_voice_exists(ip_card: dict):
    """
    通过 VoiceDesign 模型创建定制声线（如需）
    MiMo 的 VoiceDesign 通过 Chat Completions 调用，不需要预注册
    """
    voice_config = ip_card["voice"]
    design_prompt = voice_config.get("design_prompt", "")
    if not design_prompt:
        print("[配音引擎] 使用预置音色，无需设计声线")
        return

    print(f"[配音引擎] 正在设计声线: {voice_config['voice_id']}...")
    payload = {
        "model": "mimo-v2.5-tts-voicedesign",
        "messages": [
            {"role": "user", "content": design_prompt},
            {"role": "assistant", "content": "你好，我是新设计的声线。"}
        ],
        "audio": {"format": "wav", "voice": "mimo_default"}
    }
    resp = requests.post(
        f"{MIMO_BASE_URL}/chat/completions",
        json=payload,
        headers=HEADERS,
        timeout=30
    )
    if resp.status_code == 200:
        print(f"[配音引擎] 声线设计成功: {voice_config['voice_id']}")
    else:
        print(f"[配音引擎] 声线设计失败: HTTP {resp.status_code}")
        print(f"  使用预置音色作为后备")


def generate_all_audio(script: dict) -> list[str | None]:
    """
    批量生成一集所有配音
    返回音频路径列表（无台词帧为 None）
    """
    ip_id       = script["ip_id"]
    episode_num = script["episode_num"]
    ep_id       = f"{ip_id}_ep{str(episode_num).zfill(3)}"
    audio_dir   = f"../assets/episodes/{ep_id}/audio"

    os.makedirs(audio_dir, exist_ok=True)

    ip_card     = load_ip_card(ip_id)
    emotion_map = load_emotion_map()
    audio_paths = []

    ensure_voice_exists(ip_card)

    print(f"[配音引擎] 开始生成 {len(script['frames'])} 帧配音...")

    for frame in script["frames"]:
        fid      = frame["frame_id"]
        out_path = os.path.join(audio_dir, f"audio_{str(fid).zfill(3)}.mp3")

        if not frame.get("dialogue"):
            audio_paths.append(None)
            print(f"[配音引擎] 第{fid}帧：无台词，跳过")
            continue

        print(f"[配音引擎] 生成第{fid}帧配音...", end=" ")
        try:
            path = generate_frame_audio(frame, ip_card, emotion_map, out_path)
            audio_paths.append(path)
            print("✅")
        except Exception as e:
            print(f"❌ {e}")
            audio_paths.append(None)

    # 保存音频索引
    index_path = f"../assets/episodes/{ep_id}/audio_index.json"
    with open(index_path, "w") as f:
        json.dump(audio_paths, f, indent=2)

    success = len([p for p in audio_paths if p])
    print(f"[配音引擎] 完成：{success}帧有效配音")
    return audio_paths