# 主服务：整合所有引擎 + 提供完整API

import os
import sys
import json
import asyncio
import threading
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

# 路径配置：添加子模块搜索路径
sys.path.append("pipeline")
sys.path.append("character_creator")
sys.path.append("utils")

# 流水线引擎
from script_engine  import generate_script
from image_engine   import generate_all_frames
from video_engine   import generate_all_videos
from tts_engine     import generate_all_audio
from merge_engine   import merge_episode
from qc_engine      import run_qc
from main           import run_pipeline, get_next_episode_num

# 角色卡工坊
from state_machine  import StateMachine, State
from fuzzy_detector import detect_fuzzy
from prompt_builder import build_system_prompt, build_preview_prompt
from card_generator import draft_to_card, save_card, get_next_ip_id

# 工具模块
from utils.prompt_logger import log_prompt
from prompt_logger import query_logs, get_log_dates, get_log_detail, get_stats
from lora_manager import (
    train_lora_full_pipeline, get_lora_status,
    lora_exists, update_lora_status
)
from scheduler import (
    scheduler, load_schedule_config, save_schedule_config,
    get_schedule_logs, DailyScheduler
)
from ip_value_engine import (
    auto_screen, submit_human_review,
    submit_market_data, make_incubation_decision,
    get_ip_value_status, get_decision_log
)
from copyright_manager import (
    build_copyright_record, generate_copyright_pdf,
    export_copyright_package, get_copyright_records
)
from ip_comparator import get_all_ip_analytics, get_comparison_report
from distribution_manager import (
    generate_distribution_package,
    get_distribution_history
)
from story_evolution import (
    load_current_weights, save_current_weights,
    evolve_weights, get_insights, sample_style_combo,
    log_episode_performance, load_performance_data,
    create_ab_test, record_ab_result, conclude_ab_test,
    get_ab_tests, get_evolution_history,
    get_performance_summary, init_weights
)

load_dotenv()

app = FastAPI(title="AI漫剧IP孵化系统")

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# 静态文件
app.mount("/assets",   StaticFiles(directory="../assets"),   name="assets")
app.mount("/css",      StaticFiles(directory="../frontend/css"), name="css")
app.mount("/js",       StaticFiles(directory="../frontend/js"),  name="js")

# Agnes客户端
agnes_client = OpenAI(
    api_key=os.getenv("AGNES_API_KEY"),
    base_url=os.getenv("AGNES_BASE_URL")
)

# ── 全局状态 ─────────────────────────────────────
production_queue: list = []
production_logs: dict = {}   # ep_id → [log lines]
active_ws_clients: dict = {}   # client_id → WebSocket

