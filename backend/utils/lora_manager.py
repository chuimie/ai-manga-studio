# LoRA训练管理：参考图生成 → 训练集构建 → 云端/本地训练 → 权重保存

import os
import json
import time
import shutil
import requests
import zipfile
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

AGNES_API_KEY  = os.getenv("AGNES_API_KEY")
AGNES_BASE_URL = os.getenv("AGNES_BASE_URL")
AGNES_IMG_MODEL= os.getenv("AGNES_IMAGE_MODEL")

# 训练模式：runpod（云端GPU） / local（本地CPU）
LORA_TRAIN_MODE = os.getenv("LORA_TRAIN_MODE", "runpod")

# RunPod配置
RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")
RUNPOD_BASE_URL= "https://api.runpod.ai/v2"

# 云端训练参数
LORA_TRAIN_CONFIG = {
    "num_train_images":    30,     # 参考图数量
    "train_steps":         1500,   # 训练步数
    "learning_rate":       0.0001,
    "network_dim":         32,
    "network_alpha":       16,
    "resolution":          512,
    "batch_size":          1
}

# 训练状态文件
LORA_STATUS_FILE = "config/lora_status.json"

# ─────────────────────────────────────────────
# Step 1：生成参考图训练集
# ─────────────────────────────────────────────

# 30种姿势/表情/场景变体
REFERENCE_VARIANTS = [
    # 表情组（10种）
    {"pose": "front face, neutral expression",       "scene": "white background"},
    {"pose": "front face, happy smile",              "scene": "white background"},
    {"pose": "front face, surprised expression",     "scene": "white background"},
    {"pose": "front face, confused expression",      "scene": "white background"},
    {"pose": "front face, laughing",                 "scene": "white background"},
    {"pose": "front face, pouting",                  "scene": "white background"},
    {"pose": "front face, crying dramatically",      "scene": "white background"},
    {"pose": "front face, smug expression",          "scene": "white background"},
    {"pose": "front face, sleepy eyes",              "scene": "white background"},
    {"pose": "front face, determined expression",    "scene": "white background"},
    # 半身姿势组（10种）
    {"pose": "upper body, arms crossed",             "scene": "simple room background"},
    {"pose": "upper body, waving hand",              "scene": "outdoor background"},
    {"pose": "upper body, pointing forward",         "scene": "classroom background"},
    {"pose": "upper body, hands on hips",            "scene": "street background"},
    {"pose": "upper body, sitting at desk",          "scene": "study room"},
    {"pose": "upper body, side profile left",        "scene": "white background"},
    {"pose": "upper body, side profile right",       "scene": "white background"},
    {"pose": "upper body, 3/4 angle",                "scene": "white background"},
    {"pose": "upper body, looking up",               "scene": "outdoor sky background"},
    {"pose": "upper body, looking down",             "scene": "floor view"},
    # 全身姿势组（10种）
    {"pose": "full body, standing straight",         "scene": "white background"},
    {"pose": "full body, running pose",              "scene": "outdoor"},
    {"pose": "full body, jumping",                   "scene": "outdoor"},
    {"pose": "full body, sitting cross-legged",      "scene": "floor"},
    {"pose": "full body, kneeling",                  "scene": "white background"},
    {"pose": "full body, side view walking",         "scene": "street"},
    {"pose": "full body, back view",                 "scene": "white background"},
    {"pose": "full body, action pose arms raised",   "scene": "white background"},
    {"pose": "full body, crouching",                 "scene": "white background"},
    {"pose": "full body, lying down looking up",     "scene": "grass field"}
]

