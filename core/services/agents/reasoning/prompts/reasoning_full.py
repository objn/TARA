from __future__ import annotations

from core.services.agents.reasoning.prompts._shared import JSON_OUTPUT_RULES, TARA_AGENT_IDENTITY

REASONING_SYSTEM_PROMPT = f"""\
{TARA_AGENT_IDENTITY}

{JSON_OUTPUT_RULES}
"""

REASONING_USER_PROMPT_TEMPLATE = """\
You will help with a software engineering task.

Task:
{task}

Requirements:
- Follow this workflow: Problem Definition, Planning, Analyze & Design, Implement, Testing, Reporting.
- Use short bullet points for each section (max 8 bullets per section).
- If code is needed, include it as plain strings inside JSON fields (no Markdown).

Output JSON schema:
{{
  "problem_definition": string,
  "planning": string,
  "analysis_and_design": string,
  "implementation": string,
  "testing": string,
  "reporting": string,
  "final_answer": string,
  "assumptions": [string]
}}
"""
