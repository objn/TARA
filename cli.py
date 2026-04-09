from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from core.configs.settings import Env
from core.services.agents.main import Agent
from core.services.agents.tools.calculator import calculator_tool
from core.services.provider.openai import provider

JsonDict = Dict[str, Any]


TARA_LOGO = r"""
████████╗ █████╗ ██████╗  █████╗
╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗
   ██║   ███████║██████╔╝███████║
   ██║   ██╔══██║██╔══██╗██╔══██║
   ██║   ██║  ██║██║  ██║██║  ██║
   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝
"""


HELP_TEXT = """\
Commands:
  /help        Show this help
  /exit        Quit
  /clear       Clear screen
  /new         Start a new chat (clears local history)
  /model       Set model (or empty to use default)
  /effort      Set reasoning_effort (or empty)
  /reasoning   Toggle showing reasoning
  /stream      Toggle streaming with tools (raw JSON stream)
"""


@dataclass
class ChatState:
    history: List[str] = field(default_factory=list)
    model: Optional[str] = None
    reasoning_effort: Optional[str] = None
    show_reasoning: bool = True
    stream: bool = False


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)


def _safe_parse_json(text: str) -> JsonDict:
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {"_value": obj}
    except Exception:
        return {}


def _reasoning_markdown(res) -> str:
    r = getattr(res, "reasoning", None)
    if r is None:
        return ""

    parts: List[str] = []
    mapping = [
        ("Problem definition", getattr(r, "problem_definition", "")),
        ("Planning", getattr(r, "planning", "")),
        ("Analysis & design", getattr(r, "analysis_and_design", "")),
        ("Implementation", getattr(r, "implementation", "")),
        ("Testing", getattr(r, "testing", "")),
        ("Reporting", getattr(r, "reporting", "")),
    ]
    for title, body in mapping:
        body = (body or "").strip()
        if body:
            parts.append(f"### {title}\n{body}")

    assumptions = getattr(r, "assumptions", None) or []
    if assumptions:
        lines = "\n".join([f"- {a}" for a in assumptions if str(a).strip()])
        if lines.strip():
            parts.append(f"### Assumptions\n{lines}")

    return "\n\n".join(parts).strip()


def _stream_text(console: Console, *, label: str, chunks) -> str:
    """
    Stream chunks as plain text (works in non-TTY consoles).
    Returns the full final text.
    """
    console.print(f"[cyan]{label}[/cyan] ", end="")
    buf = ""
    started = False
    for delta in chunks:
        if not delta:
            continue
        d = str(delta)
        if not started:
            started = True
        buf += d
        console.print(d, end="", markup=False, soft_wrap=True)
    console.print()  # newline
    return buf.strip()


