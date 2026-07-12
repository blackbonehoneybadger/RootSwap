"""Structured JSON logging with sensitive-data masking."""

import json
import logging
import sys
from datetime import UTC, datetime

from app.security.masking import mask_mapping

_request_id_getter = lambda: None  # noqa: E731 - replaced by middleware module


def set_request_id_getter(getter) -> None:
    global _request_id_getter
    _request_id_getter = getter


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = _request_id_getter()
        if request_id:
            payload["request_id"] = request_id
        extra = getattr(record, "ctx", None)
        if isinstance(extra, dict):
            payload.update(mask_mapping(extra))
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


def log_ctx(logger: logging.Logger, level: int, message: str, **ctx) -> None:
    """Log with a masked structured context dict."""
    logger.log(level, message, extra={"ctx": ctx})
