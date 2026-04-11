from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TARASettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    HOST: str = Field(default="127.0.0.1")
    PORT: int = Field(default=8000)
    ENVIRONMENT: Literal["development", "staging", "production"] | str = Field(default="development")


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

    # Storage
    DATABASE_URL: Optional[str] = Field(default=None)
    REDIS_URL: Optional[str] = Field(default=None)
    REDIS_REASONING_TTL_SECONDS: int = Field(default=30 * 60, ge=60, le=86400 * 7)
    REDIS_RUN_STATE_TTL_SECONDS: Optional[int] = Field(default=None, ge=60, le=86400 * 7)
    DATASTORE_FAIL_MODE: Literal["strict", "degraded"] = Field(default="degraded")

    # MCP (core calls MCP over HTTP/SSE)
    MCP_HOST: str = Field(default="127.0.0.1")
    MCP_PORT: int = Field(default=9000, ge=1, le=65535)
    MCP_BASE_URL: Optional[str] = Field(default=None)
    MCP_DEFAULT_TOOL_DELAY_MS: Optional[int] = Field(default=None, ge=0, le=3_600_000)

    @property
    def mcp_base_url(self) -> str:
        if self.MCP_BASE_URL and str(self.MCP_BASE_URL).strip():
            return str(self.MCP_BASE_URL).rstrip("/")
        return f"http://{self.MCP_HOST}:{self.MCP_PORT}"

    @classmethod
    def load(cls) -> "Env":
        global ENV
        ENV = cls()
        return ENV


ENV: Optional[Env] = None

__all__ = ["ENV", "Env", "TARASettings"]
