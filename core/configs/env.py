from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Env(BaseSettings):
    """
    Environment configuration loaded from `.env`.

    Kept intentionally small and import-friendly; other modules can call `Env.load()`
    and/or reuse the global `ENV` cache.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    ENVIRONMENT: Literal["development", "staging", "production"] | str = Field(default="development")

    # OpenAI
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    OPENAI_MODEL_TEXT: str = Field(default="gpt-4.1-mini")
    OPENAI_MODEL_VISION: str = Field(default="gpt-4.1-mini")
    OPENAI_REASONING_MODEL: str = Field(default="gpt-4.1-mini")
    OPENAI_REASONING_EFFORT: Optional[str] = Field(default=None)

    @classmethod
    def load(cls) -> "Env":
        global ENV
        ENV = cls()
        return ENV


# Optional cache to avoid re-parsing `.env` on every call.
ENV: Optional[Env] = None

