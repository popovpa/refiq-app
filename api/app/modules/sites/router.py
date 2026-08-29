from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.ids import parse_id
from app.core.permissions import require_business_role
from app.modules.sites.dto import SiteCreateRequest, SiteResponse, SiteUpdateRequest
from app.modules.sites.service import SiteService

router = APIRouter()


def _service(db: AsyncSession) -> SiteService:
    return SiteService(db)


@router.get("", response_model=list[SiteResponse])
async def list_sites(
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    return await _service(db).list_sites(parse_id(session_data["active_business_id"]))


@router.post("", response_model=SiteResponse)
async def create_site(
    data: SiteCreateRequest,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    return await _service(db).create(
        parse_id(session_data["active_business_id"]),
        session_data["user_id"],
        url=data.url,
        name=data.name,
    )


@router.get("/{site_id}", response_model=SiteResponse)
async def get_site(
    site_id: int,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    return await _service(db).get_site(parse_id(session_data["active_business_id"]), site_id)


@router.patch("/{site_id}", response_model=SiteResponse)
async def update_site(
    site_id: int,
    data: SiteUpdateRequest,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    if data.name is None:
        return await _service(db).get_site(parse_id(session_data["active_business_id"]), site_id)
    return await _service(db).update_name(
        parse_id(session_data["active_business_id"]), site_id, data.name
    )


@router.post("/{site_id}/disable", response_model=SiteResponse)
async def disable_site(
    site_id: int,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    return await _service(db).disable(
        parse_id(session_data["active_business_id"]), site_id, session_data["user_id"]
    )


@router.post("/{site_id}/enable", response_model=SiteResponse)
async def enable_site(
    site_id: int,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    return await _service(db).enable(
        parse_id(session_data["active_business_id"]), site_id, session_data["user_id"]
    )


@router.post("/{site_id}/check", response_model=SiteResponse)
async def check_site_sdk(
    site_id: int,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    return await _service(db).get_site(parse_id(session_data["active_business_id"]), site_id)


@router.delete("/{site_id}", status_code=204)
async def delete_site(
    site_id: int,
    session_data: dict = Depends(require_business_role),
    db: AsyncSession = Depends(get_db),
):
    await _service(db).delete(
        parse_id(session_data["active_business_id"]), site_id, session_data["user_id"]
    )
    return Response(status_code=204)