def generate_reference_images(ip_card: dict) -> list[str]:
    """
    Step 1：根据IP角色卡生成30张参考图
    返回本地保存路径列表
    """
    ip_id      = ip_card["ip_id"]
    visual     = ip_card["visual"]
    ref_dir    = f"../assets/reference/{ip_id}_training"
    os.makedirs(ref_dir, exist_ok=True)

    appearance = visual["appearance"]
    art_style  = visual["style"]
    seed       = visual.get("fixed_seed", 42)

    saved_paths = []
    headers = {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Content-Type": "application/json"
    }

    print(f"[LoRA管理] 开始生成 {len(REFERENCE_VARIANTS)} 张参考图...")

    for i, variant in enumerate(REFERENCE_VARIANTS):
        out_path = os.path.join(ref_dir, f"ref_{str(i+1).zfill(3)}.png")

        if os.path.exists(out_path):
            print(f"[LoRA管理] ref_{i+1} 已存在，跳过")
            saved_paths.append(out_path)
            continue

        prompt = (
            f"{appearance}, {variant['pose']}, "
            f"{variant['scene']}, {art_style}, "
            f"high quality, consistent character design, "
            f"no text, no watermark, clean lines"
        )

        payload = {
            "model":           AGNES_IMG_MODEL,
            "prompt":          prompt,
            "negative_prompt": "blurry, deformed, extra limbs, watermark, text",
            "seed":            seed + i,
            "width":           512,
            "height":          512,
            "num_inference_steps": 30,
            "guidance_scale":  7.5
        }

        print(f"[LoRA管理] 生成第{i+1}/30张...", end=" ")
        try:
            resp = requests.post(
                f"{AGNES_BASE_URL}/images/generate",
                json=payload, headers=headers, timeout=60
            )
            resp.raise_for_status()
            img_url  = resp.json()["data"][0]["url"]
            img_data = requests.get(img_url, timeout=30).content

            with open(out_path, "wb") as f:
                f.write(img_data)
            saved_paths.append(out_path)
            print("✅")
        except Exception as e:
            print(f"❌ {e}")

        time.sleep(0.5)  # 避免API限流

    print(f"[LoRA管理] 参考图生成完成：{len(saved_paths)}/30 张")
    return saved_paths

# ─────────────────────────────────────────────
# Step 2：构建训练集（图文对）
# ─────────────────────────────────────────────

