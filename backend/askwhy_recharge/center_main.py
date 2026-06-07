"""AskWhy 充值服务入口（独立进程）。"""

from __future__ import annotations

import logging

import uvicorn

from .app import create_app
from .settings import load_askwhy_settings


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = load_askwhy_settings()
    app = create_app()
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
