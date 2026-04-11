from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

JsonDict = Dict[str, Any]


class ToolSpecDTO(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    args_schema: JsonDict = Field(default_factory=dict)
    datastring: str = ""


class ToolListResponseDTO(BaseModel):
    tools: List[ToolSpecDTO]


class ToolCallStreamRequestDTO(BaseModel):
    args: JsonDict = Field(default_factory=dict)
    delay_ms: Optional[int] = Field(default=None, ge=0, le=3_600_000)


class ToolEventDTO(BaseModel):
    type: Literal["start", "progress", "result", "error", "done"]
    tool: str
    data: JsonDict = Field(default_factory=dict)


class ToolErrorDTO(BaseModel):
    ok: Literal[False] = False
    error: str
    tool: Optional[str] = None
