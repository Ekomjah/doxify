from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

from .redaction import SAFE_LOG_FIELDS, redact_text, redact_value

LOGGER_NAME = "doxify"
_configured = False

logger = logging.getLogger(LOGGER_NAME)


class _RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.msg)
        if record.args:
            record.args = redact_value(record.args)
        fields = getattr(record, "doxify_fields", None)
        if isinstance(fields, dict):
            record.doxify_fields = {
                key: redact_value(value)
                for key, value in fields.items()
                if key in SAFE_LOG_FIELDS
            }
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "event": record.getMessage(),
            "logger": record.name,
        }
        fields = getattr(record, "doxify_fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info and record.exc_info[1] is not None:
            payload["exception"] = redact_text(record.exc_info[1])
        return json.dumps(payload, ensure_ascii=True, sort_keys=True)


class HumanFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = f"{record.levelname.lower():<8} {record.getMessage()}"
        fields = getattr(record, "doxify_fields", None)
        if isinstance(fields, dict) and fields:
            rendered = " ".join(f"{key}={value}" for key, value in fields.items())
            message = f"{message} {rendered}"
        return message


def configure_logging() -> None:
    global _configured
    if _configured:
        return

    raw_level = os.environ.get("DOXIFY_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, raw_level, logging.WARNING)
    json_output = os.environ.get("DOXIFY_LOG_FORMAT", "human").lower() == "json"

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter() if json_output else HumanFormatter())
    handler.addFilter(_RedactingFilter())

    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
    _configured = True


def reset_logging() -> None:
    global _configured
    logger.handlers = []
    logger.setLevel(logging.NOTSET)
    logger.propagate = True
    _configured = False


def log_event(level: int, event: str, **fields: Any) -> None:
    safe_fields = {
        key: redact_value(value)
        for key, value in fields.items()
        if key in SAFE_LOG_FIELDS
    }
    logger.log(level, event, extra={"doxify_fields": safe_fields})

    if level >= logging.WARNING:
        from .monitoring import capture_log

        capture_log(logging.getLevelName(level).lower(), event, safe_fields)
