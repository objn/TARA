from __future__ import annotations

import json
import operator
from dataclasses import dataclass, field
from functools import partial
from typing import Annotated, Any, Callable, Dict, Iterable, List, Literal, Optional, Protocol, TypedDict, runtime_checkable

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from core.services.agents.reasoning.pipeline import ReasoningPipeline, ReasoningProvider, ReasoningResult
from core.services.agents.reasoning.prompts import (
    TOOL_AGENT_SYSTEM_PROMPT,
    TOOL_AGENT_USER_PROMPT_TEMPLATE,
)


JsonDict = Dict[str, Any]
ToolFn = Callable[[JsonDict], Any]


def _tool_datastring(name: str, description: str) -> str:
    d = " ".join((description or "").split())
    if len(d) > 160:
        d = d[:157] + "..."
    return f"{name} — {d}"


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_schema: JsonDict
    fn: ToolFn

    @property
    def datastring(self) -> str:
        return _tool_datastring(self.name, self.description)

    def to_json(self) -> JsonDict:
        return {
            "name": self.name,
            "description": self.description,
            "args_schema": self.args_schema,
            "datastring": self.datastring,
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


def _tools_datastring_block(tools: Dict[str, Tool]) -> str:
    lines = [t.datastring for t in tools.values()]
    return "\n".join(lines) if lines else "(no tools)"


class RunGraphState(TypedDict, total=False):
    task: str
    model: Optional[str]
    reasoning_effort: Optional[str]
    problem_definition: str
    planning: str
    analysis_and_design: str
    implementation: str
    testing: str
    reporting: str
    reasoning_summary: str
    final_answer: str
    model_turn: int
    last_parsed: JsonDict
    assumptions: Annotated[List[str], operator.add]
    history: Annotated[List[JsonDict], operator.add]
    steps: Annotated[List[JsonDict], operator.add]
    raw_messages: Annotated[List[JsonDict], operator.add]


class StreamGraphState(TypedDict, total=False):
    task: str
    model: Optional[str]
    reasoning_effort: Optional[str]
    prev_reasoning_steps: List[JsonDict]
    reasoning_current_step: str
    reasoning_iterations: int
    stream_finished: bool
    problem_definition: str
    planning: str
    analysis_and_design: str
    implementation: str
    testing: str
    reporting: str
    reasoning_final_answer: str
    last_reasoning_step: str
    last_reasoning_content: str
    last_reasoning_next: str
    assumptions: Annotated[List[str], operator.add]
    history: Annotated[List[JsonDict], operator.add]
    steps: Annotated[List[JsonDict], operator.add]
    raw_messages: Annotated[List[JsonDict], operator.add]
    tool_used: int
    tool_limit: int
    stream_final_answer: str


def _reasoning_run_node(agent: "Agent", state: RunGraphState) -> dict[str, Any]:
    task = str(state.get("task", "")).strip()
    model = state.get("model")
    reasoning_effort = state.get("reasoning_effort")
    reasoning = agent.pipeline.run(
        task,
        provider=agent.provider,
        model=model,
        reasoning_effort=reasoning_effort,
    )
    reasoning_summary = _json_dumps(
        {
            "problem_definition": reasoning.problem_definition,
            "planning": reasoning.planning,
            "analysis_and_design": reasoning.analysis_and_design,
        }
    )
    return {
        "problem_definition": reasoning.problem_definition,
        "planning": reasoning.planning,
        "analysis_and_design": reasoning.analysis_and_design,
        "implementation": reasoning.implementation,
        "testing": reasoning.testing,
        "reporting": reasoning.reporting,
        "reasoning_summary": reasoning_summary,
        "final_answer": reasoning.final_answer.strip(),
        "assumptions": list(reasoning.assumptions or []),
        "model_turn": 0,
        "last_parsed": {},
    }


def _model_run_node(agent: "Agent", state: RunGraphState) -> dict[str, Any]:
    if int(state.get("model_turn", 0)) >= int(agent.max_tool_steps):
        return {"last_parsed": {"type": "final", "final_answer": state.get("final_answer", "")}}

    turn = int(state.get("model_turn", 0)) + 1
    task = str(state.get("task", "")).strip()
    model = state.get("model")
    reasoning_effort = state.get("reasoning_effort")
    history = list(state.get("history", []))

    prompt = agent.format_tool_user_prompt(
        task=task,
        reasoning_summary=str(state.get("reasoning_summary", "")),
        history=history,
    )

    text = agent.provider.invoke_text(
        prompt,
        system=agent.tool_system_prompt,
        model=model,
        reasoning=True,
        reasoning_effort=reasoning_effort,
    ).strip()

    msg = _safe_parse_json(text)
    return {
        "model_turn": turn,
        "raw_messages": [{"raw": text, "parsed": msg}],
        "last_parsed": msg,
    }


def _route_after_model_run(agent: "Agent", state: RunGraphState) -> Literal["tools", "end"]:
    msg = state.get("last_parsed") or {}
    msg_type = str(msg.get("type", "")).strip().lower()
    if msg_type == "final":
        return "end"
    if msg_type == "tool_call":
        return "tools"
    return "end"


def _tool_run_node(agent: "Agent", state: RunGraphState) -> dict[str, Any]:
    msg = state.get("last_parsed") or {}
    tool_name = str(msg.get("tool", "")).strip()
    args = msg.get("args")
    if not isinstance(args, dict):
        args = {}

    tool = agent.tools.get(tool_name)
    if not tool:
        return {
            "history": [
                {
                    "role": "tool_error",
                    "tool": tool_name,
                    "error": f"Unknown tool: {tool_name}",
                }
            ]
        }

    try:
        result = tool.fn(args)
    except Exception as e:  # pragma: no cover
        result = {"error": str(e)}

    step_dict = {"tool": tool_name, "args": args, "result": result}
    return {
        "history": [{"role": "tool_result", "tool": tool_name, "args": args, "result": result}],
        "steps": [step_dict],
    }


def _finalize_run_node(state: RunGraphState) -> dict[str, Any]:
    msg = state.get("last_parsed") or {}
    msg_type = str(msg.get("type", "")).strip().lower()
    if msg_type == "final":
        fa = str(msg.get("final_answer", "")).strip()
        if fa:
            return {"final_answer": fa}
    return {}


def _build_run_graph(agent: "Agent"):
    g = StateGraph(RunGraphState)
    g.add_node("reasoning", partial(_reasoning_run_node, agent))
    g.add_node("model", partial(_model_run_node, agent))
    g.add_node("tools", partial(_tool_run_node, agent))
    g.add_node("finalize", _finalize_run_node)

    g.add_edge(START, "reasoning")
    g.add_edge("reasoning", "model")
    g.add_conditional_edges(
        "model",
        partial(_route_after_model_run, agent),
        {"tools": "tools", "end": "finalize"},
    )
    g.add_edge("tools", "model")
    g.add_edge("finalize", END)
    return g.compile()


def _merge_reasoning_scalar(state: StreamGraphState, step: str, content: str) -> dict[str, Any]:
    key = {
        "problem_definition": "problem_definition",
        "planning": "planning",
        "analysis_and_design": "analysis_and_design",
        "implementation": "implementation",
        "testing": "testing",
        "reporting": "reporting",
        "final_answer": "reasoning_final_answer",
    }.get(step, "")
    if not key:
        return {}
    return {key: content}


def _next_reasoning_stream_node(agent: "Agent", state: StreamGraphState) -> dict[str, Any]:
    writer = None
    try:
        writer = get_stream_writer()
    except Exception:
        writer = None

    task = str(state.get("task", "")).strip()
    model = state.get("model")
    reasoning_effort = state.get("reasoning_effort")
    current = str(state.get("reasoning_current_step", "problem_definition")).strip() or "problem_definition"
    prev = list(state.get("prev_reasoning_steps", []))

    if int(state.get("reasoning_iterations", 0)) >= 14:
        return {
            "last_reasoning_next": "final_answer",
            "last_reasoning_step": str(state.get("last_reasoning_step", "")).strip() or "final_answer",
            "last_reasoning_content": str(state.get("last_reasoning_content", "")).strip(),
        }

    out = agent.pipeline.stream_one_step(
        task,
        provider=agent.provider,
        model=model,
        reasoning_effort=reasoning_effort,
        current_step=current,
        previous_steps=prev,
    )

    step = str(out.get("step", "")).strip() or current
    content = str(out.get("content", "")).strip()
    next_step = str(out.get("next_step", "final_answer")).strip() or "final_answer"
    step_assumptions = out.get("assumptions") or []
    if not isinstance(step_assumptions, list):
        step_assumptions = []

    new_prev = prev + [{"step": step, "content": content}]

    if writer:
        writer({"type": "reasoning_step", "step": step, "content": content, "next_step": next_step})

    scalar_updates = _merge_reasoning_scalar(state, step, content)
    inc = int(state.get("reasoning_iterations", 0)) + 1

    return {
        "prev_reasoning_steps": new_prev,
        "reasoning_current_step": next_step,
        "last_reasoning_step": step,
        "last_reasoning_content": content,
        "last_reasoning_next": next_step,
        "reasoning_iterations": inc,
        "assumptions": [str(x) for x in step_assumptions if str(x).strip()],
        **scalar_updates,
    }


def _route_after_reasoning_stream(state: StreamGraphState) -> Literal["more_reasoning", "tool_round", "finalize"]:
    next_step = str(state.get("last_reasoning_next", "")).strip()
    step = str(state.get("last_reasoning_step", "")).strip()

    if next_step == "final_answer":
        return "finalize"
    if step in {"problem_definition", "planning"}:
        return "more_reasoning"
    return "tool_round"


def _tool_round_stream_node(agent: "Agent", state: StreamGraphState) -> dict[str, Any]:
    if not isinstance(agent.provider, StreamingProvider):
        return {}

    writer = None
    try:
        writer = get_stream_writer()
    except Exception:
        writer = None

    task = str(state.get("task", "")).strip()
    model = state.get("model")
    reasoning_effort = state.get("reasoning_effort")
    history = list(state.get("history", []))
    tool_limit = max(0, int(state.get("tool_limit", agent.max_tool_steps)))
    tool_used = int(state.get("tool_used", 0))

    reasoning_summary = _json_dumps(
        {
            "problem_definition": state.get("problem_definition", ""),
            "planning": state.get("planning", ""),
            "analysis_and_design": state.get("analysis_and_design", ""),
            "current_step": state.get("last_reasoning_step", ""),
            "current_step_content": state.get("last_reasoning_content", ""),
            "next_step_hint": state.get("last_reasoning_next", ""),
        }
    )

    updates: dict[str, Any] = {}
    raw_messages_acc: List[JsonDict] = []
    history_acc: List[JsonDict] = []
    steps_acc: List[JsonDict] = []

    while tool_used < tool_limit:
        if writer:
            writer(
                {
                    "type": "step_start",
                    "step": tool_used + 1,
                    "max_tool_steps": tool_limit,
                    "reasoning_step": state.get("last_reasoning_step", ""),
                }
            )

        prompt = agent.format_tool_user_prompt(
            task=task,
            reasoning_summary=reasoning_summary,
            history=history + history_acc,
        )

        raw = ""
        for delta in agent.provider.stream_text(
            prompt,
            system=agent.tool_system_prompt,
            model=model,
            reasoning=True,
            reasoning_effort=reasoning_effort,
        ):
            if not delta:
                continue
            d = str(delta)
            raw += d
            if writer:
                writer(
                    {
                        "type": "model_delta",
                        "step": tool_used + 1,
                        "reasoning_step": state.get("last_reasoning_step", ""),
                        "delta": d,
                    }
                )

        raw = raw.strip()
        msg = _safe_parse_json(raw)
        if writer:
            writer(
                {
                    "type": "model_message",
                    "step": tool_used + 1,
                    "reasoning_step": state.get("last_reasoning_step", ""),
                    "raw": raw,
                    "parsed": msg,
                }
            )

        raw_messages_acc.append({"raw": raw, "parsed": msg})
        tool_used += 1
        updates["tool_used"] = tool_used

        msg_type = str(msg.get("type", "")).strip().lower()
        if msg_type == "final":
            fa = str(msg.get("final_answer", "")).strip() or raw
            if writer:
                writer({"type": "final", "final_answer": fa})
            updates["stream_final_answer"] = fa
            updates["stream_finished"] = True
            return {
                **updates,
                "raw_messages": raw_messages_acc,
                "history": history_acc,
                "steps": steps_acc,
            }

        if msg_type != "tool_call":
            break

        tool_name = str(msg.get("tool", "")).strip()
        args = msg.get("args")
        if not isinstance(args, dict):
            args = {}

        if writer:
            writer(
                {
                    "type": "tool_call",
                    "step": tool_used,
                    "reasoning_step": state.get("last_reasoning_step", ""),
                    "tool": tool_name,
                    "args": args,
                }
            )

        tool = agent.tools.get(tool_name)
        if not tool:
            err = {"role": "tool_error", "tool": tool_name, "error": f"Unknown tool: {tool_name}"}
            history_acc.append(err)
            if writer:
                writer(
                    {
                        "type": "tool_result",
                        "step": tool_used,
                        "reasoning_step": state.get("last_reasoning_step", ""),
                        "tool": tool_name,
                        "args": args,
                        "result": {"error": f"Unknown tool: {tool_name}"},
                    }
                )
            continue

        try:
            result = tool.fn(args)
        except Exception as e:  # pragma: no cover
            result = {"error": str(e)}

        history_acc.append({"role": "tool_result", "tool": tool_name, "args": args, "result": result})
        steps_acc.append({"tool": tool_name, "args": args, "result": result})

        if writer:
            writer(
                {
                    "type": "tool_result",
                    "step": tool_used,
                    "reasoning_step": state.get("last_reasoning_step", ""),
                    "tool": tool_name,
                    "args": args,
                    "result": result,
                }
            )

    return {
        **updates,
        "raw_messages": raw_messages_acc,
        "history": history_acc,
        "steps": steps_acc,
    }


def _finalize_stream_node(state: StreamGraphState) -> dict[str, Any]:
    writer = None
    try:
        writer = get_stream_writer()
    except Exception:
        writer = None

    fa = str(state.get("stream_final_answer", "") or "").strip()
    if not fa:
        fa = str(state.get("reasoning_final_answer", "") or "").strip()
    if writer:
        writer({"type": "final", "final_answer": fa or "(no answer)"})
    return {}


def _route_after_tool_stream(state: StreamGraphState) -> Literal["continue", "finalize", "done"]:
    if state.get("stream_finished"):
        return "done"
    if str(state.get("last_reasoning_next", "")).strip() == "final_answer":
        return "finalize"
    return "continue"


def _build_stream_graph(agent: "Agent"):
    g = StateGraph(StreamGraphState)
    g.add_node("next_reasoning", partial(_next_reasoning_stream_node, agent))
    g.add_node("tool_round", partial(_tool_round_stream_node, agent))
    g.add_node("finalize", _finalize_stream_node)

    g.add_edge(START, "next_reasoning")
    g.add_conditional_edges(
        "next_reasoning",
        _route_after_reasoning_stream,
        {"more_reasoning": "next_reasoning", "tool_round": "tool_round", "finalize": "finalize"},
    )
    g.add_conditional_edges(
        "tool_round",
        _route_after_tool_stream,
        {"continue": "next_reasoning", "finalize": "finalize", "done": END},
    )
    g.add_edge("finalize", END)
    return g.compile()


def _reasoning_from_run_state(state: RunGraphState) -> ReasoningResult:
    return ReasoningResult(
        problem_definition=str(state.get("problem_definition", "")),
        planning=str(state.get("planning", "")),
        analysis_and_design=str(state.get("analysis_and_design", "")),
        implementation=str(state.get("implementation", "")),
        testing=str(state.get("testing", "")),
        reporting=str(state.get("reporting", "")),
        final_answer=str(state.get("final_answer", "")),
        assumptions=list(state.get("assumptions", [])),
    )


@dataclass
class Agent:
    """
    Agent runtime backed by LangGraph:
    - run(): reasoning (full scaffold) then tool loop
    - stream(): incremental reasoning steps + tool loop with token streaming
    """

    provider: ReasoningProvider
    pipeline: ReasoningPipeline = field(default_factory=ReasoningPipeline)
    tools: Dict[str, Tool] = field(default_factory=dict)

    tool_system_prompt: str = TOOL_AGENT_SYSTEM_PROMPT
    tool_user_prompt_template: str = TOOL_AGENT_USER_PROMPT_TEMPLATE

    max_tool_steps: int = 10

    _compiled_run: Any = field(default=None, repr=False, init=False)
    _compiled_stream: Any = field(default=None, repr=False, init=False)

    def register_tool(self, tool: Tool) -> None:
        self.tools[tool.name] = tool
        self._compiled_run = None
        self._compiled_stream = None

    def _tools_json_str(self) -> str:
        return _json_dumps([t.to_json() for t in self.tools.values()])

    def _tools_datastring_str(self) -> str:
        return _tools_datastring_block(self.tools)

    def format_tool_user_prompt(self, *, task: str, reasoning_summary: str, history: List[JsonDict]) -> str:
        return self.tool_user_prompt_template.format(
            task=task.strip(),
            reasoning_summary=reasoning_summary,
            tools_json=self._tools_json_str(),
            tools_datastring=self._tools_datastring_str(),
            history_json=_json_dumps(history),
        )

    def get_compiled_run_graph(self):
        if self._compiled_run is None:
            self._compiled_run = _build_run_graph(self)
        return self._compiled_run

    def get_compiled_stream_graph(self):
        if self._compiled_stream is None:
            self._compiled_stream = _build_stream_graph(self)
        return self._compiled_stream

    def export_agent_flow_png(self, output_path: str = "agent_flow.png") -> str:
        """
        Render the run-time LangGraph (reasoning → model ↔ tools) to a PNG via Mermaid.
        """
        g = self.get_compiled_run_graph()
        g.get_graph().draw_mermaid_png(output_file_path=output_path)
        return output_path

    def run(
        self,
        task: str,
        *,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
    ) -> AgentRunResult:
        graph = self.get_compiled_run_graph()
        init: RunGraphState = {
            "task": task,
            "model": model,
            "reasoning_effort": reasoning_effort,
            "assumptions": [],
            "history": [],
            "steps": [],
            "raw_messages": [],
        }
        out = graph.invoke(init)

        msg = out.get("last_parsed") or {}
        msg_type = str(msg.get("type", "")).strip().lower()
        final_answer = str(out.get("final_answer", "")).strip()
        if msg_type == "final":
            fa = str(msg.get("final_answer", "")).strip()
            if fa:
                final_answer = fa

        steps_out: List[ToolStep] = []
        for s in out.get("steps", []) or []:
            if isinstance(s, dict) and "tool" in s:
                steps_out.append(
                    ToolStep(
                        tool=str(s.get("tool", "")),
                        args=s.get("args") if isinstance(s.get("args"), dict) else {},
                        result=s.get("result"),
                    )
                )

        return AgentRunResult(
            reasoning=_reasoning_from_run_state(out),
            final_answer=final_answer,
            steps=steps_out,
            raw_messages=list(out.get("raw_messages", []) or []),
        )

    def stream(
        self,
        task: str,
        *,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        max_tool_steps: Optional[int] = None,
    ) -> Iterable[JsonDict]:
        if not isinstance(self.provider, StreamingProvider):
            res = self.run(task, model=model, reasoning_effort=reasoning_effort)
            yield {"type": "final", "final_answer": res.final_answer}
            return

        tool_limit = int(max_tool_steps if max_tool_steps is not None else self.max_tool_steps)
        tool_limit = max(0, tool_limit)

        graph = self.get_compiled_stream_graph()
        init: StreamGraphState = {
            "task": task,
            "model": model,
            "reasoning_effort": reasoning_effort,
            "prev_reasoning_steps": [],
            "reasoning_current_step": "problem_definition",
            "reasoning_iterations": 0,
            "problem_definition": "",
            "planning": "",
            "analysis_and_design": "",
            "implementation": "",
            "testing": "",
            "reporting": "",
            "reasoning_final_answer": "",
            "last_reasoning_step": "",
            "last_reasoning_content": "",
            "last_reasoning_next": "",
            "assumptions": [],
            "history": [],
            "steps": [],
            "raw_messages": [],
            "tool_used": 0,
            "tool_limit": tool_limit,
            "stream_final_answer": "",
        }

        for chunk in graph.stream(
            init,
            stream_mode="custom",
        ):
            if isinstance(chunk, dict):
                yield chunk
