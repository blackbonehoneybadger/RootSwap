"""Persisted emergency stop via Redis (survives process restart)."""

from __future__ import annotations

import redis

from app.core.config import get_settings
from app.observability.logging import get_logger
from app.observability.metrics import EMERGENCY_STOP

logger = get_logger(__name__)

REDIS_KEY = "rootswap:emergency_stop"


def _client() -> redis.Redis:
    settings = get_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)


def is_emergency_stopped() -> bool:
    settings = get_settings()
    try:
        val = _client().get(REDIS_KEY)
        if val is not None:
            stopped = val in ("1", "true", "True")
            settings.emergency_stop = stopped
            return stopped
    except Exception as exc:
        logger.warning("emergency_stop_redis_read_failed", error=str(exc))
    return bool(settings.emergency_stop)


def set_emergency_stop(active: bool) -> bool:
    settings = get_settings()
    settings.emergency_stop = active
    EMERGENCY_STOP.set(1 if active else 0)
    try:
        _client().set(REDIS_KEY, "1" if active else "0")
    except Exception as exc:
        logger.warning("emergency_stop_redis_write_failed", error=str(exc))
    return active


def load_emergency_stop_on_startup() -> None:
    """Sync in-process flag from Redis at boot."""
    try:
        val = _client().get(REDIS_KEY)
        if val is not None:
            stopped = val in ("1", "true", "True")
            get_settings().emergency_stop = stopped
            EMERGENCY_STOP.set(1 if stopped else 0)
            logger.info("emergency_stop_loaded", active=stopped)
    except Exception as exc:
        logger.warning("emergency_stop_startup_load_failed", error=str(exc))
