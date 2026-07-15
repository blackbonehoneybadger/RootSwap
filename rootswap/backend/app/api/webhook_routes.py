from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import domain_error_handler
from app.core.config import get_settings
from app.core.exceptions import DomainError
from app.db.session import get_db
from app.services.webhook import WebhookService

router = APIRouter(prefix="/api/v1/webhooks")


@router.post("/partners/{partner_code}")
async def partner_webhook(
    partner_code: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    payload = await request.body()
    if len(payload) > settings.max_request_body_bytes:
        raise HTTPException(status_code=413, detail="Request body too large")
    headers = {k: v for k, v in request.headers.items()}
    # Never echo payload into logs — WebhookService uses hashes only.
    service = WebhookService()
    try:
        result = await service.process_webhook(session, partner_code, payload, headers)
    except DomainError as exc:
        raise domain_error_handler(exc) from exc
    if result.get("http_status") == 401:
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    return {k: v for k, v in result.items() if k != "http_status"}
