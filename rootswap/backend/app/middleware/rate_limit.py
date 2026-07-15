import time

import redis.asyncio as redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.observability.logging import get_logger

logger = get_logger(__name__)


def client_ip(request: Request) -> str:
    settings = get_settings()
    peer = request.client.host if request.client else "unknown"
    trusted = settings.trusted_proxy_set
    if trusted and peer in trusted:
        # Prefer nginx X-Real-IP when the peer is a trusted proxy.
        real = request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for", "").split(",")[0]
        real = real.strip()
        if real:
            return real
    return peer


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.settings = get_settings()
        self._redis: redis.Redis | None = None

    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(self.settings.redis_url, decode_responses=True)
        return self._redis

    def _limit_for_path(self, path: str) -> int:
        if path.startswith("/api/v1/auth") or path.startswith("/api/v1/webhooks"):
            return self.settings.rate_limit_auth_per_minute
        return self.settings.rate_limit_per_minute

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path.startswith("/health") or request.url.path.startswith("/metrics"):
            return await call_next(request)
        ip = client_ip(request)
        limit = self._limit_for_path(request.url.path)
        bucket = int(time.time() // 60)
        key = f"ratelimit:{ip}:{request.url.path.split('/')[3] if request.url.path.startswith('/api') else 'other'}:{bucket}"
        try:
            r = await self._get_redis()
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, 60)
            if count > limit:
                return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        except Exception as exc:
            if self.settings.environment != "development":
                logger.error("rate_limit_redis_unavailable", error=str(exc))
                return JSONResponse(
                    {"detail": "Rate limiter unavailable"},
                    status_code=503,
                )
            logger.warning("rate_limit_fail_open_dev", error=str(exc))
        return await call_next(request)
