"""
English-only prompt templates for the reasoning and tool loops.

Edit submodules under this package to tune one concern at a time.
"""

from core.services.agents.reasoning.prompts.clarify import (
    CLARIFY_GATE_SYSTEM_PROMPT,
    CLARIFY_GATE_USER_PROMPT_TEMPLATE,
    CLARIFY_OPTIONS_SYSTEM_PROMPT,
    CLARIFY_OPTIONS_USER_PROMPT_TEMPLATE,
)
from core.services.agents.reasoning.prompts.reasoning_full import (
    REASONING_SYSTEM_PROMPT,
    REASONING_USER_PROMPT_TEMPLATE,
)
from core.services.agents.reasoning.prompts.reasoning_step import (
    REASONING_STEP_SYSTEM_PROMPT,
    REASONING_STEP_USER_PROMPT_TEMPLATE,
)
from core.services.agents.reasoning.prompts.tool_agent import (
    TOOL_AGENT_SYSTEM_PROMPT,
    TOOL_AGENT_USER_PROMPT_TEMPLATE,
)

__all__ = [
    "CLARIFY_GATE_SYSTEM_PROMPT",
    "CLARIFY_GATE_USER_PROMPT_TEMPLATE",
    "CLARIFY_OPTIONS_SYSTEM_PROMPT",
    "CLARIFY_OPTIONS_USER_PROMPT_TEMPLATE",
    "REASONING_STEP_SYSTEM_PROMPT",
    "REASONING_STEP_USER_PROMPT_TEMPLATE",
    "REASONING_SYSTEM_PROMPT",
    "REASONING_USER_PROMPT_TEMPLATE",
    "TOOL_AGENT_SYSTEM_PROMPT",
    "TOOL_AGENT_USER_PROMPT_TEMPLATE",
]
