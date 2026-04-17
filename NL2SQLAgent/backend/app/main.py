from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.database import init_db
from app.services.chat_service import build_response, build_stream, save_message
from app.services.session_service import (
    create_session,
    delete_session,
    get_session_messages,
    list_sessions,
    update_session,
)

app = FastAPI(title="智能分析系统", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5180", "http://localhost:5180"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, str]:
    return {"version": app.version}


@app.post("/api/sessions")
def api_create_session(payload: dict) -> dict:
    return create_session(payload.get("title", "新建会话"))


@app.get("/api/sessions")
def api_list_sessions() -> list[dict]:
    return list_sessions()


@app.get("/api/sessions/{session_id}/messages")
def api_session_messages(session_id: str) -> list[dict]:
    return get_session_messages(session_id)


@app.patch("/api/sessions/{session_id}")
def api_update_session(session_id: str, payload: dict) -> dict:
    result = update_session(session_id, payload.get("title", ""))
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@app.delete("/api/sessions/{session_id}")
def api_delete_session(session_id: str) -> dict:
    deleted = delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True}


@app.post("/api/chat")
def api_chat(payload: dict) -> dict:
    session_id = payload.get("sessionId")
    message = payload.get("message", "")
    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId is required")
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    model_name = payload.get("model")
    base_url = payload.get("baseUrl")
    api_key = payload.get("apiKey")

    model_name_normalized = (model_name or "").strip().lower()
    requires_vendor_key = bool(base_url) or (model_name_normalized and model_name_normalized != "qwen3-max")
    if requires_vendor_key and not api_key:
        raise HTTPException(status_code=400, detail="请先填写 API Key")

    save_message(session_id, "user", message)
    response = build_response(message, model_name=model_name, base_url=base_url, api_key=api_key, session_id=session_id)
    save_message(session_id, "assistant", response["answer_text"])
    return response


@app.post("/api/chat/stream")
def api_chat_stream(payload: dict) -> StreamingResponse:
    session_id = payload.get("sessionId")
    message = payload.get("message", "")
    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId is required")
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    model_name = payload.get("model")
    base_url = payload.get("baseUrl")
    api_key = payload.get("apiKey")

    save_message(session_id, "user", message)

    def event_generator():
        chunks: list[str] = []
        for chunk in build_stream(message, model_name=model_name, base_url=base_url, api_key=api_key):
            chunks.append(chunk)
            yield f"data: {chunk}\n\n"

        assistant_text = "".join(chunks).strip()
        if assistant_text:
            save_message(session_id, "assistant", assistant_text)
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
