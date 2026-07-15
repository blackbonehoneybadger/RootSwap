import logging
import re
from typing import Any

import structlog

_SENSITIVE_KEY = re.compile(
    r"(password|secret|token|authorization|cookie|api[_-]?key|init_data|encrypted|private|jwt)",
    re.I,
)


def _redact_value(key: str, value: Any) -> Any:
    if _SENSITIVE_KEY.search(key):
        return "***"
    if isinstance(value, dict):
        return {k: _redact_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(key, v) for v in value]
    return value


def scrub_event_dict(_logger: Any, _method: str, event_dict: dict) -> dict:
    return {k: _redact_value(k, v) for k, v in event_dict.items()}


def configure_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            scrub_event_dict,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def get_logger(name: str) -> Any:
    return structlog.get_logger(name)
