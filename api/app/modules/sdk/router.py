from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.ids import parse_id
from app.core.permissions import require_business_role
from app.modules.sdk.dto import SdkCredentialCreated, SdkCredentialStatus
from app.modules.sdk.service import SdkCredentialService

router = APIRouter()


@router.get("/credential", response_model=SdkCredentialStatus)
async def get_sdk_credential(
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    service = SdkCredentialService(db)
    return await service.get_status(parse_id(session_data["active_business_id"]))


@router.post("/credential", response_model=SdkCredentialCreated)
async def create_sdk_credential(
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    service = SdkCredentialService(db)
    return await service.create(parse_id(session_data["active_business_id"]), session_data["user_id"])
