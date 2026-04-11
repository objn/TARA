from __future__ import annotations

from typing import List, Optional

from core.configs.settings import ENV, Env
from core.services.agents.main import Tool
from core.services.mcp.client import call_tool_stream_sync, fetch_tool_specs


def _require_env() -> Env:
    if ENV is not None:
        return ENV
    return Env.load()


def tools_from_mcp(base_url: Optional[str] = None) -> List[Tool]:
    cfg = _require_env()
    url = base_url or cfg.mcp_base_url
    specs = fetch_tool_specs(url)

    tools: List[Tool] = []
    for spec in specs:
        name = str(spec.get("name", "")).strip()
        if not name:
            continue
        description = str(spec.get("description", "")).strip()
        args_schema = spec.get("args_schema")
        if not isinstance(args_schema, dict):
            args_schema = {}

        def _make_fn(tool_name: str, mcp_url: str):
            def fn(args):
                delay = cfg.MCP_DEFAULT_TOOL_DELAY_MS
                return call_tool_stream_sync(mcp_url, tool_name, args, delay_ms=delay)

            return fn

        tools.append(
            Tool(
                name=name,
                description=description,
                args_schema=args_schema,
                fn=_make_fn(name, url),
            )
        )
    return tools


def register_mcp_tools(agent, *, base_url: Optional[str] = None) -> int:
    for t in tools_from_mcp(base_url):
        agent.register_tool(t)
    return len(agent.tools)
