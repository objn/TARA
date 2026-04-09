from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, runtime_checkable

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


@runtime_checkable
class StreamingProvider(Protocol):
    def stream_text(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        model: Optional[str] = None,
        reasoning: bool = False,
        reasoning_effort: Optional[str] = None,
    ) -> Iterable[str]: ...


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

    max_tool_steps: int = 10

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

    def stream(
        self,
        task: str,
        *,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        max_tool_steps: Optional[int] = None,
    ) -> Iterable[JsonDict]:
        """
        Streaming, step-by-step agent runner.

        Yields events in order:
        - {type: "reasoning", reasoning: {...}}
        - {type: "step_start", step: int}
        - {type: "model_delta", step: int, delta: str}
        - {type: "model_message", step: int, raw: str, parsed: dict}
        - {type: "tool_call", step: int, tool: str, args: dict}
        - {type: "tool_result", step: int, tool: str, args: dict, result: any}
        - {type: "final", final_answer: str}

        Notes:
        - Stops early when "final" is produced.
        - Requires provider to implement stream_text(); otherwise falls back to run() and emits "final".
        """
        # If streaming isn't available, do a normal run and emit final.
        if not isinstance(self.provider, StreamingProvider):
            res = self.run(task, model=model, reasoning_effort=reasoning_effort)
            yield {"type": "final", "final_answer": res.final_answer}
            return

        reasoning = ReasoningResult()
        history: List[JsonDict] = []
        tools_json = _json_dumps([t.to_json() for t in self.tools.values()])

        tool_limit = int(max_tool_steps if max_tool_steps is not None else self.max_tool_steps)
        tool_limit = max(0, tool_limit)
        tool_used = 0

        current_reasoning_step = "problem_definition"

        # Reasoning is incremental; after EACH reasoning step we allow tool-loop immediately.
        for ev in self.pipeline.stream_steps(
            task,
            provider=self.provider,
            model=model,
            reasoning_effort=reasoning_effort,
            start_step=current_reasoning_step,
        ):
            step = str(ev.get("step", "")).strip() or current_reasoning_step
            content = str(ev.get("content", "")).strip()
            next_step = str(ev.get("next_step", "")).strip()

            yield {"type": "reasoning_step", "step": step, "content": content, "next_step": next_step}

            # Accumulate into ReasoningResult for downstream summary.
            if step == "problem_definition":
                reasoning.problem_definition = content
            elif step == "planning":
                reasoning.planning = content
            elif step == "analysis_and_design":
                reasoning.analysis_and_design = content
            elif step == "implementation":
                reasoning.implementation = content
            elif step == "testing":
                reasoning.testing = content
            elif step == "reporting":
                reasoning.reporting = content
            elif step == "final_answer":
                reasoning.final_answer = content

            a = ev.get("assumptions")
            if isinstance(a, list):
                reasoning.assumptions.extend([str(x) for x in a if str(x).strip()])

            # Tool loop for this reasoning step (until final or tool_limit exhausted).
            reasoning_summary = _json_dumps(
                {
                    "problem_definition": reasoning.problem_definition,
                    "planning": reasoning.planning,
                    "analysis_and_design": reasoning.analysis_and_design,
                    "current_step": step,
                    "current_step_content": content,
                    "next_step_hint": next_step,
                }
            )

            while tool_used < tool_limit:
                yield {
                    "type": "step_start",
                    "step": tool_used + 1,
                    "max_tool_steps": tool_limit,
                    "reasoning_step": step,
                }

                prompt = self.tool_user_prompt_template.format(
                    task=task.strip(),
                    reasoning_summary=reasoning_summary,
                    tools_json=tools_json,
                    history_json=_json_dumps(history),
                )

                raw = ""
                for delta in self.provider.stream_text(
                    prompt,
                    system=self.tool_system_prompt,
                    model=model,
                    reasoning=True,
                    reasoning_effort=reasoning_effort,
                ):
                    if not delta:
                        continue
                    d = str(delta)
                    raw += d
                    yield {
                        "type": "model_delta",
                        "step": tool_used + 1,
                        "reasoning_step": step,
                        "delta": d,
                    }

                raw = raw.strip()
                msg = _safe_parse_json(raw)
                yield {
                    "type": "model_message",
                    "step": tool_used + 1,
                    "reasoning_step": step,
                    "raw": raw,
                    "parsed": msg,
                }

                tool_used += 1

                msg_type = str(msg.get("type", "")).strip().lower()
                if msg_type == "final":
                    fa = str(msg.get("final_answer", "")).strip() or raw
                    yield {"type": "final", "final_answer": fa}
                    return

                if msg_type != "tool_call":
                    # No tool requested; leave tool-loop for this reasoning step.
                    break

                tool_name = str(msg.get("tool", "")).strip()
                args = msg.get("args")
                if not isinstance(args, dict):
                    args = {}

                yield {
                    "type": "tool_call",
                    "step": tool_used,
                    "reasoning_step": step,
                    "tool": tool_name,
                    "args": args,
                }

                tool = self.tools.get(tool_name)
                if not tool:
                    history.append({"role": "tool_error", "tool": tool_name, "error": f"Unknown tool: {tool_name}"})
                    continue

                try:
                    result = tool.fn(args)
                except Exception as e:  # pragma: no cover
                    result = {"error": str(e)}

                yield {
                    "type": "tool_result",
                    "step": tool_used,
                    "reasoning_step": step,
                    "tool": tool_name,
                    "args": args,
                    "result": result,
                }
                history.append({"role": "tool_result", "tool": tool_name, "args": args, "result": result})

            if next_step == "final_answer":
                fa = reasoning.final_answer.strip()
                if fa:
                    yield {"type": "final", "final_answer": fa}
                return

            current_reasoning_step = next_step or current_reasoning_step

        fa = reasoning.final_answer.strip()
        if fa:
            yield {"type": "final", "final_answer": fa}


