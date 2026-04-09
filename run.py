from __future__ import annotations

import uvicorn

from core.configs.settings import TARASettings


def main() -> None:
    settings = TARASettings()
    uvicorn.run(
        "core.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        reload_delay=1.0,
    )


if __name__ == "__main__":
    main()