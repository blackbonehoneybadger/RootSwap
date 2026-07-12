from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.webhook_processor import ingest_webhook

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/partners/{partner_code}")
async def partner_webhook(
    partner_code: str,
    request: Request,
    x_signature: str = Header(default=""),
    x_timestamp: str = Header(default=""),
    session: AsyncSession = Depends(get_db),
) -> dict:
    raw_body = await request.body()
    event = await ingest_webhook(
        session,
        partner_code=partner_code,
        raw_body=raw_body,
        signature=x_signature,
        timestamp=x_timestamp,
    )
    return {
        "event_id": event.external_event_id,
        "processing_status": event.processing_status.value,
    }
