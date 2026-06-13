# 动态构建发给LLM的System Prompt + 追问指令

import json

# 各STATE对应的追问话术
STATE_QUESTIONS = {
    "GENDER_AGE": "这个角色是男是女？大概几岁的感觉？",
    "APPEARANCE": "有没有参考形象（动漫/真人/草图）？\n或者描述一个你最想要的外貌细节。",
    "ART_STYLE": "画风偏哪种？\n① 日系Q版  ② 国风水墨  ③ 写实欧美  ④ 其他（请描述）",
    "PERSONALITY": "用3个词描述他/她的性格——\n比如「蠢萌 + 善良 + 执行力离谱」",
    "WORLD": "这个角色生活在什么世界？\n校园 / 都市 / 玄幻架空 / 古代 / 其他？",
    "STYLE_MATRIX": """从以下选项各选一个：
题材：都市 / 玄幻 / 悬疑 / 爱情
基调：热血 / 治愈 / 黑暗 / 喜剧
叙事：线性叙事 / 插叙 / 多视角 / 单场景深挖
节奏：快节奏 / 慢节奏 / 张弛交替 / 悬念递进""",
    "VOICE": "声音气质一句话描述？\n例如：低沉成熟 / 元气少女 / 冷酷少年 / 奶声奶气"
}

SYSTEM_PROMPT_TEMPLATE = """
你是一个AI角色设计师助手，负责通过对话帮助用户设计漫剧角色。

你的任务：
1. 从用户的每句话中提取角色信息，返回结构化JSON
2. 如果信息不足，根据[当前需要收集的字段]提出追问
3. 语气自然友好，像聊天一样，不要像填表格

当前已收集信息：
{current_draft}

当前需要收集的字段：{missing_field}
对应追问话术：{question}

提取规则：
- 从用户输入中提取所有能识别的字段
- 对模糊词（帅/萌/酷/美等）不要自行解释，标记为需要追问
- 返回格式严格为JSON：
{{
  "extracted": {{
    "gender": null或"男"或"女",
    "age_feel": null或年龄描述,
    "appearance": null或外貌描述,
    "art_style": null或画风,
    "personality": []或[性格词列表],
    "world_setting": null或世界观,
    "genre": null或题材,
    "tone": null或基调,
    "narrative": null或叙事结构,
    "pacing": null或节奏,
    "voice_prompt": null或声线描述
  }},
  "needs_fuzzy_clarify": true或false,
  "fuzzy_word": null或检测到的模糊词,
  "reply": "你对用户说的话（追问或确认）"
}}
"""

def build_system_prompt(draft_dict: dict, missing_state: str) -> str:
    question = STATE_QUESTIONS.get(missing_state, "还有什么想补充的？")
    return SYSTEM_PROMPT_TEMPLATE.format(
        current_draft=json.dumps(draft_dict, ensure_ascii=False, indent=2),
        missing_field=missing_state,
        question=question
    )

def build_preview_prompt(draft_dict: dict) -> str:
    return f"""
根据以下角色信息，生成一份完整的角色卡预览文案。
格式要求：
- 用生动的语言描述角色，像在介绍一个真实存在的人
- 包含外貌、性格、口头禅、喜剧公式四个部分
- 最后附上一段Agnes Image生成用的Prompt（英文）

角色信息：
{json.dumps(draft_dict, ensure_ascii=False, indent=2)}
"""