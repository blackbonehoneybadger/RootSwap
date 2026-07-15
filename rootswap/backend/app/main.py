import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from app.api.admin_routes import router as admin_router
from app.api.routes import router as api_router
from app.api.webhook_routes import router as webhook_router
from app.core.config import get_settings
from app.db.session import engine
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.observability.logging import configure_logging, get_logger
from app.observability.metrics import metrics_response
from app.services.emergency_stop import load_emergency_stop_on_startup
from app.services.polling_worker import PollingWorker

settings = get_settings()
configure_logging(settings.debug)
logger = get_logger(__name__)
polling_worker = PollingWorker()


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_emergency_stop_on_startup()
    task = asyncio.create_task(polling_worker.run())
    logger.info("app_started", environment=settings.environment)
    yield
    polling_worker.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="RootSwap API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(RateLimitMiddleware)

app.include_router(api_router)
app.include_router(admin_router)
app.include_router(webhook_router)


@app.get("/health")
async def health():
    """Liveness — process is up. Prefer /health/ready for traffic routing."""
    return {"status": "ok", "environment": settings.environment}


@app.get("/health/ready")
async def health_ready():
    """Readiness — DB + Redis must answer or return 503."""
    errors: list[str] = []
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        errors.append(f"database: {exc}")

    try:
        import redis as sync_redis

        client = sync_redis.from_url(settings.redis_url, decode_responses=True)
        if client.ping() is not True:
            errors.append("redis: ping failed")
    except Exception as exc:
        errors.append(f"redis: {exc}")

    if errors:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "errors": errors},
        )
    return {"status": "ready"}


@app.get("/metrics")
async def metrics():
    return Response(content=metrics_response(), media_type="text/plain")
