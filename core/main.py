from __future__ import annotations

from fastapi import FastAPI

from core.controllers import chat_router

app = FastAPI(
    title="TARA",
    version="0.1.0",
)

app.include_router(chat_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "TARA", "status": "ok"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"ok": "true"}
