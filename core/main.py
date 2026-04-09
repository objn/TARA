from __future__ import annotations

import json
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.services.provider.openai import provider

app = FastAPI(
    title="TARA",
    version="0.1.0",
)


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "TARA", "status": "ok"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"ok": "true"}


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1)
    system: Optional[str] = None
    model: Optional[str] = None
    reasoning: bool = False
    reasoning_effort: Optional[str] = None


@app.post("/chat")
def chat(req: ChatRequest) -> dict[str, str]:
    text = provider.invoke_text(
        req.prompt,
        system=req.system,
        model=req.model,
        reasoning=req.reasoning,
        reasoning_effort=req.reasoning_effort,
    )
    return {"text": text}


@app.post("/chat/stream")
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
            # Helps with some reverse proxies buffering SSE.
            "X-Accel-Buffering": "no",
        },
    )
