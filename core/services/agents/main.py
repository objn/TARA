from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from core.services.agents.reasoning.pipeline import ReasoningPipeline, ReasoningProvider, ReasoningResult
from core.services.agents.reasoning.prompts import (
    TOOL_AGENT_SYSTEM_PROMPT,
    TOOL_AGENT_USER_PROMPT_TEMPLATE,
)


JsonDict = Dict[str, Any]
ToolFn = Callable[[JsonDict], Any]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_schema: JsonDict
    fn: ToolFn

    def to_json(self) -> JsonDict:
        return {
            "name": self.name,
            "description": self.description,
            "args_schema": self.args_schema,
        }


@dataclass
class ToolStep:
    tool: str
    args: JsonDict
    result: Any


@dataclass
class AgentRunResult:
    reasoning: ReasoningResult
    final_answer: str
    steps: List[ToolStep] = field(default_factory=list)
    raw_messages: List[JsonDict] = field(default_factory=list)


def _safe_parse_json(text: str) -> JsonDict:
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {"_value": obj}
    except Exception:
        return {}


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)


@dataclass
class Agent:
    """
    Agent runtime that:
    - uses the ReasoningPipeline for structured reasoning
    - can iteratively call tools to gather info / perform actions

    Provider-agnostic: any provider that implements `invoke_text()` can be used.
    """

    provider: ReasoningProvider
    pipeline: ReasoningPipeline = field(default_factory=ReasoningPipeline)
    tools: Dict[str, Tool] = field(default_factory=dict)

    tool_system_prompt: str = TOOL_AGENT_SYSTEM_PROMPT
    tool_user_prompt_template: str = TOOL_AGENT_USER_PROMPT_TEMPLATE

    max_tool_steps: int = 6

    def register_tool(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def run(
        self,
        task: str,
        *,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
    ) -> AgentRunResult:
        # 1) Produce a structured reasoning scaffold first.
        reasoning = self.pipeline.run(
            task,
            provider=self.provider,
            model=model,
            reasoning_effort=reasoning_effort,
        )

        # 2) Tool loop (optional): let the model decide to call tools or finish.
        history: List[JsonDict] = []
        steps: List[ToolStep] = []
        raw_messages: List[JsonDict] = []

        reasoning_summary = _json_dumps(
            {
                "problem_definition": reasoning.problem_definition,
                "planning": reasoning.planning,
                "analysis_and_design": reasoning.analysis_and_design,
            }
        )
        tools_json = _json_dumps([t.to_json() for t in self.tools.values()])

        final_answer = reasoning.final_answer.strip()

        for _ in range(max(0, int(self.max_tool_steps))):
            prompt = self.tool_user_prompt_template.format(
                task=task.strip(),
                reasoning_summary=reasoning_summary,
                tools_json=tools_json,
                history_json=_json_dumps(history),
            )

            text = self.provider.invoke_text(
                prompt,
                system=self.tool_system_prompt,
                model=model,
                reasoning=True,
                reasoning_effort=reasoning_effort,
            ).strip()

            msg = _safe_parse_json(text)
            raw_messages.append({"raw": text, "parsed": msg})

            msg_type = str(msg.get("type", "")).strip().lower()
            if msg_type == "final":
                fa = str(msg.get("final_answer", "")).strip()
                if fa:
                    final_answer = fa
                break

            if msg_type != "tool_call":
                # If the model responded in an unexpected format, stop and return what we have.
                break

            tool_name = str(msg.get("tool", "")).strip()
            args = msg.get("args")
            if not isinstance(args, dict):
                args = {}

            tool = self.tools.get(tool_name)
            if not tool:
                history.append(
                    {
                        "role": "tool_error",
                        "tool": tool_name,
                        "error": f"Unknown tool: {tool_name}",
                    }
                )
                continue

            try:
                result = tool.fn(args)
            except Exception as e:  # pragma: no cover
                result = {"error": str(e)}

            steps.append(ToolStep(tool=tool_name, args=args, result=result))
            history.append(
                {
                    "role": "tool_result",
                    "tool": tool_name,
                    "args": args,
                    "result": result,
                }
            )

        return AgentRunResult(
            reasoning=reasoning,
            final_answer=final_answer,
            steps=steps,
            raw_messages=raw_messages,
        )

