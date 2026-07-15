import time

import redis.asyncio as redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.observability.logging import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.settings = get_settings()
        self._redis: redis.Redis | None = None

    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(self.settings.redis_url, decode_responses=True)
        return self._redis

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path.startswith("/health") or request.url.path.startswith("/metrics"):
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{client_ip}:{int(time.time() // 60)}"
        try:
            r = await self._get_redis()
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, 60)
            if count > self.settings.rate_limit_per_minute:
                return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        except Exception as exc:
            # Fail closed outside development — refuse traffic without rate limiter.
            if self.settings.environment != "development":
                logger.error("rate_limit_redis_unavailable", error=str(exc))
                return JSONResponse(
                    {"detail": "Rate limiter unavailable"},
                    status_code=503,
                )
            logger.warning("rate_limit_fail_open_dev", error=str(exc))
        return await call_next(request)
