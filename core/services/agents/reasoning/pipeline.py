from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from core.services.agents.reasoning.prompts import (
    REASONING_SYSTEM_PROMPT,
    REASONING_STEP_SYSTEM_PROMPT,
    REASONING_STEP_USER_PROMPT_TEMPLATE,
    REASONING_USER_PROMPT_TEMPLATE,
)


@runtime_checkable
class ReasoningProvider(Protocol):
    """
    Minimal provider interface expected by the reasoning pipeline.

    Any provider can be used as long as it implements `invoke_text()` with a compatible signature.
    """

    def invoke_text(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        model: Optional[str] = None,
        reasoning: bool = False,
        reasoning_effort: Optional[str] = None,
    ) -> str: ...


@dataclass
class ReasoningResult:
    problem_definition: str = ""
    planning: str = ""
    analysis_and_design: str = ""
    implementation: str = ""
    testing: str = ""
    reporting: str = ""
    final_answer: str = ""
    assumptions: list[str] = field(default_factory=list)

    raw_text: str = ""
    raw_json: Dict[str, Any] = field(default_factory=dict)


def _coerce_list_of_str(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    s = str(v).strip()
    return [s] if s else []


def _safe_parse_json(text: str) -> Dict[str, Any]:
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
        return {"_value": obj}
    except Exception:
        return {}


@dataclass
class ReasoningPipeline:
    """
    Provider-agnostic reasoning pipeline.

    It requests a structured JSON response so downstream code can parse it reliably.
    Prompts are stored in `core/services/agents/reasoning/prompts.py` (English-only).
    """

    system_prompt: str = REASONING_SYSTEM_PROMPT
    user_prompt_template: str = REASONING_USER_PROMPT_TEMPLATE
    step_system_prompt: str = REASONING_STEP_SYSTEM_PROMPT
    step_user_prompt_template: str = REASONING_STEP_USER_PROMPT_TEMPLATE

    def run(
        self,
        task: str,
        *,
        provider: ReasoningProvider,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        system: Optional[str] = None,
    ) -> ReasoningResult:
        prompt = self.user_prompt_template.format(task=task.strip())
        sys_prompt = system or self.system_prompt

        # Providers may differ slightly; prefer reasoning=True when supported.
        try:
            text = provider.invoke_text(
                prompt,
                system=sys_prompt,
                model=model,
                reasoning=True,
                reasoning_effort=reasoning_effort,
            )
        except TypeError:
            text = provider.invoke_text(prompt, system=sys_prompt, model=model)

        text = (text or "").strip()
        data = _safe_parse_json(text)

        return ReasoningResult(
            problem_definition=str(data.get("problem_definition", "")).strip(),
            planning=str(data.get("planning", "")).strip(),
            analysis_and_design=str(data.get("analysis_and_design", "")).strip(),
            implementation=str(data.get("implementation", "")).strip(),
            testing=str(data.get("testing", "")).strip(),
            reporting=str(data.get("reporting", "")).strip(),
            final_answer=str(data.get("final_answer", "")).strip(),
            assumptions=_coerce_list_of_str(data.get("assumptions")),
            raw_text=text,
            raw_json=data,
        )

    def stream_steps(
        self,
        task: str,
        *,
        provider: ReasoningProvider,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        system: Optional[str] = None,
        start_step: str = "problem_definition",
        max_steps: int = 12,
    ):
        """
        Yield reasoning steps incrementally.

        Each yielded item is a dict:
          { "step": str, "content": str, "next_step": str, "assumptions": [str] }

        The model is responsible for selecting next_step so it can "jump" as needed.
        """
        max_steps = max(1, int(max_steps))
        current = (start_step or "problem_definition").strip() or "problem_definition"
        sys_prompt = system or self.step_system_prompt

        prev: list[dict[str, Any]] = []
        assumptions: list[str] = []

        for _ in range(max_steps):
            prompt = self.step_user_prompt_template.format(
                task=task.strip(),
                current_step=current,
                previous_steps_json=json.dumps(prev, ensure_ascii=False, separators=(",", ":"), default=str),
            )

            try:
                text = provider.invoke_text(
                    prompt,
                    system=sys_prompt,
                    model=model,
                    reasoning=True,
                    reasoning_effort=reasoning_effort,
                )
            except TypeError:
                text = provider.invoke_text(prompt, system=sys_prompt, model=model)

            text = (text or "").strip()
            data = _safe_parse_json(text)

            step = str(data.get("step") or current).strip() or current
            content = str(data.get("content") or "").strip()
            next_step = str(data.get("next_step") or "final_answer").strip() or "final_answer"

            step_assumptions = _coerce_list_of_str(data.get("assumptions"))
            if step_assumptions:
                assumptions.extend(step_assumptions)

            out = {
                "step": step,
                "content": content,
                "next_step": next_step,
                "assumptions": step_assumptions,
            }
            prev.append({"step": step, "content": content})
            yield out

            if next_step == "final_answer":
                break
            current = next_step

    def stream_one_step(
        self,
        task: str,
        *,
        provider: ReasoningProvider,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        system: Optional[str] = None,
        current_step: str,
        previous_steps: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Run exactly one reasoning-step LLM call (same contract as one yield of stream_steps).
        Caller is responsible for appending to previous_steps and advancing current_step.
        """
        current = (current_step or "problem_definition").strip() or "problem_definition"
        sys_prompt = system or self.step_system_prompt
        prompt = self.step_user_prompt_template.format(
            task=task.strip(),
            current_step=current,
            previous_steps_json=json.dumps(previous_steps, ensure_ascii=False, separators=(",", ":"), default=str),
        )

        try:
            text = provider.invoke_text(
                prompt,
                system=sys_prompt,
                model=model,
                reasoning=True,
                reasoning_effort=reasoning_effort,
            )
        except TypeError:
            text = provider.invoke_text(prompt, system=sys_prompt, model=model)

        text = (text or "").strip()
        data = _safe_parse_json(text)

        step = str(data.get("step") or current).strip() or current
        content = str(data.get("content") or "").strip()
        next_step = str(data.get("next_step") or "final_answer").strip() or "final_answer"
        step_assumptions = _coerce_list_of_str(data.get("assumptions"))

        return {
            "step": step,
            "content": content,
            "next_step": next_step,
            "assumptions": step_assumptions,
            "raw_text": text,
        }


# Import-friendly default instance
pipeline = ReasoningPipeline()