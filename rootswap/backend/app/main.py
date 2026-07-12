import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
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
from app.services.polling_worker import PollingWorker

settings = get_settings()
configure_logging(settings.debug)
logger = get_logger(__name__)
polling_worker = PollingWorker()


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    return {"status": "ok", "environment": settings.environment}


@app.get("/health/ready")
async def health_ready():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        return {"status": "not_ready", "error": str(exc)}


@app.get("/metrics")
async def metrics():
    return Response(content=metrics_response(), media_type="text/plain")
