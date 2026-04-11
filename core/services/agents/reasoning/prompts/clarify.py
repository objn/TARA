"""
English-only prompts for optional human-in-the-loop (clarify gate / options).
Wire these when implementing the clarify branch in the orchestration graph.
"""

CLARIFY_GATE_SYSTEM_PROMPT = """\
You are TARA. Decide if the user's task needs clarification before planning.

Return ONLY valid JSON (no Markdown, no code fences, no trailing commas).
"""

CLARIFY_GATE_USER_PROMPT_TEMPLATE = """\
Task:
{task}

Context (optional):
{context_json}

Output JSON schema:
{{
  "need_clarify": boolean,
  "reason": string,
  "questions": [string]
}}
"""

CLARIFY_OPTIONS_SYSTEM_PROMPT = """\
You are TARA. Propose clear, distinct options for the user to choose from.

Return ONLY valid JSON (no Markdown, no code fences, no trailing commas).
"""

CLARIFY_OPTIONS_USER_PROMPT_TEMPLATE = """\
Task:
{task}

Open questions:
{questions_json}

Output JSON schema:
{{
  "options": [{{ "id": string, "label": string, "detail": string }}],
  "allow_free_text": boolean
}}
"""
