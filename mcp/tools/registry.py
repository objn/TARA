from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict

JsonDict = Dict[str, Any]
ToolHandler = Callable[[JsonDict], Any]


def _tool_datastring(name: str, description: str) -> str:
    d = " ".join((description or "").split())
    if len(d) > 160:
        d = d[:157] + "..."
    return f"{name} — {d}"


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    description: str
    args_schema: JsonDict
    handler: ToolHandler

    @property
    def datastring(self) -> str:
        return _tool_datastring(self.name, self.description)

    def to_spec(self) -> JsonDict:
        return {
            "name": self.name,
            "description": self.description,
            "args_schema": self.args_schema,
            "datastring": self.datastring,
        }


TOOL_REGISTRY: Dict[str, RegisteredTool] = {}


def clear_registry() -> None:
    TOOL_REGISTRY.clear()


def register_tool(tool: RegisteredTool) -> None:
    TOOL_REGISTRY[tool.name] = tool


def get_tool(name: str) -> RegisteredTool | None:
    return TOOL_REGISTRY.get(name)


def list_specs() -> list[JsonDict]:
    return [t.to_spec() for t in TOOL_REGISTRY.values()]


def load_builtin_tools() -> None:
    clear_registry()
    from mcp.tools import builtins as builtins_mod

    builtins_mod.register_all(register_tool)
