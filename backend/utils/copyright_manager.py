# 版权备案模块
# 自动生成创作存证文件，支持作品登记所需材料导出

import os
import json
import hashlib
import zipfile
from datetime import datetime
from typing import Optional
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, Image, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from dotenv import load_dotenv

load_dotenv()

COPYRIGHT_DIR = "../exports/copyright"
FONT_PATH     = "../assets/fonts/NotoSansSC-Regular.ttf"  # 中文字体

# ─────────────────────────────────────────────
# 存证数据结构
# ─────────────────────────────────────────────

def build_copyright_record(ip_id: str) -> dict:
    """
    构建完整版权存证记录
    聚合：角色卡 + LoRA训练记录 + 生产记录 + Prompt日志摘要
    """
    # 加载IP角色卡
    with open(f"config/ip_cards/{ip_id}.json", encoding="utf-8") as f:
        ip_card = json.load(f)

    # 统计生产数据
    ep_base    = f"../assets/episodes"
    episodes   = []
    if os.path.exists(ep_base):
        for d in sorted(os.listdir(ep_base)):
            if d.startswith(ip_id):
                ep_path     = os.path.join(ep_base, d)
                script_path = os.path.join(ep_path, "script.json")
                if os.path.exists(script_path):
                    with open(script_path, encoding="utf-8") as f:
                        script = json.load(f)
                    episodes.append({
                        "ep_id":    d,
                        "title":    script.get("episode_title", d),
                        "theme":    script.get("theme", ""),
                        "frames":   len(script.get("frames", [])),
                        "duration": script.get("actual_duration", 0)
                    })

    # 加载质检报告摘要
    qc_dir  = "../qc_reports"
    qc_list = []
    if os.path.exists(qc_dir):
        for fname in sorted(os.listdir(qc_dir)):
            if fname.startswith(ip_id) and fname.endswith("_qc.json"):
                with open(os.path.join(qc_dir, fname), encoding="utf-8") as f:
                    qc = json.load(f)
                qc_list.append({
                    "ep_id": qc.get("ip_id","") + "_ep" +
                             str(qc.get("episode_num","")).zfill(3),
                    "score": qc.get("weighted_score", 0),
                    "passed": qc.get("passed", False)
                })

    # 统计Prompt日志
    prompt_count = _count_prompt_logs(ip_id)

    # 生成内容哈希（作为创作唯一性证明）
    content_fingerprint = _generate_fingerprint(ip_id, ip_card, episodes)

    record = {
        "record_id":       f"CR-{ip_id.upper()}-{datetime.now().strftime('%Y%m%d')}",
        "created_at":      datetime.now().isoformat(),
        "ip_id":           ip_id,
        "ip_name":         ip_card["name"],

        # 作品基本信息
        "work_info": {
            "title":           f"AI动态漫剧《{ip_card['name']}》系列",
            "type":            "动态漫剧",
            "creation_method": "人工智能辅助创作",
            "creator":         "系统用户（自然人）",
            "creation_start":  ip_card.get("created_at", ""),
            "episode_count":   len(episodes),
            "total_duration":  sum(e["duration"] for e in episodes),
        },

        # 角色创作说明
        "character_creation": {
            "name":         ip_card["name"],
            "appearance":   ip_card["visual"]["appearance"],
            "personality":  ip_card["character"]["核心性格"],
            "catchphrases": ip_card["character"]["口头禅"],
            "world":        ip_card["world"]["setting"],
            "art_style":    ip_card["visual"]["style"]
        },

        # 创作工具声明
        "tools_declaration": {
            "text_model":  os.getenv("AGNES_TEXT_MODEL", "agnes-2.0-flash"),
            "image_model": os.getenv("AGNES_IMAGE_MODEL", "agnes-image-2.1-flash"),
            "video_model": os.getenv("AGNES_VIDEO_MODEL", "agnes-video-v2.0"),
            "tts_model":   "mimo-v2.5-tts",
            "human_input": "角色设计、剧情主题、风格参数、创作审核均由人工完成"
        },

        # 创作过程证明
        "creation_evidence": {
            "prompt_call_count": prompt_count,
            "qc_review_count":   len(qc_list),
            "human_checkpoints": 5,  # C1~C5
            "lora_training":     os.path.exists(
                f"../models/lora/{ip_id}.safetensors"
            )
        },

        # 内容指纹（唯一性证明）
        "fingerprint": content_fingerprint,

        # 作品清单
        "episode_list": episodes,
        "qc_summary":   qc_list
    }

    return record