# ── 页面路由 ─────────────────────────────────────
@app.get("/")
async def serve_spa():
    with open("../frontend/index.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())

# ── IP管理 API ───────────────────────────────────
@app.get("/api/ips")
async def list_ips():
    cards_dir = "config/ip_cards"
    os.makedirs(cards_dir, exist_ok=True)
    ips = []
    for fname in os.listdir(cards_dir):
        if fname.endswith(".json"):
            with open(os.path.join(cards_dir, fname), encoding="utf-8") as f:
                card = json.load(f)
            # 统计该IP已生产集数
            ep_count = count_episodes(card["ip_id"])
            ips.append({**card, "episode_count": ep_count})
    return {"ips": ips, "total": len(ips)}

@app.get("/api/ips/{ip_id}")
async def get_ip(ip_id: str):
    path = f"config/ip_cards/{ip_id}.json"
    if not os.path.exists(path):
        return {"error": "IP不存在"}
    with open(path, encoding="utf-8") as f:
        card = json.load(f)
    card["episode_count"] = count_episodes(ip_id)
    return card

@app.delete("/api/ips/{ip_id}")
async def delete_ip(ip_id: str):
    path = f"config/ip_cards/{ip_id}.json"
    if os.path.exists(path):
        os.remove(path)
    return {"status": "deleted", "ip_id": ip_id}

# ── 剧集管理 API ─────────────────────────────────
@app.get("/api/episodes")
async def list_episodes(ip_id: Optional[str] = None):
    ep_base = "../assets/episodes"
    os.makedirs(ep_base, exist_ok=True)
    episodes = []
    for ep_dir in sorted(os.listdir(ep_base), reverse=True):
        if ip_id and not ep_dir.startswith(ip_id):
            continue
        ep_path   = os.path.join(ep_base, ep_dir)
        if not os.path.isdir(ep_path):
            continue
        ep_info   = build_episode_info(ep_dir, ep_path)
        episodes.append(ep_info)
    return {"episodes": episodes, "total": len(episodes)}

@app.get("/api/episodes/{ep_id}")
async def get_episode(ep_id: str):
    ep_path = f"../assets/episodes/{ep_id}"
    if not os.path.exists(ep_path):
        return {"error": "剧集不存在"}
    ep_info = build_episode_info(ep_id, ep_path)
    # 附带分镜脚本
    script_path = os.path.join(ep_path, "script.json")
    if os.path.exists(script_path):
        with open(script_path, encoding="utf-8") as f:
            ep_info["script"] = json.load(f)
    return ep_info

@app.get("/api/episodes/{ep_id}/video")
async def get_episode_video(ep_id: str):
    video_path = f"../assets/episodes/{ep_id}/output.mp4"
    if not os.path.exists(video_path):
        return {"error": "视频不存在"}
    return FileResponse(video_path, media_type="video/mp4")

# ── 生产控制 API ─────────────────────────────────
class ProductionRequest(BaseModel):
    ip_id:  str
    count:  int = 1
    theme:  Optional[str] = None

@app.post("/api/production/start")
async def start_production(req: ProductionRequest, bg: BackgroundTasks):
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    bg.add_task(
        run_production_task,
        task_id, req.ip_id, req.count, req.theme
    )
    return {
        "status":  "started",
        "task_id": task_id,
        "ip_id":   req.ip_id,
        "count":   req.count
    }

@app.get("/api/production/status")
async def production_status():
    return {
        "queue":   production_queue,
        "running": len([t for t in production_queue if t.get("status") == "running"])
    }

# ── 质检报告 API ─────────────────────────────────
@app.get("/api/qc")
async def list_qc_reports(ip_id: Optional[str] = None):
    qc_dir = "../qc_reports"
    os.makedirs(qc_dir, exist_ok=True)
    reports = []
    for fname in sorted(os.listdir(qc_dir), reverse=True):
        if not fname.endswith("_qc.json"):
            continue
        if ip_id and not fname.startswith(ip_id):
            continue
        with open(os.path.join(qc_dir, fname), encoding="utf-8") as f:
            reports.append(json.load(f))
    return {"reports": reports, "total": len(reports)}

# ── 统计数据 API ─────────────────────────────────
@app.get("/api/stats")
async def get_stats():
    ips      = await list_ips()
    episodes = await list_episodes()
    qc_data  = await list_qc_reports()

    reports  = qc_data["reports"]
    avg_score = (
        sum(r["weighted_score"] for r in reports) / len(reports)
        if reports else 0
    )
    pass_rate = (
        len([r for r in reports if r["passed"]]) / len(reports) * 100
        if reports else 0
    )

    # 估算成本（每集约$0.77）
    total_cost = episodes["total"] * 0.77

    return {
        "ip_count":      ips["total"],
        "episode_count": episodes["total"],
        "avg_qc_score":  round(avg_score, 3),
        "pass_rate":     round(pass_rate, 1),
        "total_cost_usd": round(total_cost, 2),
        "today_episodes": count_today_episodes()
    }

# ── 图像预览 API（角色卡工坊用）────────────────────
class PreviewRequest(BaseModel):
    draft: dict

@app.post("/api/generate-preview")
async def generate_preview(req: PreviewRequest):
    """生成角色预览图"""
    import requests as req_lib
    draft   = req.draft
    prompt  = (
        f"{draft.get('appearance', '')}, "
        f"{draft.get('art_style', 'anime style')}, "
        f"character design, white background, "
        f"front view, high quality"
    )
    images = []
    for i in range(3):
        try:
            resp = req_lib.post(
                f"{os.getenv('AGNES_BASE_URL')}/images/generate",
                json={
                    "model":  os.getenv("AGNES_IMAGE_MODEL"),
                    "prompt": prompt,
                    "seed":   42 + i * 100,
                    "width":  512,
                    "height": 512
                },
                headers={"Authorization": f"Bearer {os.getenv('AGNES_API_KEY')}"},
                timeout=60
            )
            result = resp.json()
            images.append(result["data"][0]["url"])
        except Exception as e:
            images.append(None)
    return {"images": images}

@app.get("/api/ip-count")
async def ip_count():
    cards_dir = "config/ip_cards"
    os.makedirs(cards_dir, exist_ok=True)
    count = len([f for f in os.listdir(cards_dir) if f.endswith(".json")])
    return {"count": count}

# ── WebSocket：角色卡工坊 ─────────────────────────
creator_sessions: dict = {}

@app.websocket("/ws/creator")
async def creator_ws(websocket: WebSocket):
    await websocket.accept()
    sm = StateMachine()
    creator_sessions["local"] = sm

    await websocket.send_json({
        "type":     "ai_message",
        "content":  sm.get_opening_message(),
        "state":    sm.state.name,
        "progress": sm.draft.completion_rate()
    })

    try:
        while True:
            data       = await websocket.receive_json()
            user_input = data.get("message", "")

            if data.get("action") == "confirm_card":
                ip_id    = get_next_ip_id()
                card     = draft_to_card(sm.draft, ip_id)
                filepath = save_card(card)
                sm.state = State.VOICE_CONFIRM
                await websocket.send_json({
                    "type":     "card_saved",
                    "ip_id":    ip_id,
                    "filepath": filepath,
                    "message":  f"✅ 角色卡已保存！IP编号：{ip_id}",
                    "state":    sm.state.name
                })
                continue

            if data.get("action") == "regenerate":
                sm.state = sm.next_missing_state()
                await websocket.send_json({
                    "type":     "ai_message",
                    "content":  "好，保留已有信息，告诉我想修改哪里？",
                    "state":    sm.state.name,
                    "progress": sm.draft.completion_rate()
                })
                continue

            fuzzy = detect_fuzzy(user_input)
            if fuzzy and sm.state not in [State.FUZZY_CLARIFY, State.PREVIEW]:
                sm.pending_fuzzy = fuzzy
                sm.state = State.FUZZY_CLARIFY
                await websocket.send_json({
                    "type":     "ai_message",
                    "content":  fuzzy["question"],
                    "state":    sm.state.name,
                    "progress": sm.draft.completion_rate()
                })
                continue

            sm.history.append({"role": "user", "content": user_input})
            system_prompt = build_system_prompt(
                sm.draft.__dict__,
                sm.next_missing_state().name
            )

            log_prompt(
                engine = "creator",
                stage  = f"state_{sm.state.name}",
                prompt = {
                    "system": system_prompt,
                    "user":   user_input,
                    "history_len": len(sm.history)
                },
                model  = os.getenv("AGNES_TEXT_MODEL"),
                extra  = {
                    "current_state":  sm.state.name,
                    "draft_snapshot": sm.draft.__dict__
                }
            )

            response = agnes_client.chat.completions.create(
                model=os.getenv("AGNES_TEXT_MODEL"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    *sm.history
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            result    = json.loads(response.choices[0].message.content)
            extracted = result.get("extracted", {})
            ai_reply  = result.get("reply", "")
            new_state = sm.advance(user_input, extracted)
            sm.history.append({"role": "assistant", "content": ai_reply})

            if new_state == State.PREVIEW:
                preview_resp = agnes_client.chat.completions.create(
                    model=os.getenv("AGNES_TEXT_MODEL"),
                    messages=[{"role": "user",
                               "content": build_preview_prompt(sm.draft.__dict__)}],
                    temperature=0.8
                )
                preview_text = preview_resp.choices[0].message.content
                await websocket.send_json({
                    "type":     "preview_ready",
                    "content":  preview_text,
                    "draft":    sm.draft.__dict__,
                    "state":    new_state.name,
                    "progress": sm.draft.completion_rate(),
                    "actions":  ["confirm", "modify", "regenerate"]
                })
            else:
                await websocket.send_json({
                    "type":     "ai_message",
                    "content":  ai_reply,
                    "state":    new_state.name,
                    "progress": sm.draft.completion_rate()
                })
    except WebSocketDisconnect:
        creator_sessions.pop("local", None)

# ── WebSocket：生产实时日志 ───────────────────────
@app.websocket("/ws/production/{client_id}")
async def production_ws(websocket: WebSocket, client_id: str):
    await websocket.accept()
    active_ws_clients[client_id] = websocket
    try:
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        active_ws_clients.pop(client_id, None)

async def broadcast_log(message: str, level: str = "info", ep_id: str = None):
    """向所有已连接客户端广播日志"""
    payload = {
        "type":    "log",
        "level":   level,
        "message": message,
        "ep_id":   ep_id,
        "time":    datetime.now().strftime("%H:%M:%S")
    }
    dead_clients = []
    for cid, ws in active_ws_clients.items():
        try:
            await ws.send_json(payload)
        except Exception:
            dead_clients.append(cid)
    for cid in dead_clients:
        active_ws_clients.pop(cid, None)

# ── 生产任务（后台线程）─────────────────────────
def run_production_task(task_id: str, ip_id: str, count: int, theme: str):
    """在后台线程中运行生产流水线"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run():
        production_queue.append({
            "task_id": task_id,
            "ip_id":   ip_id,
            "count":   count,
            "status":  "running",
            "started": datetime.now().isoformat()
        })

        for i in range(count):
            ep_num = get_next_episode_num(ip_id)
            ep_id  = f"{ip_id}_ep{str(ep_num).zfill(3)}"

            await broadcast_log(f"🎬 开始生产 {ip_id} 第{ep_num}集", "info", ep_id)
            await broadcast_log("📝 剧本引擎启动...", "info", ep_id)

            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: run_pipeline(ip_id, ep_num, theme)
                )
                status = result.get("status")
                if status == "SUCCESS":
                    await broadcast_log(
                        f"✅ 第{ep_num}集完成！得分：{result['qc_score']:.3f}",
                        "success", ep_id
                    )
                else:
                    await broadcast_log(
                        f"⚠️  第{ep_num}集需人工复审",
                        "warning", ep_id
                    )
            except Exception as e:
                await broadcast_log(f"❌ 生产异常：{e}", "error", ep_id)

        # 更新队列状态
        for task in production_queue:
            if task["task_id"] == task_id:
                task["status"]   = "completed"
                task["finished"] = datetime.now().isoformat()

        await broadcast_log(f"🏁 任务完成：{count}集生产结束", "success")

    loop.run_until_complete(_run())
    loop.close()

# ── 工具函数 ─────────────────────────────────────
def count_episodes(ip_id: str) -> int:
    ep_base = "../assets/episodes"
    if not os.path.exists(ep_base):
        return 0
    return len([
        d for d in os.listdir(ep_base)
        if d.startswith(ip_id) and os.path.isdir(os.path.join(ep_base, d))
    ])

def count_today_episodes() -> int:
    today   = datetime.now().strftime("%Y%m%d")
    qc_dir  = "../qc_reports"
    if not os.path.exists(qc_dir):
        return 0
    return len([
        f for f in os.listdir(qc_dir)
        if today in f and f.endswith("_qc.json")
    ])

def build_episode_info(ep_id: str, ep_path: str) -> dict:
    has_video = os.path.exists(os.path.join(ep_path, "output.mp4"))
    qc_path   = f"../qc_reports/{ep_id}_qc.json"
    qc_score  = None
    qc_passed = None
    if os.path.exists(qc_path):
        with open(qc_path, encoding="utf-8") as f:
            qc_data   = json.load(f)
            qc_score  = qc_data.get("weighted_score")
            qc_passed = qc_data.get("passed")

    parts     = ep_id.split("_ep")
    ip_id     = parts[0] if len(parts) > 1 else ep_id
    ep_num    = int(parts[1]) if len(parts) > 1 else 0

    # 获取IP名称
    ip_name = ip_id
    card_path = f"config/ip_cards/{ip_id}.json"
    if os.path.exists(card_path):
        with open(card_path, encoding="utf-8") as f:
            ip_name = json.load(f).get("name", ip_id)

    # 文件时间
    mtime = os.path.getmtime(ep_path)
    created_at = datetime.fromtimestamp(mtime).isoformat()

    return {
        "ep_id":      ep_id,
        "ip_id":      ip_id,
        "ip_name":    ip_name,
        "episode_num": ep_num,
        "has_video":  has_video,
        "qc_score":   qc_score,
        "qc_passed":  qc_passed,
        "video_url":  f"/assets/episodes/{ep_id}/output.mp4" if has_video else None,
        "created_at": created_at
    }

# 启动时启动调度器
@app.on_event("startup")
async def startup_event():
    scheduler.start()
    print("[系统] 调度器已随服务启动")

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.stop()

# ── LoRA训练 API ─────────────────────────────

class LoraTrainRequest(BaseModel):
    ip_id: str

@app.post("/api/lora/train")
async def start_lora_training(req: LoraTrainRequest, bg: BackgroundTasks):
    ip_id = req.ip_id

    if lora_exists(ip_id):
        return {"status": "already_exists",
                "message": f"{ip_id} 的LoRA权重已存在",
                "weight_path": f"../models/lora/{ip_id}.safetensors"}

    update_lora_status(ip_id, "queued", 0)
    bg.add_task(train_lora_bg, ip_id)

    return {"status": "started", "ip_id": ip_id,
            "message": "训练任务已提交，预计2~4小时完成"}

async def train_lora_bg(ip_id: str):
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, train_lora_full_pipeline, ip_id)
        await broadcast_log(f"✅ {ip_id} LoRA训练完成", "success")
    except Exception as e:
        update_lora_status(ip_id, "failed", 0, error=str(e))
        await broadcast_log(f"❌ {ip_id} LoRA训练失败：{e}", "error")

@app.get("/api/lora/status")
async def get_all_lora_status():
    all_status = get_lora_status()
    # 补充已存在但无状态记录的IP
    for fname in os.listdir("../models/lora") if os.path.exists("../models/lora") else []:
        if fname.endswith(".safetensors"):
            ip_id = fname.replace(".safetensors", "")
            if ip_id not in all_status:
                all_status[ip_id] = {
                    "ip_id": ip_id, "status": "completed",
                    "progress": 100,
                    "weight_path": f"../models/lora/{fname}"
                }
    return all_status

@app.get("/api/lora/status/{ip_id}")
async def get_ip_lora_status(ip_id: str):
    return get_lora_status(ip_id)

@app.delete("/api/lora/{ip_id}")
async def delete_lora(ip_id: str):
    path = f"../models/lora/{ip_id}.safetensors"
    if os.path.exists(path):
        os.remove(path)
    update_lora_status(ip_id, "deleted", 0)
    return {"status": "deleted", "ip_id": ip_id}

# ── 调度器 API ───────────────────────────────

@app.get("/api/schedule/config")
async def get_schedule_config():
    return load_schedule_config()

@app.post("/api/schedule/config")
async def update_schedule_config(config: dict):
    save_schedule_config(config)
    scheduler.reload()
    return {"status": "saved", "message": "调度配置已保存并重新加载"}

@app.post("/api/schedule/trigger/{ip_id}")
async def trigger_schedule_now(ip_id: str):
    try:
        scheduler.trigger_now(ip_id)
        return {"status": "triggered", "ip_id": ip_id}
    except ValueError as e:
        return {"error": str(e)}

@app.get("/api/schedule/next-runs")
async def get_next_runs():
    return {"jobs": scheduler.get_next_runs(), "running": scheduler.running}

@app.get("/api/schedule/logs")
async def get_sched_logs(limit: int = 50):
    return {"logs": get_schedule_logs(limit)}

@app.post("/api/schedule/toggle")
async def toggle_scheduler(body: dict):
    enabled = body.get("enabled", False)
    config  = load_schedule_config()
    config["enabled"] = enabled
    save_schedule_config(config)
    if enabled:
        scheduler.reload()
    else:
        scheduler.stop()
        scheduler.start()   # 重启但不注册任务（因为enabled=False）
    return {"status": "ok", "enabled": enabled}

# ── 审计日志 API ─────────────────────────────

@app.get("/api/audit/logs")
async def get_audit_logs(
    date:        Optional[str] = None,
    engine:      Optional[str] = None,
    ip_id:       Optional[str] = None,
    episode_num: Optional[int] = None,
    limit:       int = 50,
    offset:      int = 0
):
    return query_logs(
        date=date, engine=engine, ip_id=ip_id,
        episode_num=episode_num, limit=limit, offset=offset
    )

@app.get("/api/audit/dates")
async def get_audit_dates():
    return {"dates": get_log_dates()}

@app.get("/api/audit/logs/{log_id}")
async def get_audit_detail(log_id: str, date: Optional[str] = None):
    entry = get_log_detail(log_id, date)
    if not entry:
        return {"error": "日志不存在"}
    return entry

@app.get("/api/audit/stats")
async def get_audit_stats(date: Optional[str] = None):
    return get_stats(date)

# ── IP价值评估 API ────────────────────────────

@app.post("/api/ipvalue/auto-screen/{ip_id}")
async def run_auto_screen(ip_id: str, bg: BackgroundTasks):
    """触发自动初筛（LLM评估，后台运行）"""
    bg.add_task(_run_auto_screen_bg, ip_id)
    return {"status": "started", "ip_id": ip_id}

async def _run_auto_screen_bg(ip_id: str):
    try:
        report = await asyncio.get_event_loop().run_in_executor(
            None, auto_screen, ip_id
        )
        await broadcast_log(
            f"✅ {ip_id} 自动初筛完成：{report['weighted_score']:.2f}分",
            "success"
        )
    except Exception as e:
        await broadcast_log(f"❌ {ip_id} 初筛失败：{e}", "error")

class HumanReviewRequest(BaseModel):
    reviewer_scores: dict
    comments:        str
    decision:        str   # pass / reject / observe

@app.post("/api/ipvalue/human-review/{ip_id}")
async def submit_human_review_api(ip_id: str, req: HumanReviewRequest):
    report = submit_human_review(
        ip_id, req.reviewer_scores, req.comments, req.decision
    )
    return report

class MarketDataRequest(BaseModel):
    platform:         str
    sample_episodes:  int
    raw_metrics:      dict

@app.post("/api/ipvalue/market-data/{ip_id}")
async def submit_market_data_api(ip_id: str, req: MarketDataRequest):
    report = submit_market_data(
        ip_id, req.platform, req.sample_episodes, req.raw_metrics
    )
    return report

@app.post("/api/ipvalue/decide/{ip_id}")
async def make_decision_api(ip_id: str):
    report = make_incubation_decision(ip_id)
    return report

@app.get("/api/ipvalue/status")
async def get_all_ipvalue_status():
    return get_ip_value_status()

@app.get("/api/ipvalue/status/{ip_id}")
async def get_ipvalue_status(ip_id: str):
    return get_ip_value_status(ip_id)

@app.get("/api/ipvalue/decisions")
async def get_decisions(ip_id: Optional[str] = None, limit: int = 50):
    return {"decisions": get_decision_log(ip_id, limit)}

# ── 版权备案 API ─────────────────────────────

@app.get("/api/copyright/records")
async def list_copyright_records(ip_id: Optional[str] = None):
    return {"records": get_copyright_records(ip_id)}

@app.post("/api/copyright/generate/{ip_id}")
async def generate_copyright(ip_id: str, bg: BackgroundTasks):
    bg.add_task(_generate_copyright_bg, ip_id)
    return {"status": "started", "ip_id": ip_id}

async def _generate_copyright_bg(ip_id: str):
    try:
        path = await asyncio.get_event_loop().run_in_executor(
            None, export_copyright_package, ip_id
        )
        await broadcast_log(f"✅ {ip_id} 版权存证包已生成", "success")
    except Exception as e:
        await broadcast_log(f"❌ 版权存证生成失败：{e}", "error")

@app.get("/api/copyright/download/{filename}")
async def download_copyright(filename: str):
    path = os.path.join("../exports/copyright", filename)
    if not os.path.exists(path):
        return {"error": "文件不存在"}
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=filename
    )

@app.get("/api/copyright/preview/{ip_id}")
async def preview_copyright_record(ip_id: str):
    """预览存证数据（不生成PDF）"""
    record = build_copyright_record(ip_id)
    return record

# ── 多IP对比 API ─────────────────────────────

@app.get("/api/compare/all")
async def compare_all_ips():
    analytics = get_all_ip_analytics()
    return {"analytics": analytics, "total": len(analytics)}

@app.post("/api/compare/selected")
async def compare_selected_ips(body: dict):
    ip_ids = body.get("ip_ids", [])
    if not ip_ids:
        return {"error": "请提供IP列表"}
    report = get_comparison_report(ip_ids)
    return report

# ── 内容分发 API ─────────────────────────────

class DistributionRequest(BaseModel):
    platforms: Optional[list] = None

@app.post("/api/distribution/generate/{ep_id}")
async def generate_distribution(
    ep_id: str,
    req: DistributionRequest,
    bg: BackgroundTasks
):
    bg.add_task(_generate_dist_bg, ep_id, req.platforms)
    return {"status": "started", "ep_id": ep_id}

async def _generate_dist_bg(ep_id: str, platforms: list):
    try:
        pkg = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: generate_distribution_package(ep_id, platforms)
        )
        await broadcast_log(
            f"✅ {ep_id} 分发素材已生成（{len(pkg['platforms'])}个平台）",
            "success"
        )
    except Exception as e:
        await broadcast_log(f"❌ 分发素材生成失败：{e}", "error")

@app.get("/api/distribution/history")
async def dist_history(ip_id: Optional[str] = None):
    return {"history": get_distribution_history(ip_id)}

@app.get("/api/distribution/{ep_id}")
async def get_dist_package(ep_id: str):
    path = f"../exports/distribution/{ep_id}_dist.json"
    if not os.path.exists(path):
        return {"error": "分发素材不存在"}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

# ── 剧情进化 API ─────────────────────────────

@app.get("/api/evolution/weights/{ip_id}")
async def get_weights(ip_id: str):
    return {
        "ip_id":   ip_id,
        "weights": load_current_weights(ip_id)
    }

@app.post("/api/evolution/evolve/{ip_id}")
async def trigger_evolve(ip_id: str):
    result = await asyncio.get_event_loop().run_in_executor(
        None, evolve_weights, ip_id
    )
    if result.get("status") == "evolved":
        await broadcast_log(
            f"🧬 {ip_id} 权重进化完成，最大变化：{result['max_change']}",
            "success"
        )
    return result

@app.post("/api/evolution/reset/{ip_id}")
async def reset_weights(ip_id: str):
    weights = init_weights(ip_id)
    save_current_weights(ip_id, weights, reason="manual_reset")
    return {"status": "reset", "weights": weights}

@app.post("/api/evolution/weights/{ip_id}")
async def update_weights_manual(ip_id: str, body: dict):
    weights = body.get("weights", {})
    save_current_weights(ip_id, weights, reason="manual_edit")
    return {"status": "saved", "weights": weights}

@app.get("/api/evolution/insights/{ip_id}")
async def get_evolution_insights(ip_id: str):
    insights = await asyncio.get_event_loop().run_in_executor(
        None, get_insights, ip_id
    )
    return insights

@app.get("/api/evolution/sample/{ip_id}")
async def sample_next_combo(ip_id: str, explore: bool = False):
    combo = sample_style_combo(ip_id, force_explore=explore)
    return {"ip_id": ip_id, "combo": combo}

@app.post("/api/evolution/performance")
async def log_performance(body: dict):
    score = log_episode_performance(
        body["ip_id"], body["ep_id"],
        body["style_combo"], body["metrics"]
    )
    return {"status": "logged", "composite_score": score}

@app.get("/api/evolution/performance/{ip_id}")
async def get_performance(ip_id: str, limit: int = 50):
    data    = load_performance_data(ip_id, limit)
    summary = get_performance_summary(ip_id)
    return {"data": data, "summary": summary}

@app.get("/api/evolution/history/{ip_id}")
async def get_weight_history(ip_id: str, limit: int = 20):
    return {"history": get_evolution_history(ip_id, limit)}

# ── A/B 测试 API ─────────────────────────────

class ABTestRequest(BaseModel):
    test_name:            str
    variant_a:            dict
    variant_b:            dict
    episodes_per_variant: int = 5

@app.post("/api/evolution/abtest/{ip_id}")
async def create_ab(ip_id: str, req: ABTestRequest):
    test = create_ab_test(
        ip_id, req.test_name,
        req.variant_a, req.variant_b,
        req.episodes_per_variant
    )
    return test

@app.post("/api/evolution/abtest/{test_id}/record")
async def record_ab(test_id: str, body: dict):
    record_ab_result(
        test_id,
        body["variant"],
        body["ep_id"],
        body["score"]
    )
    return {"status": "recorded"}

@app.post("/api/evolution/abtest/{test_id}/conclude")
async def conclude_ab(test_id: str):
    result = conclude_ab_test(test_id)
    await broadcast_log(
        f"🏆 A/B测试 {test_id} 结束，胜出：Variant {result.get('winner','?').upper()}",
        "success"
    )
    return result

@app.get("/api/evolution/abtests")
async def list_abtests(ip_id: Optional[str] = None):
    return {"tests": get_ab_tests(ip_id)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_app:app", host="0.0.0.0", port=8000, reload=True)