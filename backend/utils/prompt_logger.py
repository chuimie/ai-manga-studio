# Prompt审计日志：记录每个引擎的每次调用
# 日志格式：结构化JSON，支持按引擎/IP/集数/时间过滤

import os
import json
import hashlib
from datetime import datetime
from typing import Optional

LOGS_DIR = "logs/prompts"

def log_prompt(
    engine:     str,            # script / image / video / tts / qc / creator
    stage:      str,            # 更细的阶段描述，如 "frame_001" / "preview"
    prompt:     str | dict,     # 实际发送的Prompt（字符串或dict）
    response:   str | dict | None = None,  # 模型返回（可选）
    ip_id:      Optional[str]  = None,
    episode_num:Optional[int]  = None,
    frame_id:   Optional[int]  = None,
    model:      Optional[str]  = None,
    extra:      Optional[dict] = None      # 任意附加信息
) -> str:
    """
    记录一次Prompt调用
    返回本条日志的log_id（用于关联追溯）
    """
    os.makedirs(LOGS_DIR, exist_ok=True)

    # 生成唯一log_id
    ts      = datetime.now()
    raw_id  = f"{engine}_{stage}_{ts.isoformat()}"
    log_id  = hashlib.md5(raw_id.encode()).hexdigest()[:12]

    entry = {
        "log_id":      log_id,
        "timestamp":   ts.isoformat(),
        "engine":      engine,
        "stage":       stage,
        "ip_id":       ip_id,
        "episode_num": episode_num,
        "frame_id":    frame_id,
        "model":       model,
        "prompt":      prompt,
        "response_preview": _truncate(response, 500),  # 完整response太大，只存预览
        "prompt_hash": hashlib.md5(
            str(prompt).encode()
        ).hexdigest(),
        "prompt_length": len(str(prompt)),
        "extra": extra or {}
    }

    # 按日期分文件：logs/prompts/2025-01-01.jsonl
    log_file = os.path.join(LOGS_DIR, f"{ts.strftime('%Y-%m-%d')}.jsonl")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"[审计] {engine}/{stage} → log_id={log_id}")
    return log_id


def query_logs(
    date:        Optional[str] = None,   # "2025-01-01"，不填则今天
    engine:      Optional[str] = None,
    ip_id:       Optional[str] = None,
    episode_num: Optional[int] = None,
    limit:       int = 100,
    offset:      int = 0
) -> dict:
    """
    查询Prompt日志
    返回 {total, logs, page_info}
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    log_file    = os.path.join(LOGS_DIR, f"{target_date}.jsonl")

    if not os.path.exists(log_file):
        return {"total": 0, "logs": [], "date": target_date}

    all_logs = []
    with open(log_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                # 过滤条件
                if engine and entry.get("engine") != engine:
                    continue
                if ip_id and entry.get("ip_id") != ip_id:
                    continue
                if episode_num is not None and entry.get("episode_num") != episode_num:
                    continue
                all_logs.append(entry)
            except Exception:
                continue

    total    = len(all_logs)
    paginated = list(reversed(all_logs))[offset: offset + limit]

    return {
        "total":  total,
        "logs":   paginated,
        "date":   target_date,
        "offset": offset,
        "limit":  limit
    }


def get_log_dates() -> list[str]:
    """返回所有有日志的日期列表"""
    os.makedirs(LOGS_DIR, exist_ok=True)
    dates = []
    for fname in sorted(os.listdir(LOGS_DIR), reverse=True):
        if fname.endswith(".jsonl"):
            dates.append(fname.replace(".jsonl", ""))
    return dates


def get_log_detail(log_id: str, date: Optional[str] = None) -> Optional[dict]:
    """根据log_id获取完整日志条目"""
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    log_file    = os.path.join(LOGS_DIR, f"{target_date}.jsonl")

    if not os.path.exists(log_file):
        return None

    with open(log_file, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if entry.get("log_id") == log_id:
                    return entry
            except Exception:
                continue
    return None


def get_stats(date: Optional[str] = None) -> dict:
    """返回当日Prompt调用统计"""
    result = query_logs(date=date, limit=99999)
    logs   = result["logs"]

    engine_counts = {}
    total_chars   = 0

    for entry in logs:
        eng = entry.get("engine", "unknown")
        engine_counts[eng] = engine_counts.get(eng, 0) + 1
        total_chars += entry.get("prompt_length", 0)

    return {
        "date":          result["date"],
        "total_calls":   result["total"],
        "by_engine":     engine_counts,
        "total_prompt_chars": total_chars
    }


def _truncate(obj, max_len: int) -> str | None:
    """截断过长的响应内容"""
    if obj is None:
        return None
    s = str(obj) if not isinstance(obj, str) else obj
    if len(s) <= max_len:
        return s
    return s[:max_len] + f"…（共{len(s)}字）"