# 视觉引擎：根据分镜脚本生成静态图像序列

import os
import json
import requests
from dotenv import load_dotenv
from utils.prompt_logger import log_prompt

load_dotenv()

AGNES_API_KEY   = os.getenv("AGNES_API_KEY")
AGNES_BASE_URL  = os.getenv("AGNES_BASE_URL")
AGNES_IMG_MODEL = os.getenv("AGNES_IMAGE_MODEL")

def load_ip_card(ip_id: str) -> dict:
    with open(f"config/ip_cards/{ip_id}.json", encoding="utf-8") as f:
        return json.load(f)

def build_image_prompt(frame: dict, ip_card: dict) -> str:
    """
    构建Agnes Image生成Prompt
    将分镜场景描述 + 角色外貌 + 画风合并
    """
    visual   = ip_card["visual"]
    char     = ip_card["character"]

    base_appearance = visual["appearance"]
    art_style       = visual["style"]
    char_state      = frame["character_state"]
    scene           = frame["scene"]
    camera          = frame["camera"]

    prompt = (
        f"{base_appearance}, {char_state}, "
        f"{scene}, {art_style}, "
        f"{camera} shot, "
        f"manga panel, high quality, "
        f"consistent character design, "
        f"no text, no watermark"
    )
    return prompt

def build_negative_prompt(ip_card: dict) -> str:
    forbidden = ip_card["visual"].get("forbidden_visual", "")
    base_neg  = (
        "blurry, low quality, deformed, "
        "inconsistent character, watermark, "
        "text, signature, extra limbs"
    )
    return f"{forbidden}, {base_neg}" if forbidden else base_neg

def generate_frame_image(
    frame: dict,
    ip_card: dict,
    output_path: str
) -> str:
    """
    生成单帧图像，保存到output_path
    返回保存路径
    """
    prompt   = build_image_prompt(frame, ip_card)
    neg_prompt = build_negative_prompt(ip_card)
    seed     = ip_card["visual"]["fixed_seed"]
    lora     = ip_card["visual"]["lora_weight"]

    log_prompt(
        engine    = "image",
        stage     = f"frame_{str(frame['frame_id']).zfill(3)}",
        prompt    = {
            "positive": prompt,
            "negative": neg_prompt,
            "seed":     ip_card["visual"]["fixed_seed"],
            "lora":     ip_card["visual"]["lora_weight"]
        },
        ip_id     = ip_card["ip_id"],
        frame_id  = frame["frame_id"],
        model     = os.getenv("AGNES_IMAGE_MODEL"),
        extra     = {
            "scene":          frame["scene"],
            "character_state":frame["character_state"],
            "camera":         frame["camera"]
        }
    )

    payload = {
        "model":           AGNES_IMG_MODEL,
        "prompt":          prompt,
        "negative_prompt": neg_prompt,
        "seed":            seed,
        "width":           768,
        "height":          1024,   # 竖版漫剧比例
        "num_inference_steps": 30,
        "guidance_scale":  7.5,
        "lora_weights":    lora
    }

    headers = {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Content-Type":  "application/json"
    }

    response = requests.post(
        f"{AGNES_BASE_URL}/images/generate",
        json=payload,
        headers=headers,
        timeout=60
    )
    response.raise_for_status()
    result = response.json()

    # 下载图像到本地
    img_url = result["data"][0]["url"]
    img_data = requests.get(img_url, timeout=30).content

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(img_data)

    return output_path

def generate_all_frames(script: dict) -> list[str]:
    """
    批量生成一集所有分镜图像
    返回图像路径列表
    """
    ip_id      = script["ip_id"]
    episode_num = script["episode_num"]
    ep_id      = f"{ip_id}_ep{str(episode_num).zfill(3)}"
    frames_dir = f"../assets/episodes/{ep_id}/frames"
    ip_card    = load_ip_card(ip_id)

    os.makedirs(frames_dir, exist_ok=True)
    image_paths = []

    print(f"[视觉引擎] 开始生成 {len(script['frames'])} 帧图像...")

    for frame in script["frames"]:
        fid        = frame["frame_id"]
        out_path   = os.path.join(frames_dir, f"frame_{str(fid).zfill(3)}.png")

        print(f"[视觉引擎] 生成第{fid}帧...", end=" ")
        try:
            path = generate_frame_image(frame, ip_card, out_path)
            image_paths.append(path)
            print("✅")
        except Exception as e:
            print(f"❌ {e}")
            image_paths.append(None)

    # 保存图像路径索引
    index_path = f"../assets/episodes/{ep_id}/frames_index.json"
    with open(index_path, "w") as f:
        json.dump(image_paths, f, indent=2)

    success = len([p for p in image_paths if p])
    print(f"[视觉引擎] 完成：{success}/{len(script['frames'])}帧生成成功")
    return image_paths