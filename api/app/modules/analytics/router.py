from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import get_session_data
from app.modules.analytics.filters import AnalyticsFilters, analytics_filters
from app.modules.analytics.schemas import (
    BehaviorResponse,
    FiltersResponse,
    FunnelResponse,
    OverviewResponse,
    PerformanceResponse,
    QualityResponse,
    SourcesResponse,
)
from app.modules.analytics.service import (
    build_behavior,
    build_filters,
    build_funnel,
    build_overview,
    build_performance,
    build_quality,
    build_sources,
)

router = APIRouter()


@router.get("/overview", response_model=OverviewResponse)
async def overview(
    filt: AnalyticsFilters = Depends(analytics_filters),
    db: AsyncSession = Depends(get_db),
    session_data: dict = Depends(get_session_data),
):
    return await build_overview(db, session_data, filt)


@router.get("/funnel", response_model=FunnelResponse)
async def funnel(
    filt: AnalyticsFilters = Depends(analytics_filters),
    db: AsyncSession = Depends(get_db),
    session_data: dict = Depends(get_session_data),
):
    return await build_funnel(db, session_data, filt)


@router.get("/behavior", response_model=BehaviorResponse)
async def behavior(
    filt: AnalyticsFilters = Depends(analytics_filters),
    db: AsyncSession = Depends(get_db),
    session_data: dict = Depends(get_session_data),
):
    return await build_behavior(db, session_data, filt)


@router.get("/sources", response_model=SourcesResponse)
async def sources(
    filt: AnalyticsFilters = Depends(analytics_filters),
    db: AsyncSession = Depends(get_db),
    session_data: dict = Depends(get_session_data),
):
    return await build_sources(db, session_data, filt)


@router.get("/quality", response_model=QualityResponse)
async def quality(
    filt: AnalyticsFilters = Depends(analytics_filters),
    db: AsyncSession = Depends(get_db),
    session_data: dict = Depends(get_session_data),
):
    return await build_quality(db, session_data, filt)


@router.get("/performance", response_model=PerformanceResponse)
async def performance(
    filt: AnalyticsFilters = Depends(analytics_filters),
    db: AsyncSession = Depends(get_db),
    session_data: dict = Depends(get_session_data),
):
    return await build_performance(db, session_data, filt)


@router.get("/filters", response_model=FiltersResponse)
async def filters(
    db: AsyncSession = Depends(get_db),
    session_data: dict = Depends(get_session_data),
):
    return await build_filters(db, session_data)
