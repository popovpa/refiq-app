from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.sdk.service import SdkCredentialService

router = APIRouter()


@router.post("/event", status_code=204)
@router.post("/events", status_code=204)
async def receive_sdk_event(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    raw = (await request.body()).decode("utf-8", errors="replace")
    await SdkCredentialService(db).ingest(raw)
    return Response(status_code=204)
