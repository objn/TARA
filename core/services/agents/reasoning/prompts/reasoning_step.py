from __future__ import annotations

from core.services.agents.reasoning.prompts._shared import JSON_OUTPUT_RULES, TARA_AGENT_IDENTITY

REASONING_STEP_SYSTEM_PROMPT = f"""\
{TARA_AGENT_IDENTITY}

You will output ONE reasoning step at a time.

{JSON_OUTPUT_RULES}
Do not reveal hidden chain-of-thought; provide concise, user-visible reasoning notes only.
"""

REASONING_STEP_USER_PROMPT_TEMPLATE = """\
You will help with a software engineering task by producing reasoning steps incrementally.

Task:
{task}

Current step: {current_step}
Previous steps (JSON):
{previous_steps_json}

Allowed steps (in typical order):
- problem_definition
- explore
- planning
- analysis_and_design
- implementation
- testing
- reporting
- final_answer

Requirements:
- Output ONLY ONE step for the given current_step.
- You may jump to ANY next_step that is most appropriate (you can skip steps and you don't need to follow the typical order).
- Include where to jump next via next_step (must be one of allowed steps, or "final_answer" to end).
- Keep content concise; short bullet points in plain text are OK.

Output JSON schema:
{{
  "step": string,
  "content": string,
  "next_step": string,
  "assumptions": [string]
}}
"""
