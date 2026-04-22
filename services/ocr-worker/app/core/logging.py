from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

