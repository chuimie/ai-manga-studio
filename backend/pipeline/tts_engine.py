# 配音引擎：根据分镜脚本生成角色配音音频

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

MIMO_API_KEY  = os.getenv("MIMO_API_KEY")
MIMO_BASE_URL = os.getenv("MIMO_BASE_URL")

def load_ip_card(ip_id: str) -> dict:
    with open(f"config/ip_cards/{ip_id}.json", encoding="utf-8") as f:
        return json.load(f)

def load_emotion_map() -> dict:
    with open("config/emotion_tts_map.json", encoding="utf-8") as f:
        return json.load(f)

def build_tts_request(
    dialogue: str,
    emotion_tag: str,
    voice_id: str,
    duration: float,
    emotion_map: dict
) -> dict:
    """
    构建MiMo TTS请求体
    将情绪标签转换为TTS指令
    """
    emotion_config = emotion_map.get(emotion_tag, {
        "style": "平和自然",
        "tags": []
    })

    style  = emotion_config["style"]
    tags   = emotion_config["tags"]

    # 构建富文本指令：在台词中插入音频标签
    tagged_text = dialogue
    if tags:
        tag_str    = "".join([f"<{t}>" for t in tags])
        tagged_text = f"{tag_str}{dialogue}"

    return {
        "model":    "mimo-v2.5-tts-voiceclone",
        "voice_id": voice_id,
        "text":     tagged_text,
        "style_prompt": style,
        "speed":    1.0,
        "target_duration": duration  # 对齐分镜时长
    }

def generate_frame_audio(
    frame: dict,
    ip_card: dict,
    emotion_map: dict,
    output_path: str
) -> str | None:
    """
    生成单帧配音
    无台词帧返回None（留白/场景切换格）
    """
    dialogue = frame.get("dialogue")
    if not dialogue:
        return None  # 无台词，跳过TTS

    voice_id     = ip_card["voice"]["voice_id"]
    emotion_tag  = frame.get("emotion_tag", "平静")

    payload = build_tts_request(
        dialogue    = dialogue,
        emotion_tag = emotion_tag,
        voice_id    = voice_id,
        duration    = frame["duration"],
        emotion_map = emotion_map
    )

    headers = {
        "Authorization": f"Bearer {MIMO_API_KEY}",
        "Content-Type":  "application/json"
    }

    response = requests.post(
        f"{MIMO_BASE_URL}/tts/generate",
        json=payload,
        headers=headers,
        timeout=60
    )
    response.raise_for_status()
    result = response.json()

    # 下载音频
    audio_url  = result["audio_url"]
    audio_data = requests.get(audio_url, timeout=30).content

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(audio_data)

    return output_path

def generate_all_audio(script: dict) -> list[str | None]:
    """
    批量生成一集所有配音
    返回音频路径列表（无台词帧为None）
    """
    ip_id       = script["ip_id"]
    episode_num = script["episode_num"]
    ep_id       = f"{ip_id}_ep{str(episode_num).zfill(3)}"
    audio_dir   = f"../assets/episodes/{ep_id}/audio"

    os.makedirs(audio_dir, exist_ok=True)

    ip_card     = load_ip_card(ip_id)
    emotion_map = load_emotion_map()
    audio_paths = []

    # 如果声线尚未创建，先通过VoiceDesign初始化
    ensure_voice_exists(ip_card)

    print(f"[配音引擎] 开始生成 {len(script['frames'])} 帧配音...")

    for frame in script["frames"]:
        fid       = frame["frame_id"]
        out_path  = os.path.join(audio_dir, f"audio_{str(fid).zfill(3)}.mp3")

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

def ensure_voice_exists(ip_card: dict):
    """如果声线ID未创建，通过VoiceDesign初始化"""
    voice_config = ip_card["voice"]
    voice_id     = voice_config["voice_id"]

    # 检查声线是否已注册
    headers = {"Authorization": f"Bearer {MIMO_API_KEY}"}
    resp    = requests.get(
        f"{MIMO_BASE_URL}/voices/{voice_id}",
        headers=headers,
        timeout=10
    )

    if resp.status_code == 404:
        # 声线不存在，通过VoiceDesign创建
        print(f"[配音引擎] 声线 {voice_id} 不存在，正在创建...")
        payload = {
            "voice_id":     voice_id,
            "model":        "mimo-v2.5-tts-voicedesign",
            "description":  voice_config["design_prompt"]
        }
        create_resp = requests.post(
            f"{MIMO_BASE_URL}/voices/design",
            json=payload,
            headers={**headers, "Content-Type": "application/json"},
            timeout=30
        )
        create_resp.raise_for_status()
        print(f"[配音引擎] 声线创建成功：{voice_id}")