from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.postback.dto import PostbackAccepted, PostbackRequest
from app.modules.postback.service import PostbackService

router = APIRouter()


@router.post("/postback", response_model=PostbackAccepted)
async def receive_postback(
    payload: PostbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    service = PostbackService(db)
    return await service.handle(request.headers.get("Authorization"), payload)
