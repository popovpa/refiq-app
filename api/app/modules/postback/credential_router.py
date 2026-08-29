from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.ids import parse_id
from app.core.permissions import require_business_role
from app.modules.postback.credential_service import PostbackCredentialService
from app.modules.postback.dto import PostbackCredentialStatus, PostbackTokenCreated

router = APIRouter()


@router.get("/credential", response_model=PostbackCredentialStatus)
async def get_postback_credential(
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    service = PostbackCredentialService(db)
    return await service.get_status(parse_id(session_data["active_business_id"]))


@router.post("/credential", response_model=PostbackTokenCreated)
async def create_postback_credential(
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    service = PostbackCredentialService(db)
    return await service.create(parse_id(session_data["active_business_id"]), session_data["user_id"])


@router.post("/credential/rotate", response_model=PostbackTokenCreated)
async def rotate_postback_credential(
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    service = PostbackCredentialService(db)
    return await service.rotate(parse_id(session_data["active_business_id"]), session_data["user_id"])
