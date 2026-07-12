"""Fixed-window rate limiting backed by Redis, with an in-memory fallback for
dev/test when Redis is unreachable.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import get_settings

try:
    import redis.asyncio as aioredis
except ImportError:  # pragma: no cover
    aioredis = None

_memory_buckets: dict[str, tuple[int, float]] = {}

EXEMPT_PATHS = {"/health", "/health/ready", "/metrics"}


class RateLimiter:
    def __init__(self) -> None:
        self._redis = None
        self._redis_failed = False

    async def _get_redis(self):
        if self._redis_failed or aioredis is None:
            return None
        if self._redis is None:
            settings = get_settings()
            try:
                self._redis = aioredis.from_url(
                    settings.redis_url,
                    password=settings.redis_password or None,
                    socket_connect_timeout=1,
                )
                await self._redis.ping()
            except Exception:
                self._redis = None
                self._redis_failed = True
        return self._redis

    async def is_allowed(self, subject: str) -> bool:
        settings = get_settings()
        window = settings.rate_limit_window_seconds
        limit = settings.rate_limit_requests
        bucket = f"rl:{subject}:{int(time.time()) // window}"

        redis = await self._get_redis()
        if redis is not None:
            try:
                count = await redis.incr(bucket)
                if count == 1:
                    await redis.expire(bucket, window)
                return count <= limit
            except Exception:
                self._redis_failed = True

        # In-memory fallback (single-process only)
        now = time.time()
        count, started = _memory_buckets.get(bucket, (0, now))
        if now - started > window:
            count, started = 0, now
        count += 1
        _memory_buckets[bucket] = (count, started)
        if len(_memory_buckets) > 10000:
            _memory_buckets.clear()
        return count <= limit


rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if not settings.rate_limit_enabled or request.url.path in EXEMPT_PATHS:
            return await call_next(request)
        subject = request.client.host if request.client else "unknown"
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer ") and len(auth) > 24:
            subject = f"tok:{auth[-24:]}"
        if not await rate_limiter.is_allowed(subject):
            return JSONResponse(
                status_code=429,
                content={"error": "rate_limited", "message": "Too many requests"},
            )
        return await call_next(request)
