"""
Pipeline logging utility.

Adds a structured JSON FileHandler to the root logger so every pipeline
script automatically writes machine-readable logs to the shared datastore
at /Library/Assets/logs/pipeline/.  Avocet ingests these for Turnstone
logreading training (kiwi#141 / avocet#67).

Usage (add near the top of main() after logging.basicConfig):

    from scripts.pipeline.log_utils import attach_pipeline_log
    attach_pipeline_log("scrape_recipes")
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

PIPELINE_LOG_DIR = Path(
    os.environ.get("PIPELINE_LOG_DIR", "/Library/Assets/logs/pipeline")
)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Any extra kwargs passed via logger.info("...", extra={...})
        standard = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
            "taskName",
        }
        extra = {k: v for k, v in record.__dict__.items() if k not in standard}
        if extra:
            payload["extra"] = extra
        return json.dumps(payload)


def attach_pipeline_log(script_name: str) -> Path:
    """Attach a JSON file handler to the root logger for pipeline logging.

    Returns the path of the log file created.
    """
    PIPELINE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
    log_path = PIPELINE_LOG_DIR / f"{script_name}_{ts}.jsonl"

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(_JsonFormatter())
    logging.getLogger().addHandler(handler)

    logging.getLogger(__name__).info(
        "Pipeline log: %s", log_path, extra={"script": script_name}
    )
    return log_path