def _generate_fingerprint(ip_id: str, ip_card: dict,
                           episodes: list) -> str:
    """生成内容指纹（MD5，用于唯一性证明）"""
    content = json.dumps({
        "ip_id":      ip_id,
        "ip_name":    ip_card["name"],
        "appearance": ip_card["visual"]["appearance"],
        "episodes":   [e["title"] for e in episodes]
    }, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()

def _count_prompt_logs(ip_id: str) -> int:
    """统计该IP相关的Prompt调用次数"""
    logs_dir = "logs/prompts"
    count    = 0
    if not os.path.exists(logs_dir):
        return 0
    for fname in os.listdir(logs_dir):
        if not fname.endswith(".jsonl"):
            continue
        with open(os.path.join(logs_dir, fname), encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("ip_id") == ip_id:
                        count += 1
                except Exception:
                    continue
    return count

# ─────────────────────────────────────────────
# PDF存证文件生成
# ─────────────────────────────────────────────

def generate_copyright_pdf(ip_id: str) -> str:
    """
    生成版权存证PDF文件
    返回PDF文件路径
    """
    os.makedirs(COPYRIGHT_DIR, exist_ok=True)
    record   = build_copyright_record(ip_id)
    out_path = os.path.join(
        COPYRIGHT_DIR,
        f"{record['record_id']}.pdf"
    )

    # 注册中文字体
    _register_font()

    doc   = SimpleDocTemplate(
        out_path, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )
    story = []
    styles = _build_styles()

    # ── 封面 ──────────────────────────────────
    story.append(Spacer(1, 2*cm))
    story.append(Paragraph("AI动态漫剧", styles["subtitle"]))
    story.append(Paragraph("版权创作存证文件", styles["title"]))
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#7c5cfc")))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph(
        f"作品名称：{record['work_info']['title']}",
        styles["normal"]
    ))
    story.append(Paragraph(
        f"存证编号：{record['record_id']}",
        styles["normal"]
    ))
    story.append(Paragraph(
        f"生成时间：{record['created_at'][:19]}",
        styles["normal"]
    ))
    story.append(Paragraph(
        f"内容指纹：{record['fingerprint'][:32]}...",
        styles["code"]
    ))
    story.append(Spacer(1, 1*cm))

    # ── 第一部分：作品信息 ────────────────────
    story.append(Paragraph("一、作品基本信息", styles["heading"]))
    wi       = record["work_info"]
    wi_data  = [
        ["字段",    "内容"],
        ["作品名称", wi["title"]],
        ["作品类型", wi["type"]],
        ["创作方式", wi["creation_method"]],
        ["创作主体", wi["creator"]],
        ["创作起始", wi["creation_start"][:10] if wi["creation_start"] else "—"],
        ["已完成集数", f"{wi['episode_count']} 集"],
        ["总时长",   f"{wi['total_duration']:.0f} 秒"],
    ]
    story.append(_build_table(wi_data))
    story.append(Spacer(1, 0.5*cm))

    # ── 第二部分：角色创作说明 ─────────────────
    story.append(Paragraph("二、角色创作说明", styles["heading"]))
    cc      = record["character_creation"]
    cc_data = [
        ["字段",    "内容"],
        ["角色名称", cc["name"]],
        ["外貌设计", cc["appearance"][:60] + "..."],
        ["核心性格", "、".join(cc["personality"])],
        ["标志口头禅", "、".join(cc["catchphrases"])],
        ["世界观背景", cc["world"]],
        ["视觉风格",  cc["art_style"]]
    ]
    story.append(_build_table(cc_data))
    story.append(Spacer(1, 0.5*cm))

    # ── 第三部分：创作工具声明 ─────────────────
    story.append(Paragraph("三、AI工具使用声明", styles["heading"]))
    td      = record["tools_declaration"]
    td_data = [
        ["工具类型", "具体模型"],
        ["文本生成", td["text_model"]],
        ["图像生成", td["image_model"]],
        ["视频生成", td["video_model"]],
        ["语音合成", td["tts_model"]],
        ["人工投入", td["human_input"]]
    ]
    story.append(_build_table(td_data))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "声明：以上AI工具均作为创作辅助手段使用。角色设计、剧情创意、"
        "风格参数设定及全部内容审核均由人工创作者完成，"
        "AI生成内容的选择、编排与最终呈现体现了创作者的独创性智力投入。",
        styles["note"]
    ))
    story.append(Spacer(1, 0.5*cm))

    # ── 第四部分：创作过程证明 ─────────────────
    story.append(Paragraph("四、创作过程证明", styles["heading"]))
    ce      = record["creation_evidence"]
    ce_data = [
        ["证明项目",   "数量/状态"],
        ["AI调用记录数",  f"{ce['prompt_call_count']} 条（详见审计日志）"],
        ["质检审核次数",  f"{ce['qc_review_count']} 次"],
        ["人工确认节点",  f"{ce['human_checkpoints']} 个"],
        ["LoRA角色训练",  "✅ 已完成" if ce['lora_training'] else "未训练"],
    ]
    story.append(_build_table(ce_data))
    story.append(Spacer(1, 0.5*cm))

    # ── 第五部分：作品清单 ────────────────────
    if record["episode_list"]:
        story.append(Paragraph("五、作品清单", styles["heading"]))
        ep_data  = [["集编号", "标题", "主题", "时长(秒)"]]
        for ep in record["episode_list"]:
            ep_data.append([
                ep["ep_id"],
                ep["title"][:20],
                ep["theme"][:15],
                f"{ep['duration']:.0f}"
            ])
        story.append(_build_table(ep_data))
        story.append(Spacer(1, 0.5*cm))

    # ── 第六部分：法律声明 ────────────────────
    story.append(Paragraph("六、法律声明", styles["heading"]))
    story.append(Paragraph(
        "本文件由AI动态漫剧IP孵化系统自动生成，作为创作过程的记录与存证。"
        "根据《中华人民共和国著作权法》及相关司法实践，"
        "利用AI工具进行创作且体现人类独创性智力投入的作品，"
        "其著作权归属于实际创作的自然人。"
        "本存证文件记录了创作过程中的关键参数、人工决策节点及内容指纹，"
        "可作为著作权归属的辅助证明材料。",
        styles["note"]
    ))
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#2a2a40")))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        f"存证时间：{record['created_at'][:19]}　　"
        f"指纹：{record['fingerprint'][:16]}",
        styles["footer"]
    ))

    doc.build(story)
    print(f"[版权] PDF已生成：{out_path}")
    return out_path

