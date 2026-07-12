import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.orders import router as orders_router
from app.api.v1.quotes import router as quotes_router
from app.api.v1.referral import router as referral_router
from app.api.v1.webhooks import router as webhooks_router
from app.core.config import get_settings
from app.core.errors import DomainError
from app.db.session import get_session_factory
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.observability.logging import configure_logging
from app.partners.mock_crypto import MockCryptoPartnerAdapter
from app.partners.mock_fiat import MockFiatPartnerAdapter
from app.partners.registry import registry
from app.services.polling import run_polling_loop

logger = logging.getLogger(__name__)


def register_default_partners() -> None:
    settings = get_settings()
    if settings.allow_mock_partners and not settings.is_production:
        if registry.get_adapter("mock_fiat_alpha") is None:
            registry.register_adapter(MockFiatPartnerAdapter())
        if registry.get_adapter("mock_fiat_beta") is None:
            from decimal import Decimal

            registry.register_adapter(
                MockFiatPartnerAdapter(
                    code="mock_fiat_beta",
                    name="Mock Fiat Beta",
                    fee_percent=Decimal("0.6"),
                    latency_score_minutes=8,
                )
            )
        if registry.get_adapter("mock_crypto") is None:
            registry.register_adapter(MockCryptoPartnerAdapter())


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)

    problems = settings.validate_for_production()
    if problems:
        for problem in problems:
            logger.critical("production startup blocker: %s", problem)
        raise RuntimeError(
            "refusing to start in production with unsafe configuration: "
            + "; ".join(problems)
        )

    register_default_partners()
    session_factory = get_session_factory()
    async with session_factory() as session:
        await registry.sync_partner_rows(session)

    polling_task: asyncio.Task | None = None
    if settings.polling_enabled:
        polling_task = asyncio.create_task(run_polling_loop(session_factory))

    logger.info(
        "rootswap backend started",
        extra={"ctx": {"environment": settings.environment}},
    )
    yield

    if polling_task:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="RootSwap API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
    )

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
    )

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError):
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": exc.code, "message": exc.message, "details": exc.details},
        )

    prefix = settings.api_v1_prefix
    app.include_router(health_router)
    app.include_router(auth_router, prefix=prefix)
    app.include_router(quotes_router, prefix=prefix)
    app.include_router(orders_router, prefix=prefix)
    app.include_router(referral_router, prefix=prefix)
    app.include_router(webhooks_router, prefix=prefix)
    app.include_router(admin_router, prefix=prefix)
    return app


app = create_app()
