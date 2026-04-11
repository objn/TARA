from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MCPSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    MCP_HOST: str = Field(default="127.0.0.1")
    MCP_PORT: int = Field(default=9000)
    MCP_DEFAULT_TOOL_DELAY_MS: int = Field(default=0, ge=0, le=3_600_000)

    @property
    def base_url(self) -> str:
        return f"http://{self.MCP_HOST}:{self.MCP_PORT}"