def build_training_dataset(ip_card: dict, ref_paths: list[str]) -> str:
    """
    Step 2：构建标准LoRA训练集
    每张图配对一个caption文件
    返回训练集目录路径
    """
    ip_id    = ip_card["ip_id"]
    ip_name  = ip_card.get("name", ip_id)
    visual   = ip_card["visual"]
    dataset_dir = f"../assets/reference/{ip_id}_dataset"
    os.makedirs(dataset_dir, exist_ok=True)

    appearance = visual["appearance"]
    art_style  = visual["style"]

    # LoRA触发词：唯一标识该角色
    trigger_word = f"{ip_id.replace('_','')}char"

    print(f"[LoRA管理] 构建训练集，触发词：{trigger_word}")

    for i, (ref_path, variant) in enumerate(zip(ref_paths, REFERENCE_VARIANTS)):
        if not ref_path or not os.path.exists(ref_path):
            continue

        # 复制图像
        dst_img = os.path.join(dataset_dir, f"{i+1:03d}.png")
        shutil.copy(ref_path, dst_img)

        # 生成caption
        caption = (
            f"{trigger_word}, {appearance}, "
            f"{variant['pose']}, {variant['scene']}, "
            f"{art_style}"
        )
        dst_cap = os.path.join(dataset_dir, f"{i+1:03d}.txt")
        with open(dst_cap, "w", encoding="utf-8") as f:
            f.write(caption)

    # 保存训练集元数据
    meta = {
        "ip_id":        ip_id,
        "ip_name":      ip_name,
        "trigger_word": trigger_word,
        "image_count":  len(ref_paths),
        "created_at":   datetime.now().isoformat(),
        "train_config": LORA_TRAIN_CONFIG,
        "dataset_dir":  dataset_dir
    }
    with open(os.path.join(dataset_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"[LoRA管理] 训练集构建完成：{dataset_dir}")
    return dataset_dir

# ─────────────────────────────────────────────
# Step 3：打包上传到云端GPU（RunPod）
# ─────────────────────────────────────────────

def package_dataset(dataset_dir: str, ip_id: str) -> str:
    """打包训练集为zip"""
    zip_path = f"../assets/reference/{ip_id}_dataset.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(dataset_dir):
            zf.write(os.path.join(dataset_dir, fname), fname)
    size_mb = os.path.getsize(zip_path) / (1024*1024)
    print(f"[LoRA管理] 训练集打包完成：{zip_path} ({size_mb:.1f}MB)")
    return zip_path

def submit_runpod_training(ip_card: dict, dataset_dir: str) -> str:
    """
    Step 3：提交RunPod训练任务
    返回RunPod job_id
    """
    ip_id = ip_card["ip_id"]
    meta_path = os.path.join(dataset_dir, "meta.json")
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    trigger_word = meta["trigger_word"]
    config       = LORA_TRAIN_CONFIG

    headers = {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "input": {
            "ip_id":          ip_id,
            "trigger_word":   trigger_word,
            "dataset_dir":    dataset_dir,
            "output_path":    f"../models/lora/{ip_id}.safetensors",
            "train_steps":    config["train_steps"],
            "learning_rate":  config["learning_rate"],
            "network_dim":    config["network_dim"],
            "network_alpha":  config["network_alpha"],
            "resolution":     config["resolution"],
            "batch_size":     config["batch_size"]
        }
    }

    # 提交到RunPod Serverless端点
    ENDPOINT_ID = os.getenv("RUNPOD_LORA_ENDPOINT_ID", "")
    resp = requests.post(
        f"{RUNPOD_BASE_URL}/{ENDPOINT_ID}/run",
        json=payload, headers=headers, timeout=30
    )
    resp.raise_for_status()
    job_id = resp.json()["id"]

    print(f"[LoRA管理] RunPod任务已提交：job_id={job_id}")
    return job_id

def poll_runpod_job(job_id: str, max_wait: int = 14400) -> dict:
    """
    轮询RunPod训练任务状态
    max_wait=14400 = 4小时超时
    """
    headers  = {"Authorization": f"Bearer {RUNPOD_API_KEY}"}
    ENDPOINT_ID = os.getenv("RUNPOD_LORA_ENDPOINT_ID", "")
    elapsed  = 0
    interval = 30  # 每30秒检查一次

    print(f"[LoRA管理] 等待训练完成（最长4小时）...")

    while elapsed < max_wait:
        resp   = requests.get(
            f"{RUNPOD_BASE_URL}/{ENDPOINT_ID}/status/{job_id}",
            headers=headers, timeout=15
        )
        status = resp.json()
        state  = status.get("status", "")

        elapsed_min = elapsed // 60
        print(f"[LoRA管理] 训练状态：{state} （已等待{elapsed_min}分钟）")

        if state == "COMPLETED":
            return status
        elif state in ["FAILED", "CANCELLED"]:
            raise Exception(f"RunPod训练失败：{status.get('error', '未知错误')}")

        time.sleep(interval)
        elapsed += interval

    raise TimeoutError("LoRA训练超时：超过4小时")

def download_lora_weights(job_result: dict, ip_id: str) -> str:
    """
    Step 4：下载训练好的LoRA权重文件
    返回本地权重路径
    """
    output     = job_result.get("output", {})
    weight_url = output.get("lora_url") or output.get("model_url")

    if not weight_url:
        raise Exception("RunPod返回结果中缺少权重URL")

    os.makedirs("../models/lora", exist_ok=True)
    out_path   = f"../models/lora/{ip_id}.safetensors"

    print(f"[LoRA管理] 下载权重文件...")
    resp = requests.get(weight_url, stream=True, timeout=120)
    resp.raise_for_status()

    total    = int(resp.headers.get("content-length", 0))
    downloaded = 0
    with open(out_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded / total * 100
                print(f"\r[LoRA管理] 下载进度：{pct:.1f}%", end="")
    print()
    print(f"[LoRA管理] ✅ 权重已保存：{out_path}")
    return out_path

# ─────────────────────────────────────────────
# 全流程入口
# ─────────────────────────────────────────────

def train_lora_full_pipeline(ip_id: str) -> str:
    """
    一键执行完整LoRA训练流水线
    Step 1：生成参考图
    Step 2：构建训练集
    Step 3：训练（云端RunPod / 本地CPU）
    Step 4：保存权重
    返回权重文件路径
    """
    update_lora_status(ip_id, "generating_refs", 0)

    # 加载IP卡
    with open(f"config/ip_cards/{ip_id}.json", encoding="utf-8") as f:
        ip_card = json.load(f)

    print(f"\n{'='*50}")
    print(f"🎨 LoRA训练启动：{ip_card['name']}（{ip_id}）")
    print(f"   训练模式: {'🌐 RunPod云端' if LORA_TRAIN_MODE == 'runpod' else '💻 本地CPU'}")
    print(f"{'='*50}\n")

    # Step 1
    print("📸 Step 1/4：生成参考图...")
    update_lora_status(ip_id, "generating_refs", 10)
    ref_paths = generate_reference_images(ip_card)

    # Step 2
    print("\n📁 Step 2/4：构建训练集...")
    update_lora_status(ip_id, "building_dataset", 30)
    dataset_dir = build_training_dataset(ip_card, ref_paths)

    # Step 3：根据模式选择训练方式
    if LORA_TRAIN_MODE == "local":
        weight_path = _train_local(ip_card, dataset_dir, ip_id)
    else:
        weight_path = _train_runpod(ip_card, dataset_dir, ip_id)

    # 更新IP卡中的LoRA路径
    ip_card["visual"]["lora_weight"] = weight_path
    with open(f"config/ip_cards/{ip_id}.json", "w", encoding="utf-8") as f:
        json.dump(ip_card, f, ensure_ascii=False, indent=2)

    update_lora_status(ip_id, "completed", 100, weight_path=weight_path)

    print(f"\n✅ LoRA训练完成！权重：{weight_path}")
    return weight_path


def _train_runpod(ip_card: dict, dataset_dir: str, ip_id: str) -> str:
    """RunPod云端训练（原流程）"""
    print("\n☁️  Step 3/4：提交云端训练...")
    update_lora_status(ip_id, "training", 40)
    job_id     = submit_runpod_training(ip_card, dataset_dir)
    job_result = poll_runpod_job(job_id)
    update_lora_status(ip_id, "downloading", 90)

    print("\n⬇️  Step 4/4：下载权重文件...")
    return download_lora_weights(job_result, ip_id)


def _train_local(ip_card: dict, dataset_dir: str, ip_id: str) -> str:
    """本地CPU训练"""
    from local_lora_trainer import train_lora_local, LOCAL_TRAIN_CONFIG

    meta_path = os.path.join(dataset_dir, "meta.json")
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    trigger_word = meta["trigger_word"]
    output_path  = f"../models/lora/{ip_id}.safetensors"
    os.makedirs("../models/lora", exist_ok=True)

    print(f"\n💻 Step 3/4：本地CPU训练...")
    update_lora_status(ip_id, "training", 40)

    # 合并配置：本地配置优先，云端配置作为fallback
    config = {**LORA_TRAIN_CONFIG, **LOCAL_TRAIN_CONFIG}

    weight_path = train_lora_local(
        dataset_dir   = dataset_dir,
        output_path   = output_path,
        trigger_word  = trigger_word,
        base_model    = config["base_model"],
        resolution    = config["resolution"],
        train_steps   = config["train_steps"],
        learning_rate = config["learning_rate"],
        network_dim   = config["network_dim"],
        network_alpha = config["network_alpha"],
        batch_size    = config["batch_size"],
    )

    update_lora_status(ip_id, "completed", 100, weight_path=weight_path)
    return weight_path

# ─────────────────────────────────────────────
# 训练状态管理
# ─────────────────────────────────────────────

def update_lora_status(
    ip_id: str,
    status: str,
    progress: int,
    weight_path: str = None,
    error: str = None
):
    """更新训练状态文件（供前端轮询）"""
    all_status = {}
    if os.path.exists(LORA_STATUS_FILE):
        with open(LORA_STATUS_FILE, encoding="utf-8") as f:
            all_status = json.load(f)

    all_status[ip_id] = {
        "ip_id":       ip_id,
        "status":      status,
        "progress":    progress,
        "updated_at":  datetime.now().isoformat(),
        "weight_path": weight_path,
        "error":       error
    }

    os.makedirs(os.path.dirname(LORA_STATUS_FILE), exist_ok=True)
    with open(LORA_STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_status, f, ensure_ascii=False, indent=2)

def get_lora_status(ip_id: str = None) -> dict:
    """获取训练状态"""
    if not os.path.exists(LORA_STATUS_FILE):
        return {}
    with open(LORA_STATUS_FILE, encoding="utf-8") as f:
        all_status = json.load(f)
    if ip_id:
        return all_status.get(ip_id, {"status": "not_started", "progress": 0})
    return all_status

def lora_exists(ip_id: str) -> bool:
    """检查LoRA权重是否已存在"""
    path = f"../models/lora/{ip_id}.safetensors"
    return os.path.exists(path)