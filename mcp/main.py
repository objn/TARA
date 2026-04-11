from __future__ import annotations

from fastapi import FastAPI

from mcp.controllers.tools import router as tools_router
from mcp.tools.registry import load_builtin_tools

app = FastAPI(title="TARA MCP", version="0.1.0")

app.include_router(tools_router)


@app.on_event("startup")
def _startup() -> None:
    load_builtin_tools()


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "TARA MCP", "status": "ok"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"ok": "true"}
