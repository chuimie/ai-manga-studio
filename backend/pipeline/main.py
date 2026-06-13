# 主控入口：一键启动全自动生产流水线

import os
import sys
import json
import argparse
from datetime import datetime
from dotenv import load_dotenv

# 引入六大引擎
from script_engine import generate_script
from image_engine  import generate_all_frames
from video_engine  import generate_all_videos
from tts_engine    import generate_all_audio
from merge_engine  import merge_episode
from qc_engine     import run_qc

load_dotenv()

# ── 全局配置 ──────────────────────────────────────
MAX_RETRY     = 3       # 质检不过最多重试次数
QC_PASS_SCORE = 0.80    # 质检通过阈值

def load_ip_card(ip_id: str) -> dict:
    with open(f"config/ip_cards/{ip_id}.json", encoding="utf-8") as f:
        return json.load(f)

def get_next_episode_num(ip_id: str) -> int:
    """自动计算下一集集号"""
    ep_base = f"../assets/episodes"
    if not os.path.exists(ep_base):
        return 1
    existing = [
        d for d in os.listdir(ep_base)
        if d.startswith(ip_id) and os.path.isdir(os.path.join(ep_base, d))
    ]
    return len(existing) + 1

def run_pipeline(
    ip_id: str,
    episode_num: int = None,
    theme: str = None,
    retry_count: int = 0
) -> dict:
    """
    执行单集完整生产流水线
    返回生产结果报告
    """
    start_time  = datetime.now()
    ep_num      = episode_num or get_next_episode_num(ip_id)

    print(f"\n{'='*50}")
    print(f"🎬 开始生产：{ip_id} 第{ep_num}集")
    print(f"   主题：{theme or '自动生成'}")
    print(f"   重试次数：{retry_count}/{MAX_RETRY}")
    print(f"{'='*50}\n")

    try:
        # ── 引擎1：剧本 ───────────────────────────
        print("📝 [1/6] 剧本引擎启动...")
        script = generate_script(ip_id, ep_num, theme)
        print(f"   ✅ 剧本生成：{script['episode_title']}，{len(script['frames'])}帧")

        # ── 引擎2：图像 ───────────────────────────
        print("\n🖼️  [2/6] 视觉引擎启动...")
        image_paths = generate_all_frames(script)
        valid_images = len([p for p in image_paths if p])
        print(f"   ✅ 图像生成：{valid_images}/{len(script['frames'])}帧")

        # ── 引擎3：视频 ───────────────────────────
        print("\n🎬 [3/6] 视频引擎启动...")
        video_paths = generate_all_videos(script, image_paths)
        valid_videos = len([p for p in video_paths if p])
        print(f"   ✅ 视频生成：{valid_videos}/{len(script['frames'])}帧")

        # ── 引擎4：配音 ───────────────────────────
        print("\n🔊 [4/6] 配音引擎启动...")
        audio_paths = generate_all_audio(script)
        valid_audio = len([p for p in audio_paths if p])
        print(f"   ✅ 配音生成：{valid_audio}帧有台词")

        # ── 引擎5：合成 ───────────────────────────
        print("\n🎞️  [5/6] 合成引擎启动...")
        output_path = merge_episode(script, video_paths, audio_paths)
        print(f"   ✅ 合成完成：{output_path}")

        # ── 引擎6：质检 ───────────────────────────
        print("\n🔍 [6/6] 质检引擎启动...")
        qc_report = run_qc(script, image_paths, ip_id)

        # ── 质检结果处理 ──────────────────────────
        elapsed = (datetime.now() - start_time).seconds

        if qc_report["passed"]:
            print(f"\n✅ 第{ep_num}集生产完成！用时 {elapsed}s")
            print(f"   输出文件：{output_path}")
            return {
                "status":       "SUCCESS",
                "ip_id":        ip_id,
                "episode_num":  ep_num,
                "output_path":  output_path,
                "qc_score":     qc_report["weighted_score"],
                "elapsed_sec":  elapsed
            }
        else:
            print(f"\n❌ 质检未通过（得分：{qc_report['weighted_score']:.3f}）")
            print(f"   失败维度：{', '.join(qc_report['failed_items'])}")

            if retry_count < MAX_RETRY:
                print(f"\n🔄 自动重试（{retry_count+1}/{MAX_RETRY}）...")
                # 根据失败维度生成针对性主题
                retry_theme = build_retry_theme(theme, qc_report["failed_items"])
                return run_pipeline(ip_id, ep_num, retry_theme, retry_count + 1)
            else:
                print(f"\n⚠️  已达最大重试次数，需人工介入。")
                return {
                    "status":      "NEEDS_REVIEW",
                    "ip_id":       ip_id,
                    "episode_num": ep_num,
                    "output_path": output_path,
                    "qc_score":    qc_report["weighted_score"],
                    "failed_items": qc_report["failed_items"],
                    "elapsed_sec": elapsed
                }

    except Exception as e:
        print(f"\n💥 流水线异常：{e}")
        return {
            "status":      "ERROR",
            "ip_id":       ip_id,
            "episode_num": ep_num,
            "error":       str(e)
        }

def build_retry_theme(original_theme: str, failed_items: list[str]) -> str:
    """根据失败维度生成针对性重试主题"""
    if "叙事连贯性" in failed_items:
        return f"{original_theme}（注意：情节要有完整起承转合，避免逻辑跳跃）"
    if "情绪吻合度" in failed_items:
        return f"{original_theme}（注意：台词情绪要强烈明确，匹配标签）"
    return original_theme

def run_daily_batch(ip_id: str, count: int = 2) -> list[dict]:
    """
    每日批量生产任务
    默认生产2集
    """
    print(f"\n🌅 每日批量生产启动：{ip_id} × {count}集")
    results = []
    for i in range(count):
        result = run_pipeline(ip_id)
        results.append(result)
        print(f"\n{'─'*30}")
        print(f"进度：{i+1}/{count} 集完成")

    # 打印汇总
    success = len([r for r in results if r["status"] == "SUCCESS"])
    print(f"\n📊 批量生产汇总：{success}/{count} 集成功")
    return results

def list_ips() -> list[str]:
    """列出所有已创建的IP"""
    cards_dir = "config/ip_cards"
    if not os.path.exists(cards_dir):
        return []
    return [
        f.replace(".json", "")
        for f in os.listdir(cards_dir)
        if f.endswith(".json")
    ]

# ── CLI入口 ───────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI漫剧生产流水线")
    parser.add_argument("--ip",    type=str, help="IP编号，如 ip_001")
    parser.add_argument("--ep",    type=int, help="指定集号（不填则自动递增）")
    parser.add_argument("--theme", type=str, help="本集主题（不填则自动生成）")
    parser.add_argument("--batch", type=int, default=1, help="批量生产集数，默认1")
    parser.add_argument("--list",  action="store_true", help="列出所有IP")
    args = parser.parse_args()

    if args.list:
        ips = list_ips()
        print(f"\n已创建的IP（{len(ips)}个）：")
        for ip in ips:
            card = load_ip_card(ip)
            print(f"  {ip} → {card['name']}")
        sys.exit(0)

    if not args.ip:
        print("❌ 请指定IP编号：--ip ip_001")
        sys.exit(1)

    if args.batch > 1:
        run_daily_batch(args.ip, args.batch)
    else:
        result = run_pipeline(args.ip, args.ep, args.theme)
        print(f"\n最终状态：{result['status']}")