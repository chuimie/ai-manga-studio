# 每日自动调度器：定时触发生产任务

import os
import json
import asyncio
import threading
import schedule
import time
from datetime import datetime, date
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

import sys
sys.path.append("pipeline")
from main import run_pipeline, get_next_episode_num

SCHEDULE_CONFIG_FILE = "config/schedule_config.json"
SCHEDULE_LOG_FILE    = "logs/schedule.jsonl"

# ─────────────────────────────────────────────
# 调度配置结构
# ─────────────────────────────────────────────

DEFAULT_SCHEDULE_CONFIG = {
    "enabled": False,
    "daily_tasks": [
        # 每个IP可独立配置
        # {
        #   "ip_id": "ip_001",
        #   "count": 2,
        #   "time": "09:00",
        #   "enabled": True,
        #   "theme_pool": []   # 主题池（空则自动生成）
        # }
    ],
    "created_at": None,
    "updated_at": None
}

def load_schedule_config() -> dict:
    if not os.path.exists(SCHEDULE_CONFIG_FILE):
        return DEFAULT_SCHEDULE_CONFIG.copy()
    with open(SCHEDULE_CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)

def save_schedule_config(config: dict):
    os.makedirs(os.path.dirname(SCHEDULE_CONFIG_FILE), exist_ok=True)
    config["updated_at"] = datetime.now().isoformat()
    with open(SCHEDULE_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# ─────────────────────────────────────────────
# 调度日志
# ─────────────────────────────────────────────

def log_schedule_event(
    event_type: str,
    ip_id: str = None,
    detail: dict = None
):
    os.makedirs(os.path.dirname(SCHEDULE_LOG_FILE), exist_ok=True)
    entry = {
        "timestamp":  datetime.now().isoformat(),
        "event_type": event_type,
        "ip_id":      ip_id,
        "detail":     detail or {}
    }
    with open(SCHEDULE_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def get_schedule_logs(limit: int = 50) -> list:
    if not os.path.exists(SCHEDULE_LOG_FILE):
        return []
    logs = []
    with open(SCHEDULE_LOG_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                logs.append(json.loads(line.strip()))
            except Exception:
                continue
    return list(reversed(logs))[:limit]

# ─────────────────────────────────────────────
# 每日生产任务执行逻辑
# ─────────────────────────────────────────────

def pick_theme(theme_pool: list, ip_id: str) -> Optional[str]:
    """
    从主题池中按轮询顺序取主题
    无主题池则返回None（引擎自动生成）
    """
    if not theme_pool:
        return None

    # 记录已使用的主题索引
    used_file = f"config/theme_cursor_{ip_id}.json"
    cursor    = 0
    if os.path.exists(used_file):
        with open(used_file) as f:
            cursor = json.load(f).get("cursor", 0)

    theme     = theme_pool[cursor % len(theme_pool)]
    next_cursor = (cursor + 1) % len(theme_pool)

    with open(used_file, "w") as f:
        json.dump({"cursor": next_cursor}, f)

    return theme

def run_daily_task(task: dict):
    """执行单个IP的每日生产任务"""
    ip_id      = task["ip_id"]
    count      = task.get("count", 2)
    theme_pool = task.get("theme_pool", [])

    log_schedule_event("task_start", ip_id, {
        "count": count, "time": datetime.now().strftime("%H:%M")
    })

    print(f"\n[调度器] {datetime.now().strftime('%H:%M:%S')} "
          f"开始执行：{ip_id} × {count}集")

    results = []
    for i in range(count):
        theme = pick_theme(theme_pool, ip_id)
        try:
            result = run_pipeline(ip_id, theme=theme)
            results.append(result)
            status = result.get("status", "UNKNOWN")
            log_schedule_event("episode_done", ip_id, {
                "episode_num": result.get("episode_num"),
                "status":      status,
                "qc_score":    result.get("qc_score")
            })
            print(f"[调度器] 第{i+1}/{count}集完成：{status}")
        except Exception as e:
            log_schedule_event("episode_error", ip_id, {"error": str(e)})
            print(f"[调度器] 第{i+1}/{count}集异常：{e}")

    success = len([r for r in results if r.get("status") == "SUCCESS"])
    log_schedule_event("task_done", ip_id, {
        "total": count, "success": success
    })
    print(f"[调度器] {ip_id} 今日任务完成：{success}/{count}集成功")

# ─────────────────────────────────────────────
# 调度器主控
# ─────────────────────────────────────────────

class DailyScheduler:
    def __init__(self):
        self.running    = False
        self.thread     = None
        self._stop_flag = False

    def setup_jobs(self):
        """根据配置文件注册所有定时任务"""
        schedule.clear()
        config = load_schedule_config()

        if not config.get("enabled"):
            print("[调度器] 全局调度已禁用")
            return

        for task in config.get("daily_tasks", []):
            if not task.get("enabled", True):
                continue

            ip_id    = task["ip_id"]
            run_time = task.get("time", "09:00")

            # 注册定时任务
            schedule.every().day.at(run_time).do(
                self._safe_run_task, task=task
            )
            print(f"[调度器] 已注册：{ip_id} 每天 {run_time} 生产 {task.get('count',2)}集")

        log_schedule_event("scheduler_started", detail={
            "task_count": len([t for t in config.get("daily_tasks",[])
                               if t.get("enabled", True)])
        })

    def _safe_run_task(self, task: dict):
        """在独立线程中安全执行任务，防止阻塞调度器"""
        t = threading.Thread(
            target=run_daily_task,
            args=(task,),
            daemon=True
        )
        t.start()

    def start(self):
        """启动调度器守护线程"""
        if self.running:
            return

        self.running    = True
        self._stop_flag = False
        self.setup_jobs()

        def _loop():
            while not self._stop_flag:
                schedule.run_pending()
                time.sleep(10)  # 每10秒检查一次

        self.thread = threading.Thread(target=_loop, daemon=True)
        self.thread.start()
        print("[调度器] 守护线程已启动")

    def stop(self):
        self._stop_flag = True
        self.running    = False
        schedule.clear()
        log_schedule_event("scheduler_stopped")
        print("[调度器] 已停止")

    def reload(self):
        """重新加载配置（前端修改后调用）"""
        schedule.clear()
        self.setup_jobs()
        print("[调度器] 配置已重新加载")

    def get_next_runs(self) -> list:
        """返回接下来的计划任务"""
        jobs = []
        for job in schedule.jobs:
            jobs.append({
                "next_run": job.next_run.isoformat() if job.next_run else None,
                "interval": str(job.interval),
                "unit":     job.unit,
                "at_time":  str(job.at_time) if hasattr(job,"at_time") else None
            })
        return jobs

    def trigger_now(self, ip_id: str):
        """立即触发指定IP的任务（不等定时）"""
        config = load_schedule_config()
        task   = next(
            (t for t in config.get("daily_tasks",[])
             if t["ip_id"] == ip_id),
            None
        )
        if not task:
            raise ValueError(f"未找到 {ip_id} 的调度配置")
        self._safe_run_task(task)
        log_schedule_event("manual_trigger", ip_id)
        print(f"[调度器] 手动触发：{ip_id}")


# 全局调度器实例
scheduler = DailyScheduler()