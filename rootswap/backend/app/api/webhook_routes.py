from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import domain_error_handler
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
    payload = await request.body()
    headers = {k: v for k, v in request.headers.items()}
    service = WebhookService()
    try:
        result = await service.process_webhook(session, partner_code, payload, headers)
    except DomainError as exc:
        raise domain_error_handler(exc) from exc
    return result
