from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.services.chat.main import ChatService, CreateTopicRequestDTO, RunChatRequestDTO, SendMessageRequestDTO
from core.services.agents.main import Agent
from core.services.agents.tools.calculator import calculator_tool
from core.services.provider.openai import provider

router = APIRouter(tags=["chat"])

chat_service = ChatService()
agent = Agent(provider=provider)
agent.register_tool(calculator_tool())
agent.max_tool_steps = 10


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1)
    system: Optional[str] = None
    model: Optional[str] = None
    reasoning: bool = False
    reasoning_effort: Optional[str] = None
    max_tool_steps: int = 10


@router.post("/chat")
def chat(req: ChatRequest) -> dict[str, str]:
    text = provider.invoke_text(
        req.prompt,
        system=req.system,
        model=req.model,
        reasoning=req.reasoning,
        reasoning_effort=req.reasoning_effort,
    )
    return {"text": text}


@router.post("/chat/stream")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    def event_iter():
        try:
            for delta in provider.stream_text(
                req.prompt,
                system=req.system,
                model=req.model,
                reasoning=req.reasoning,
                reasoning_effort=req.reasoning_effort,
            ):
                if not delta:
                    continue
                payload = json.dumps({"delta": delta}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
            yield "event: done\ndata: {}\n\n"
        except Exception as e:
            payload = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"event: error\ndata: {payload}\n\n"
            yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_iter(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/agent/stream")
def agent_stream(req: ChatRequest) -> StreamingResponse:
    """
    SSE stream that supports tool-loop step-by-step.

    Emits events:
    - reasoning
    - step_start
    - model_delta
    - model_message
    - tool_call
    - tool_result
    - final
    """

    def event_iter():
        try:
            for ev in agent.stream(
                req.prompt,
                model=req.model,
                reasoning_effort=req.reasoning_effort,
                max_tool_steps=req.max_tool_steps,
            ):
                et = str(ev.get("type", "message"))
                payload = json.dumps(ev, ensure_ascii=False, default=str)
                yield f"event: {et}\ndata: {payload}\n\n"
            yield "event: done\ndata: {}\n\n"
        except Exception as e:
            payload = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"event: error\ndata: {payload}\n\n"
            yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_iter(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/topics")
def create_chat_topic(req: CreateTopicRequestDTO):
    try:
        return chat_service.create_topic(req.title)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/chat/messages")
def send_chat_message(req: SendMessageRequestDTO):
    try:
        return chat_service.send_message(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/chat/run")
def run_chat(req: RunChatRequestDTO):
    try:
        return chat_service.run_chat(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

