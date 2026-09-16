import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import JSON, event
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base, get_db

from app.modules.users.models import User, UserRole  # noqa
from app.modules.auth.models import PasswordResetToken, EmailConfirmationToken  # noqa
from app.modules.businesses.models import Business, BusinessMembership  # noqa
from app.modules.partners.models import PartnerProfile, BusinessPartner  # noqa
from app.modules.products.models import Product  # noqa
from app.modules.offers.models import Offer, OfferCommissionRule, OfferPartnerAccess  # noqa
from app.modules.catalog.models import OfferVertical, OfferCategory  # noqa
from app.modules.campaigns.models import Campaign  # noqa
from app.modules.links.models import TrackingLink, Click  # noqa
from app.modules.conversions.models import Conversion  # noqa
from app.modules.commissions.models import Commission  # noqa
from app.modules.payouts.models import Payout, PayoutItem  # noqa
from app.modules.system.models import AuditLog, OutboxEvent, UserSettings, BusinessSettings, PartnerSettings  # noqa
from app.modules.postback.models import PostbackCredential  # noqa
from app.modules.sdk.models import SdkScript  # noqa
from app.modules.sites.models import Site  # noqa
from app.modules.ai.usage.models import AiUsage  # noqa
from app.modules.ai.lifecycle.models import AiGeneration  # noqa
from app.modules.assets.models import Asset  # noqa
from app.modules.brand_kits.models import BrandKit  # noqa
from app.modules.creatives.models import Creative  # noqa
from app.modules.creatives.promo_runs import OfferPromoGenerationItem, OfferPromoGenerationRun  # noqa
from app.modules.billing.models import BusinessSubscription, PlatformFee, BillingTransaction  # noqa
from app.admin.auth.models import AdminUser  # noqa
from app.admin.audit.models import AdminAuditEvent  # noqa
from app.modules.postback.attempt import PostbackAttempt  # noqa
from app.modules.notifications.models import Notification  # noqa

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# In-memory session store for tests
_sessions: dict[str, str] = {}


class FakeRedis:
    async def setex(self, key: str, ttl: int, value: str):
        _sessions[key] = value

    async def set(self, key: str, value: str, **kwargs):
        _sessions[key] = value

    async def get(self, key: str):
        return _sessions.get(key)

    async def incr(self, key: str):
        value = int(_sessions.get(key) or 0) + 1
        _sessions[key] = str(value)
        return value

    async def expire(self, key: str, ttl: int):
        return True

    async def delete(self, key: str):
        _sessions.pop(key, None)

    async def scan_iter(self, pattern: str):
        for key in list(_sessions.keys()):
            if key.startswith(pattern.rstrip("*")):
                yield key

    async def ping(self):
        return True


# Patch redis before importing the app
import app.core.redis
import app.core.sessions
fake_redis = FakeRedis()
app.core.redis.redis_client = fake_redis
app.core.sessions.redis_client = fake_redis

from app.main import app as fastapi_app
from app.modules.ai.deps import set_usage_session_factory
from app.modules.ai.jobs import DeferredJobRunner, set_job_runner
from app.modules.assets.service import set_asset_storage
from app.modules.email.deps import set_email_provider
from app.core.config import settings as app_settings

set_usage_session_factory(TestingSessionLocal)


@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=OFF")
    cursor.close()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    _sessions.clear()
    monkeypatch.setattr(app_settings, "ASSET_STORAGE_DIR", str(tmp_path / "assets"))
    monkeypatch.setattr(app_settings, "S3_ACCESS_KEY_ID", "")
    monkeypatch.setattr(app_settings, "S3_SECRET_ACCESS_KEY", "")
    monkeypatch.setattr(app_settings, "YANDEX_POSTBOX_ACCESS_KEY_ID", "")
    monkeypatch.setattr(app_settings, "YANDEX_POSTBOX_SECRET_ACCESS_KEY", "")
    monkeypatch.setattr("app.core.database.async_session_factory", TestingSessionLocal)
    monkeypatch.setattr("app.modules.postback.service.async_session_factory", TestingSessionLocal)
    set_asset_storage(None)
    set_email_provider(None)
    runner = DeferredJobRunner()
    set_job_runner(runner)

    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    set_job_runner(None)
    set_asset_storage(None)
    set_email_provider(None)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with TestingSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


fastapi_app.dependency_overrides[get_db] = override_get_db

from app.admin.app import app as admin_app

admin_app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def client():
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def admin_client():
    transport = ASGITransport(app=admin_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def job_runner() -> DeferredJobRunner:
    from app.modules.ai.jobs import get_test_job_runner

    return get_test_job_runner()


@pytest.fixture
async def db():
    async with TestingSessionLocal() as session:
        yield session
