# 合成引擎：将视频片段 + 音频 + 字幕合并为完整一集mp4

import os
import json
import subprocess
import ffmpeg
from dotenv import load_dotenv

load_dotenv()

def build_concat_file(video_paths: list, ep_id: str) -> str:
    """生成FFmpeg拼接文件"""
    concat_path = f"../assets/episodes/{ep_id}/concat.txt"
    with open(concat_path, "w") as f:
        for path in video_paths:
            if path and os.path.exists(path):
                f.write(f"file '{os.path.abspath(path)}'\n")
    return concat_path

def build_subtitle_file(script: dict, ep_id: str) -> str:
    """生成SRT字幕文件"""
    srt_path = f"../assets/episodes/{ep_id}/subtitles.srt"
    current_time = 0.0
    srt_lines    = []
    sub_index    = 1

    for frame in script["frames"]:
        dialogue = frame.get("dialogue")
        duration = frame["duration"]

        if dialogue:
            start = format_srt_time(current_time)
            end   = format_srt_time(current_time + duration)
            srt_lines.append(f"{sub_index}\n{start} --> {end}\n{dialogue}\n")
            sub_index += 1

        current_time += duration

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))

    return srt_path

def format_srt_time(seconds: float) -> str:
    """秒数转SRT时间格式 HH:MM:SS,mmm"""
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def merge_frame(
    video_path: str,
    audio_path: str | None,
    duration: float,
    output_path: str
) -> str:
    """合并单帧视频+音频"""
    if audio_path and os.path.exists(audio_path):
        # 有音频：混合视频+配音
        (
            ffmpeg
            .output(
                ffmpeg.input(video_path),
                ffmpeg.input(audio_path),
                output_path,
                t=duration,
                vcodec="libx264",
                acodec="aac",
                audio_bitrate="192k",
                shortest=None
            )
            .overwrite_output()
            .run(quiet=True)
        )
    else:
        # 无音频：纯视频片段（静音）
        (
            ffmpeg
            .input(video_path)
            .output(
                output_path,
                t=duration,
                vcodec="libx264",
                an=None   # 无音频轨
            )
            .overwrite_output()
            .run(quiet=True)
        )
    return output_path

def concat_and_burn_subtitles(
    ep_id: str,
    concat_file: str,
    subtitle_file: str,
    output_path: str
) -> str:
    """拼接所有片段并烧录字幕"""
    # Step1：拼接所有视频片段
    concat_output = f"../assets/episodes/{ep_id}/concat_raw.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-f",       "concat",
        "-safe",    "0",
        "-i",       concat_file,
        "-c",       "copy",
        concat_output
    ], check=True, capture_output=True)

    # Step2：烧录字幕
    (
        ffmpeg
        .input(concat_output)
        .output(
            output_path,
            vf=f"subtitles={subtitle_file}:force_style='FontName=PingFang SC,"
               f"FontSize=18,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,"
               f"Outline=1,Alignment=2'",
            vcodec="libx264",
            acodec="aac",
            crf=18,
            preset="fast"
        )
        .overwrite_output()
        .run(quiet=True)
    )

    # 清理临时文件
    os.remove(concat_output)
    return output_path

def merge_episode(
    script: dict,
    video_paths: list[str],
    audio_paths: list[str | None]
) -> str:
    """
    主函数：合并完整一集
    返回最终mp4路径
    """
    ip_id       = script["ip_id"]
    episode_num = script["episode_num"]
    ep_id       = f"{ip_id}_ep{str(episode_num).zfill(3)}"
    merged_dir  = f"../assets/episodes/{ep_id}/merged_frames"
    os.makedirs(merged_dir, exist_ok=True)

    print(f"[合成引擎] 开始合并 {len(script['frames'])} 个片段...")

    # Step1：逐帧合并视频+音频
    merged_paths = []
    for i, frame in enumerate(script["frames"]):
        fid        = frame["frame_id"]
        vid_path   = video_paths[i]
        aud_path   = audio_paths[i]
        out_path   = os.path.join(merged_dir, f"merged_{str(fid).zfill(3)}.mp4")

        if not vid_path or not os.path.exists(vid_path):
            print(f"[合成引擎] 第{fid}帧视频缺失，跳过")
            continue

        try:
            merge_frame(vid_path, aud_path, frame["duration"], out_path)
            merged_paths.append(out_path)
            print(f"[合成引擎] 第{fid}帧合并 ✅")
        except Exception as e:
            print(f"[合成引擎] 第{fid}帧合并失败 ❌ {e}")

    # Step2：生成拼接文件 + 字幕文件
    concat_file   = build_concat_file(merged_paths, ep_id)
    subtitle_file = build_subtitle_file(script, ep_id)

    # Step3：拼接并烧录字幕
    final_output = f"../assets/episodes/{ep_id}/output.mp4"
    concat_and_burn_subtitles(ep_id, concat_file, subtitle_file, final_output)

    size_mb = os.path.getsize(final_output) / (1024 * 1024)
    print(f"[合成引擎] ✅ 完整一集已生成：{final_output} ({size_mb:.1f}MB)")
    return final_output