def _agent_run_streaming_with_tools(
    console: Console,
    *,
    agent: Agent,
    task: str,
    model: Optional[str],
    reasoning_effort: Optional[str],
) -> tuple[str, Any]:
    """
    Streaming version of Agent.run():
    - runs the reasoning pipeline first (non-streaming)
    - then runs the tool-loop, but streams the model's raw JSON messages
    Returns (final_answer, AgentRunResult-like object).
    """
    # 1) Reasoning scaffold (non-streaming).
    reasoning = agent.pipeline.run(
        task,
        provider=agent.provider,
        model=model,
        reasoning_effort=reasoning_effort,
    )

    # 2) Tool loop with streaming provider output.
    history: List[JsonDict] = []
    steps: List[JsonDict] = []
    raw_messages: List[JsonDict] = []

    reasoning_summary = _json_dumps(
        {
            "problem_definition": reasoning.problem_definition,
            "planning": reasoning.planning,
            "analysis_and_design": reasoning.analysis_and_design,
        }
    )
    tools_json = _json_dumps([t.to_json() for t in agent.tools.values()])
    final_answer = reasoning.final_answer.strip()

    for i in range(max(0, int(agent.max_tool_steps))):
        prompt = agent.tool_user_prompt_template.format(
            task=task.strip(),
            reasoning_summary=reasoning_summary,
            tools_json=tools_json,
            history_json=_json_dumps(history),
        )

        console.print(f"[dim]step {i + 1}/{agent.max_tool_steps}[/dim]")
        chunks = agent.provider.stream_text(
            prompt,
            system=agent.tool_system_prompt,
            model=model,
            reasoning=True,
            reasoning_effort=reasoning_effort,
        )
        raw = _stream_text(console, label="TARA(stream)", chunks=chunks)

        msg = _safe_parse_json(raw)
        raw_messages.append({"raw": raw, "parsed": msg})

        msg_type = str(msg.get("type", "")).strip().lower()
        if msg_type == "final":
            fa = str(msg.get("final_answer", "")).strip()
            if fa:
                final_answer = fa
            break

        if msg_type != "tool_call":
            # Fallback: treat raw stream as a final answer.
            if raw.strip():
                final_answer = raw.strip()
            break

        tool_name = str(msg.get("tool", "")).strip()
        args = msg.get("args")
        if not isinstance(args, dict):
            args = {}

        tool = agent.tools.get(tool_name)
        if not tool:
            history.append({"role": "tool_error", "tool": tool_name, "error": f"Unknown tool: {tool_name}"})
            console.print(f"[red]Unknown tool:[/red] {tool_name}")
            continue

        console.print(f"[yellow]tool_call[/yellow] {tool_name}({_json_dumps(args)})", soft_wrap=True)
        try:
            result = tool.fn(args)
        except Exception as e:  # pragma: no cover
            result = {"error": str(e)}

        steps.append({"tool": tool_name, "args": args, "result": result})
        history.append({"role": "tool_result", "tool": tool_name, "args": args, "result": result})
        console.print(Panel(Markdown(f"```json\n{_json_dumps(result)}\n```"), title="tool_result", border_style="yellow"))

    # Create a lightweight result object compatible with _reasoning_markdown usage.
    res = type("AgentRunResultLite", (), {})()
    res.reasoning = reasoning
    res.final_answer = final_answer
    res.steps = steps
    res.raw_messages = raw_messages
    return final_answer, res


def _clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _render_header(console: Console) -> None:
    title = Text("TARA CLI", style="bold")
    subtitle = Text("Agent chat (Rich console)", style="dim")
    logo = Text(TARA_LOGO, style="bold cyan")
    console.print(Panel.fit(logo, title=title, subtitle=subtitle, border_style="cyan"))


def _build_agent() -> Agent:
    a = Agent(provider=provider)
    a.register_tool(calculator_tool())
    a.max_tool_steps = 10
    return a


def _compose_task(user_text: str, state: ChatState) -> str:
    user_text = (user_text or "").strip()
    if not state.history:
        return user_text
    context = "\n".join(state.history[-30:]).strip()
    return f"{user_text}\n\n[chat_context]\n{context}"


def _handle_command(cmd: str, *, console: Console, state: ChatState) -> bool:
    c = cmd.strip()

    if c == "/help":
        console.print(Panel(HELP_TEXT, title="Help", border_style="green"))
        return True
    if c == "/exit":
        raise SystemExit(0)
    if c == "/clear":
        _clear_screen()
        _render_header(console)
        return True
    if c == "/new":
        state.history.clear()
        console.print("[green]Started a new chat.[/green]")
        return True
    if c == "/model":
        v = Prompt.ask("Model (empty = default)", default=state.model or "")
        v = v.strip()
        state.model = v or None
        console.print(f"[green]model = {state.model!r}[/green]")
        return True
    if c == "/effort":
        v = Prompt.ask("reasoning_effort (empty = default)", default=state.reasoning_effort or "")
        v = v.strip()
        state.reasoning_effort = v or None
        console.print(f"[green]reasoning_effort = {state.reasoning_effort!r}[/green]")
        return True
    if c == "/reasoning":
        state.show_reasoning = not state.show_reasoning
        console.print(f"[green]show_reasoning = {state.show_reasoning!r}[/green]")
        return True
    if c == "/stream":
        state.stream = not state.stream
        console.print(f"[green]stream = {state.stream!r}[/green]")
        return True

    return False


