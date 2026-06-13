# 视频引擎：将静态分镜图动态化

import os
import json
import requests
import time
from dotenv import load_dotenv
from utils.prompt_logger import log_prompt

load_dotenv()

AGNES_API_KEY    = os.getenv("AGNES_API_KEY")
AGNES_BASE_URL   = os.getenv("AGNES_BASE_URL")
AGNES_VID_MODEL  = os.getenv("AGNES_VIDEO_MODEL")

# 运镜指令映射
CAMERA_MOTION_MAP = {
    "推近":  "slow zoom in, camera slowly pushes toward subject",
    "拉远":  "slow zoom out, camera pulls back to reveal scene",
    "跟随":  "camera follows character movement, slight shake",
    "固定":  "static shot, no camera movement",
    "特写":  "extreme close up, face or detail focus"
}

def image_to_video(
    image_path: str,
    camera_motion: str,
    duration: float,
    output_path: str
) -> str:
    """
    将单帧静态图动态化
    返回视频片段路径
    """
    motion_prompt = CAMERA_MOTION_MAP.get(camera_motion, "static shot")

    log_prompt(
        engine   = "video",
        stage    = os.path.basename(image_path),
        prompt   = {
            "motion_prompt": motion_prompt,
            "camera_raw":    camera_motion,
            "duration":      duration,
            "source_image":  image_path
        },
        model    = os.getenv("AGNES_VIDEO_MODEL")
    )

    # 时长截断：Agnes Video单次最长6秒
    clip_duration = min(duration, 6.0)

    with open(image_path, "rb") as img_file:
        files   = {"image": img_file}
        payload = {
            "model":          AGNES_VID_MODEL,
            "motion_prompt":  motion_prompt,
            "duration":       clip_duration,
            "fps":            24,
            "quality":        "high"
        }
        headers = {"Authorization": f"Bearer {AGNES_API_KEY}"}

        response = requests.post(
            f"{AGNES_BASE_URL}/videos/generate",
            data=payload,
            files=files,
            headers=headers,
            timeout=120
        )
        response.raise_for_status()
        result = response.json()

    # 轮询任务状态（异步生成）
    task_id  = result.get("task_id")
    video_url = poll_video_task(task_id)

    # 下载视频
    video_data = requests.get(video_url, timeout=60).content
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(video_data)

    return output_path

def poll_video_task(task_id: str, max_wait: int = 300) -> str:
    """轮询视频生成任务，返回视频URL"""
    headers  = {"Authorization": f"Bearer {AGNES_API_KEY}"}
    elapsed  = 0
    interval = 5

    while elapsed < max_wait:
        resp   = requests.get(
            f"{AGNES_BASE_URL}/videos/tasks/{task_id}",
            headers=headers,
            timeout=30
        )
        status = resp.json()

        if status["status"] == "completed":
            return status["video_url"]
        elif status["status"] == "failed":
            raise Exception(f"视频生成失败：{status.get('error')}")

        time.sleep(interval)
        elapsed += interval
        print(f"[视频引擎] 等待视频生成... {elapsed}s")

    raise TimeoutError(f"视频生成超时：task_id={task_id}")

def generate_all_videos(script: dict, image_paths: list[str]) -> list[str]:
    """
    批量将所有分镜图动态化
    返回视频片段路径列表
    """
    ip_id       = script["ip_id"]
    episode_num = script["episode_num"]
    ep_id       = f"{ip_id}_ep{str(episode_num).zfill(3)}"
    videos_dir  = f"../assets/episodes/{ep_id}/videos"

    os.makedirs(videos_dir, exist_ok=True)
    video_paths = []

    print(f"[视频引擎] 开始动态化 {len(script['frames'])} 帧...")

    for i, frame in enumerate(script["frames"]):
        fid        = frame["frame_id"]
        img_path   = image_paths[i]

        if not img_path or not os.path.exists(img_path):
            print(f"[视频引擎] 第{fid}帧图像缺失，跳过")
            video_paths.append(None)
            continue

        out_path = os.path.join(videos_dir, f"video_{str(fid).zfill(3)}.mp4")
        print(f"[视频引擎] 动态化第{fid}帧...", end=" ")

        try:
            path = image_to_video(
                image_path   = img_path,
                camera_motion = frame["camera"],
                duration     = frame["duration"],
                output_path  = out_path
            )
            video_paths.append(path)
            print("✅")
        except Exception as e:
            print(f"❌ {e}")
            video_paths.append(None)

    # 保存视频索引
    index_path = f"../assets/episodes/{ep_id}/videos_index.json"
    with open(index_path, "w") as f:
        json.dump(video_paths, f, indent=2)

    success = len([p for p in video_paths if p])
    print(f"[视频引擎] 完成：{success}/{len(script['frames'])}个视频片段")
    return video_paths