from contextlib import asynccontextmanager
import asyncio
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine
from app.core.middleware import RequestIDMiddleware, StructuredLoggingMiddleware
from app.core.exceptions import register_exception_handlers

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.modules.ai.jobs import has_test_job_runner
    from app.modules.finance.jobs import run_financial_jobs

    stop = asyncio.Event()
    task = None
    finance_task = None
    if not has_test_job_runner():
        async def _promo_loop():
            from app.modules.ai.application.creative.promo_worker import pump_queued_runs

            while not stop.is_set():
                try:
                    await pump_queued_runs()
                except Exception:
                    logger.exception("promo_generation_pump_failed")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=2)
                except asyncio.TimeoutError:
                    pass

        async def _finance_loop():
            while not stop.is_set():
                try:
                    await run_financial_jobs()
                except Exception:
                    logger.exception("financial_jobs_failed")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=60)
                except asyncio.TimeoutError:
                    pass

        task = asyncio.create_task(_promo_loop())
        finance_task = asyncio.create_task(_finance_loop())
    yield
    stop.set()
    for item in (task, finance_task):
        if item:
            item.cancel()
            try:
                await item
            except asyncio.CancelledError:
                pass
    await engine.dispose()


app = FastAPI(
    title="RefIQ API",
    version="0.1.0",
    docs_url="/api/docs" if settings.APP_ENV == "development" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)
app.add_middleware(StructuredLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

register_exception_handlers(app)

from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.businesses.router import router as businesses_router
from app.modules.partners.router import router as partners_router
from app.modules.offers.router import router as offers_router
from app.modules.links.router import router as links_router
from app.modules.links.business_router import router as business_links_router
from app.modules.campaigns.router import router as partner_campaigns_router
from app.modules.campaigns.router import business_router as business_campaigns_router
from app.modules.conversions.router import router as conversions_router
from app.modules.commissions.router import router as commissions_router
from app.modules.payouts.router import router as payouts_router
from app.modules.tracker.router import router as tracker_router
from app.modules.postback.controller import router as postback_router
from app.modules.postback.credential_router import router as postback_credential_router
from app.modules.sdk.router import router as sdk_credential_router
from app.modules.sdk.event_router import router as sdk_event_router
from app.modules.sites.router import router as sites_router
from app.modules.ai.router import router as ai_router
from app.modules.creatives.business_router import router as business_creatives_router
from app.modules.creatives.partner_router import router as partner_creatives_router
from app.modules.notifications.router import router as notifications_router
from app.modules.finance.business_router import router as finance_business_router
from app.modules.finance.partner_router import router as finance_partner_router
from app.modules.finance.webhooks import router as finance_webhook_router
from app.modules.finance.test_router import router as finance_test_router
from app.modules.finance.providers.factory import validate_live_startup

validate_live_startup()

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/v1/me", tags=["users"])
app.include_router(businesses_router, prefix="/api/v1/business", tags=["business"])
app.include_router(partners_router, prefix="/api/v1/partner", tags=["partner"])
app.include_router(offers_router, prefix="/api/v1/business/offers", tags=["offers"])
app.include_router(links_router, prefix="/api/v1/partner/links", tags=["links"])
app.include_router(business_links_router, prefix="/api/v1/business", tags=["links"])
app.include_router(partner_campaigns_router, prefix="/api/v1/partner/campaigns", tags=["campaigns"])
app.include_router(business_campaigns_router, prefix="/api/v1/business", tags=["campaigns"])
app.include_router(conversions_router, prefix="/api/v1", tags=["conversions"])
app.include_router(commissions_router, prefix="/api/v1", tags=["commissions"])
app.include_router(payouts_router, prefix="/api/v1", tags=["payouts"])
app.include_router(tracker_router, tags=["tracker"])
app.include_router(postback_router, tags=["postback"])
app.include_router(postback_credential_router, prefix="/api/v1/business/postback", tags=["postback"])
app.include_router(sdk_credential_router, prefix="/api/v1/business/sdk", tags=["sdk"])
app.include_router(sites_router, prefix="/api/v1/business/sites", tags=["sites"])
app.include_router(sdk_event_router, tags=["sdk"])
app.include_router(ai_router, prefix="/api/v1/ai", tags=["ai"])
app.include_router(business_creatives_router, prefix="/api/v1/business/offers", tags=["creatives"])
app.include_router(partner_creatives_router, prefix="/api/v1/partner", tags=["creatives"])
app.include_router(notifications_router, prefix="/api/v1/notifications", tags=["notifications"])
app.include_router(finance_business_router, prefix="/api/v1/business", tags=["finance"])
app.include_router(finance_partner_router, prefix="/api/v1/partner", tags=["finance"])
app.include_router(finance_webhook_router, prefix="/api/v1/finance", tags=["finance"])
if not settings.is_production:
    app.include_router(finance_test_router, prefix="/api/v1/finance/test", tags=["finance-test"])


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    from app.core.database import async_session_factory
    from app.core.redis import redis_client
    try:
        async with async_session_factory() as session:
            await session.execute(__import__("sqlalchemy").text("SELECT 1"))
        await redis_client.ping()
        return {"status": "ready"}
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"status": "unavailable"})