# ─────────────────────────────────────────────
# 完整存证包（PDF + JSON + 参考图）
# ─────────────────────────────────────────────

def export_copyright_package(ip_id: str) -> str:
    """
    打包完整版权存证包
    包含：PDF存证文件 + JSON原始数据 + 角色参考图
    返回zip文件路径
    """
    os.makedirs(COPYRIGHT_DIR, exist_ok=True)
    record   = build_copyright_record(ip_id)
    date_str = datetime.now().strftime("%Y%m%d")
    zip_path = os.path.join(
        COPYRIGHT_DIR,
        f"copyright_{ip_id}_{date_str}.zip"
    )

    # 生成PDF
    pdf_path  = generate_copyright_pdf(ip_id)

    # 保存JSON数据
    json_path = os.path.join(COPYRIGHT_DIR, f"{record['record_id']}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    # 打包
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # PDF
        zf.write(pdf_path, os.path.basename(pdf_path))
        # JSON
        zf.write(json_path, os.path.basename(json_path))
        # 角色参考图
        ref_dir = f"../assets/reference/{ip_id}_training"
        if os.path.exists(ref_dir):
            for i, fname in enumerate(
                sorted(os.listdir(ref_dir))[:5]
            ):
                fpath = os.path.join(ref_dir, fname)
                zf.write(fpath, f"reference_images/{fname}")
        # Prompt审计日志摘要
        logs_dir = "logs/prompts"
        if os.path.exists(logs_dir):
            for fname in sorted(os.listdir(logs_dir))[:3]:
                if fname.endswith(".jsonl"):
                    zf.write(
                        os.path.join(logs_dir, fname),
                        f"prompt_logs/{fname}"
                    )

    size_mb = os.path.getsize(zip_path) / (1024*1024)
    print(f"[版权] 存证包已生成：{zip_path} ({size_mb:.1f}MB)")
    return zip_path

# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────

def _register_font():
    """注册中文字体（fallback到系统字体）"""
    if os.path.exists(FONT_PATH):
        pdfmetrics.registerFont(TTFont("NotoSans", FONT_PATH))
        return "NotoSans"
    # 尝试系统字体
    fallbacks = [
        "/System/Library/Fonts/PingFang.ttc",         # macOS
        "C:/Windows/Fonts/msyh.ttc",                  # Windows
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttf" # Linux
    ]
    for path in fallbacks:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("CJKFont", path))
                return "CJKFont"
            except Exception:
                continue
    return "Helvetica"