def run() -> int:
    # Ensure env is loaded early (so missing keys fail fast).
    Env.load()

    # In some terminals (incl. some IDE-integrated consoles), Rich may not detect an interactive TTY.
    # For streaming (Live) output we force interactive terminal mode.
    console = Console(force_terminal=True, force_interactive=True, color_system="truecolor")
    _clear_screen()
    _render_header(console)
    console.print("[dim]Tip: if you're not sure what to do, type /help[/dim]")

    agent = _build_agent()
    state = ChatState()

    while True:
        try:
            text = Prompt.ask("[bold]You[/bold]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]bye[/dim]")
            return 0

        if not text:
            continue
        if text.startswith("/"):
            try:
                if _handle_command(text, console=console, state=state):
                    continue
            except SystemExit:
                console.print("[dim]bye[/dim]")
                return 0

        task = _compose_task(text, state)
        if state.stream:
            console.print("[dim]Thinking... (stream+tools)[/dim]")
            # 1) Get reasoning first, show it immediately.
            # 2) Stream step-by-step tool loop (raw JSON deltas).
            answer = ""
            res = type("AgentRunResultLite", (), {})()
            res.reasoning = None
            for ev in agent.stream(task, model=state.model, reasoning_effort=state.reasoning_effort, max_tool_steps=10):
                t = str(ev.get("type", ""))
                if t == "reasoning_step":
                    step = str(ev.get("step", "")).strip()
                    content = str(ev.get("content", "")).strip()
                    next_step = str(ev.get("next_step", "")).strip()

                    if res.reasoning is None:
                        res.reasoning = type("ReasoningLite", (), {})()

                    if step == "problem_definition":
                        setattr(res.reasoning, "problem_definition", content)
                    elif step == "planning":
                        setattr(res.reasoning, "planning", content)
                    elif step == "analysis_and_design":
                        setattr(res.reasoning, "analysis_and_design", content)
                    elif step == "implementation":
                        setattr(res.reasoning, "implementation", content)
                    elif step == "testing":
                        setattr(res.reasoning, "testing", content)
                    elif step == "reporting":
                        setattr(res.reasoning, "reporting", content)
                    elif step == "final_answer":
                        setattr(res.reasoning, "final_answer", content)

                    if state.show_reasoning:
                        title = f"Reasoning: {step} → {next_step or '?'}"
                        console.print(Panel(Markdown(content or ""), title=title, border_style="magenta"))
                    continue

                if t == "step_start":
                    console.print(
                        f"[dim]tool_step {ev.get('step')}/{ev.get('max_tool_steps')} (reasoning={ev.get('reasoning_step')})[/dim]",
                        soft_wrap=True,
                    )
                    continue

                if t == "model_delta":
                    # Show JSON stream as plain text (no panels).
                    console.print(str(ev.get("delta", "")), end="", markup=False, soft_wrap=True)
                    continue

                if t == "model_message":
                    console.print()  # newline after streamed JSON
                    continue

                if t == "tool_call":
                    console.print(
                        f"[yellow]tool_call[/yellow] {ev.get('tool')}({_json_dumps(ev.get('args') or {})}) [dim](reasoning={ev.get('reasoning_step')})[/dim]",
                        soft_wrap=True,
                    )
                    continue

                if t == "tool_result":
                    console.print(
                        Panel(
                            Markdown(f"```json\n{_json_dumps(ev.get('result'))}\n```"),
                            title="tool_result",
                            border_style="yellow",
                        )
                    )
                    continue

                if t == "final":
                    answer = str(ev.get("final_answer", "") or "").strip()
                    break

            if not answer:
                answer = "(no answer)"
        else:
            with console.status("[cyan]Thinking...[/cyan]"):
                res = agent.run(task, model=state.model, reasoning_effort=state.reasoning_effort)

            answer = (res.final_answer or "").strip()
            if not answer:
                answer = "(no answer)"

        state.history.append(f"user: {text}")
        state.history.append(f"assistant: {answer}")

        # Show final result after reasoning.
        if (not state.stream) and state.show_reasoning and res is not None:
            md = _reasoning_markdown(res)
            if md:
                console.print(Panel(Markdown(md), title="Reasoning", border_style="magenta"))
        console.print(Panel(Markdown(answer), title="TARA", border_style="cyan"))


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tara", description="TARA CLI (Agent chat)")
    p.add_argument("--no-clear", action="store_true", help="Do not clear the screen on start.")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    _ = _build_parser().parse_args(argv)
    # Note: --no-clear is intentionally ignored for now (kept for future UX tweaks).
    return run()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
