from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from mcp.configs.settings import MCPSettings
from mcp.dto.tools import ToolCallStreamRequestDTO, ToolListResponseDTO, ToolSpecDTO
from mcp.tools.registry import get_tool, list_specs, load_builtin_tools

router = APIRouter(tags=["tools"])
_settings = MCPSettings()


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)


@router.get("/tools", response_model=ToolListResponseDTO)
def list_tools() -> ToolListResponseDTO:
    specs = list_specs()
    return ToolListResponseDTO(tools=[ToolSpecDTO(**s) for s in specs])


@router.post("/tools/reload")
def reload_tools() -> dict[str, str]:
    load_builtin_tools()
    return {"status": "ok", "count": str(len(list_specs()))}


@router.post("/tools/{tool_name}/stream")
async def stream_tool(tool_name: str, body: ToolCallStreamRequestDTO) -> StreamingResponse:
    tool = get_tool(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")

    delay_ms = body.delay_ms
    if delay_ms is None:
        delay_ms = _settings.MCP_DEFAULT_TOOL_DELAY_MS

    args = body.args if isinstance(body.args, dict) else {}

    async def event_iter() -> AsyncIterator[str]:
        yield f"event: start\ndata: {_json_dumps({'tool': tool_name, 'delay_ms': delay_ms})}\n\n"
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)
        try:
            yield f"event: progress\ndata: {_json_dumps({'tool': tool_name, 'phase': 'execute'})}\n\n"
            result = await asyncio.to_thread(tool.handler, args)
            payload = {"tool": tool_name, "result": result}
            yield f"event: result\ndata: {_json_dumps(payload)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {_json_dumps({'tool': tool_name, 'error': str(e)})}\n\n"
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


def include_tools_routes(app) -> None:
    app.include_router(router)
