from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx

JsonDict = Dict[str, Any]


def _json_loads(s: str) -> Any:
    try:
        return json.loads(s)
    except Exception:
        return {}


def fetch_tool_specs(base_url: str, *, timeout_s: float = 30.0) -> List[JsonDict]:
    url = f"{base_url.rstrip('/')}/tools"
    with httpx.Client(timeout=timeout_s) as client:
        r = client.get(url)
        r.raise_for_status()
        data = r.json()
    tools = data.get("tools")
    if not isinstance(tools, list):
        return []
    return [t for t in tools if isinstance(t, dict)]


def call_tool_stream_sync(
    base_url: str,
    tool_name: str,
    args: JsonDict,
    *,
    delay_ms: Optional[int] = None,
    timeout_s: float = 600.0,
) -> JsonDict:
    """
    POST /tools/{tool_name}/stream and parse SSE until result/error/done.
    Returns the tool result dict from the MCP handler (inner value), or {error: ...}.
    """
    url = f"{base_url.rstrip('/')}/tools/{tool_name}/stream"
    body: JsonDict = {"args": args if isinstance(args, dict) else {}}
    if delay_ms is not None:
        body["delay_ms"] = delay_ms

    last_result: JsonDict = {}
    last_error: Optional[str] = None

    with httpx.Client(timeout=timeout_s) as client:
        with client.stream(
            "POST",
            url,
            json=body,
            headers={"Accept": "text/event-stream"},
        ) as r:
            r.raise_for_status()
            event_name: Optional[str] = None
            data_parts: list[str] = []

            for line in r.iter_lines():
                if line is None:
                    continue
                if line.startswith(":"):
                    continue
                if line == "":
                    if event_name and data_parts:
                        raw = "".join(data_parts)
                        payload = _json_loads(raw) if raw.strip() else {}
                        if not isinstance(payload, dict):
                            payload = {"_value": payload}
                        if event_name == "result":
                            inner = payload.get("result")
                            if isinstance(inner, dict):
                                last_result = inner
                            else:
                                last_result = {"_raw": inner}
                        elif event_name == "error":
                            last_error = str(payload.get("error", payload))
                    event_name = None
                    data_parts = []
                    continue
                if line.startswith("event:"):
                    event_name = line[6:].strip()
                elif line.startswith("data:"):
                    data_parts.append(line[5:].lstrip())

    if last_error is not None:
        return {"ok": False, "error": last_error}
    if last_result:
        return last_result
    return {"ok": False, "error": "No result event from MCP"}