def _build_styles() -> dict:
    """构建PDF样式"""
    font = _register_font()
    return {
        "title": ParagraphStyle(
            "title", fontName=font, fontSize=22,
            textColor=colors.HexColor("#7c5cfc"),
            spaceAfter=12, alignment=1
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontName=font, fontSize=13,
            textColor=colors.HexColor("#9090b0"),
            spaceAfter=6, alignment=1
        ),
        "heading": ParagraphStyle(
            "heading", fontName=font, fontSize=14,
            textColor=colors.HexColor("#e8e8f0"),
            spaceBefore=16, spaceAfter=8,
            borderPad=4
        ),
        "normal": ParagraphStyle(
            "normal", fontName=font, fontSize=11,
            textColor=colors.HexColor("#c0c0d8"),
            spaceAfter=6
        ),
        "note": ParagraphStyle(
            "note", fontName=font, fontSize=10,
            textColor=colors.HexColor("#9090b0"),
            spaceAfter=6, leftIndent=10
        ),
        "code": ParagraphStyle(
            "code", fontName="Courier", fontSize=9,
            textColor=colors.HexColor("#7c5cfc"),
            spaceAfter=4
        ),
        "footer": ParagraphStyle(
            "footer", fontName=font, fontSize=9,
            textColor=colors.HexColor("#606080"),
            alignment=1
        )
    }

def _build_table(data: list) -> Table:
    """构建样式统一的表格"""
    t = Table(data, colWidths=[4*cm, 13*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,0),  colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR",   (0,0), (-1,0),  colors.HexColor("#7c5cfc")),
        ("FONTSIZE",    (0,0), (-1,-1), 10),
        ("ROWBACKGROUNDS", (0,1), (-1,-1),
         [colors.HexColor("#12121a"), colors.HexColor("#16162a")]),
        ("TEXTCOLOR",   (0,1), (-1,-1), colors.HexColor("#c0c0d8")),
        ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#2a2a40")),
        ("PADDING",     (0,0), (-1,-1), 8),
        ("VALIGN",      (0,0), (-1,-1), "TOP"),
    ]))
    return t

def get_copyright_records(ip_id: str = None) -> list:
    """列出已生成的存证文件"""
    if not os.path.exists(COPYRIGHT_DIR):
        return []
    files = []
    for fname in sorted(os.listdir(COPYRIGHT_DIR), reverse=True):
        if ip_id and ip_id.upper() not in fname.upper():
            continue
        fpath = os.path.join(COPYRIGHT_DIR, fname)
        files.append({
            "filename": fname,
            "path":     fpath,
            "size_mb":  round(os.path.getsize(fpath)/(1024*1024), 2),
            "created":  datetime.fromtimestamp(
                os.path.getmtime(fpath)
            ).isoformat()
        })
    return files