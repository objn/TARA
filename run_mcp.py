from __future__ import annotations

import uvicorn

from mcp.configs.settings import MCPSettings


def main() -> None:
    settings = MCPSettings()
    uvicorn.run(
        "mcp.main:app",
        host=settings.MCP_HOST,
        port=settings.MCP_PORT,
        reload=True,
        reload_delay=1.0,
    )


if __name__ == "__main__":
    main()
