"""
Structured JSON Logging
───────────────────────
Uses python-json-logger for machine-parseable structured logs.

Why JSON logs?
- Easy to ingest into ELK / CloudWatch / Datadog in production
- Extra fields (enquiry_id, event type) are first-class citizens
- Consistent format across all modules
"""

import logging
import sys
from pathlib import Path

from pythonjsonlogger import jsonlogger
from src.config import settings

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def _create_formatter() -> jsonlogger.JsonFormatter:
    return jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )


def get_logger(name: str = "closira") -> logging.Logger:
    log = logging.getLogger(name)
    log.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    if log.handlers:
        return log

    fmt = _create_formatter()

    # Console
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    log.addHandler(console)

    # File — all events
    file_handler = logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    log.addHandler(file_handler)

    # File — errors only
    err_handler = logging.FileHandler(LOG_DIR / "error.log", encoding="utf-8")
    err_handler.setFormatter(fmt)
    err_handler.setLevel(logging.ERROR)
    log.addHandler(err_handler)

    return log


logger = get_logger()
