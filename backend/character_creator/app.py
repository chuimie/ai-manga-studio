# FastAPI主服务：角色卡工坊

import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from openai import OpenAI
from dotenv import load_dotenv

from state_machine import StateMachine, State
from fuzzy_detector import detect_fuzzy
from prompt_builder import build_system_prompt, build_preview_prompt
from card_generator import draft_to_card, save_card, get_next_ip_id

load_dotenv()

app = FastAPI()

# Agnes AI客户端
client = OpenAI(
    api_key=os.getenv("AGNES_API_KEY"),
    base_url=os.getenv("AGNES_BASE_URL")
)

# 挂载前端静态文件
app.mount("/static", StaticFiles(directory="../../frontend"), name="static")

@app.get("/")
async def root():
    with open("../../frontend/index.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())

# 存储每个连接的状态机（单用户，本地工具）
sessions: dict[str, StateMachine] = {}

@app.websocket("/ws/creator")
async def creator_websocket(websocket: WebSocket):
    await websocket.accept()
    session_id = "local"
    sm = StateMachine()
    sessions[session_id] = sm

    # 发送开场白
    await websocket.send_json({
        "type": "ai_message",
        "content": sm.get_opening_message(),
        "state": sm.state.name,
        "progress": sm.draft.completion_rate()
    })

    try:
        while True:
            data = await websocket.receive_json()
            user_input = data.get("message", "")

            # ─── 处理人工确认节点 ───────────────────────
            if data.get("action") == "confirm_card":
                # 节点①：确认角色卡 → 写入文件
                ip_id = get_next_ip_id()
                card = draft_to_card(sm.draft, ip_id)
                filepath = save_card(card)
                sm.state = State.VOICE_CONFIRM
                await websocket.send_json({
                    "type": "card_saved",
                    "ip_id": ip_id,
                    "filepath": filepath,
                    "message": f"✅ 角色卡已保存！\n下一步：生成声线",
                    "state": sm.state.name
                })
                continue

            if data.get("action") == "regenerate":
                # 重新生成：保留已有信息，回到上一个缺失STATE
                sm.state = sm.next_missing_state()
                await websocket.send_json({
                    "type": "ai_message",
                    "content": "好，我们重新来过。已保留你之前填写的信息，告诉我想修改哪里？",
                    "state": sm.state.name,
                    "progress": sm.draft.completion_rate()
                })
                continue

            # ─── 模糊词检测（优先于LLM调用）────────────
            fuzzy = detect_fuzzy(user_input)
            if fuzzy and sm.state not in [State.FUZZY_CLARIFY, State.PREVIEW]:
                sm.pending_fuzzy = fuzzy
                sm.state = State.FUZZY_CLARIFY
                await websocket.send_json({
                    "type": "ai_message",
                    "content": fuzzy["question"],
                    "state": sm.state.name,
                    "progress": sm.draft.completion_rate()
                })
                continue

            # ─── 调用Agnes LLM提取信息 + 生成追问 ───────
            sm.history.append({"role": "user", "content": user_input})

            system_prompt = build_system_prompt(
                draft_dict=sm.draft.__dict__,
                missing_state=sm.next_missing_state().name
            )

            response = client.chat.completions.create(
                model=os.getenv("AGNES_TEXT_MODEL"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    *sm.history
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )

            result = json.loads(response.choices[0].message.content)
            extracted = result.get("extracted", {})
            ai_reply  = result.get("reply", "")

            # 更新状态机
            new_state = sm.advance(user_input, extracted)
            sm.history.append({"role": "assistant", "content": ai_reply})

            # ─── 进入预览STATE → 生成角色卡预览 ──────────
            if new_state == State.PREVIEW:
                preview_response = client.chat.completions.create(
                    model=os.getenv("AGNES_TEXT_MODEL"),
                    messages=[{
                        "role": "user",
                        "content": build_preview_prompt(sm.draft.__dict__)
                    }],
                    temperature=0.8
                )
                preview_text = preview_response.choices[0].message.content

                await websocket.send_json({
                    "type": "preview_ready",
                    "content": preview_text,
                    "draft": sm.draft.__dict__,
                    "state": new_state.name,
                    "progress": sm.draft.completion_rate(),
                    "actions": ["confirm", "modify", "regenerate"]
                })
            else:
                await websocket.send_json({
                    "type": "ai_message",
                    "content": ai_reply,
                    "state": new_state.name,
                    "progress": sm.draft.completion_rate()
                })

    except WebSocketDisconnect:
        sessions.pop(session_id, None)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)