# 对话状态机：控制角色卡收集流程

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

class State(Enum):
    START          = 0
    GENDER_AGE     = 1
    APPEARANCE     = 2
    ART_STYLE      = 3
    PERSONALITY    = 4
    WORLD          = 5
    STYLE_MATRIX   = 6
    VOICE          = 7
    FUZZY_CLARIFY  = 8
    PREVIEW        = 9
    VOICE_CONFIRM  = 10
    IMAGE_SELECT   = 11
    DONE           = 12

@dataclass
class CharacterDraft:
    """角色卡草稿，随对话逐步填充"""
    name:            Optional[str]  = None
    gender:          Optional[str]  = None
    age_feel:        Optional[str]  = None
    appearance:      Optional[str]  = None
    art_style:       Optional[str]  = None
    personality:     list           = field(default_factory=list)
    speech_pattern:  Optional[str]  = None
    catchphrases:    list           = field(default_factory=list)
    comedy_formula:  Optional[str]  = None
    forbidden:       Optional[str]  = None
    world_setting:   Optional[str]  = None
    genre:           Optional[str]  = None
    tone:            Optional[str]  = None
    narrative:       Optional[str]  = None
    pacing:          Optional[str]  = None
    voice_prompt:    Optional[str]  = None
    voice_method:    str            = "VoiceDesign"

    def completion_rate(self) -> dict:
        """返回各维度完成度，用于前端进度条"""
        return {
            "外貌": 100 if self.appearance else 0,
            "性格": min(100, len(self.personality) * 33),
            "世界观": 100 if self.world_setting else 0,
            "画风": 100 if self.art_style else 0,
            "声线": 100 if self.voice_prompt else 0,
            "风格矩阵": sum([
                25 if self.genre else 0,
                25 if self.tone else 0,
                25 if self.narrative else 0,
                25 if self.pacing else 0
            ])
        }

    def is_ready_for_preview(self) -> bool:
        """判断是否收集完毕，可进入预览确认"""
        required = [
            self.gender, self.appearance, self.art_style,
            self.personality, self.world_setting,
            self.genre, self.tone, self.pacing, self.voice_prompt
        ]
        return all(required)


class StateMachine:
    def __init__(self):
        self.state   = State.START
        self.draft   = CharacterDraft()
        self.history = []   # 对话历史，传给LLM
        self.pending_fuzzy = None  # 待解决的模糊词

    def get_opening_message(self) -> str:
        return "想创建什么样的角色？随便说，哪怕一个词。"

    def next_missing_state(self) -> State:
        """根据草稿缺失项，决定下一个要收集的STATE"""
        if not self.draft.gender:
            return State.GENDER_AGE
        if not self.draft.appearance:
            return State.APPEARANCE
        if not self.draft.art_style:
            return State.ART_STYLE
        if len(self.draft.personality) < 2:
            return State.PERSONALITY
        if not self.draft.world_setting:
            return State.WORLD
        if not all([self.draft.genre, self.draft.tone,
                    self.draft.narrative, self.draft.pacing]):
            return State.STYLE_MATRIX
        if not self.draft.voice_prompt:
            return State.VOICE
        return State.PREVIEW

    def advance(self, user_input: str, llm_extracted: dict) -> State:
        """
        根据LLM提取结果更新草稿，返回下一个状态
        llm_extracted: LLM从用户输入中提取的结构化字段
        """
        # 合并LLM提取到草稿
        if llm_extracted.get("gender"):
            self.draft.gender = llm_extracted["gender"]
        if llm_extracted.get("age_feel"):
            self.draft.age_feel = llm_extracted["age_feel"]
        if llm_extracted.get("appearance"):
            self.draft.appearance = llm_extracted["appearance"]
        if llm_extracted.get("art_style"):
            self.draft.art_style = llm_extracted["art_style"]
        if llm_extracted.get("personality"):
            self.draft.personality.extend(llm_extracted["personality"])
            self.draft.personality = list(set(self.draft.personality))
        if llm_extracted.get("world_setting"):
            self.draft.world_setting = llm_extracted["world_setting"]
        if llm_extracted.get("genre"):
            self.draft.genre = llm_extracted["genre"]
        if llm_extracted.get("tone"):
            self.draft.tone = llm_extracted["tone"]
        if llm_extracted.get("narrative"):
            self.draft.narrative = llm_extracted["narrative"]
        if llm_extracted.get("pacing"):
            self.draft.pacing = llm_extracted["pacing"]
        if llm_extracted.get("voice_prompt"):
            self.draft.voice_prompt = llm_extracted["voice_prompt"]

        # 判断是否可以进入预览
        if self.draft.is_ready_for_preview():
            self.state = State.PREVIEW
        else:
            self.state = self.next_missing_state()

        return self.state