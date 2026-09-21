import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base
from app.modules.users.models import User, UserRole
from app.modules.auth.models import PasswordResetToken, EmailConfirmationToken
from app.modules.businesses.models import Business, BusinessMembership
from app.modules.partners.models import PartnerProfile, BusinessPartner
from app.modules.products.models import Product
from app.modules.offers.models import Offer, OfferCommissionRule, OfferPartnerAccess
from app.modules.audit.models import AuditEvent
from app.modules.catalog.models import OfferVertical, OfferCategory
from app.modules.campaigns.models import Campaign
from app.modules.links.models import TrackingLink, Click
from app.modules.conversions.models import Conversion
from app.modules.commissions.models import Commission
from app.modules.payouts.models import Payout, PayoutItem
from app.modules.billing.models import BusinessSubscription, PlatformFee, BillingTransaction
from app.modules.system.models import UserSettings, BusinessSettings, PartnerSettings, AuditLog, OutboxEvent
from app.modules.postback.models import PostbackCredential
from app.modules.sdk.models import SdkScript
from app.modules.sites.models import Site
from app.modules.ai.usage.models import AiUsage
from app.admin.auth.models import AdminUser
from app.admin.audit.models import AdminAuditEvent
from app.modules.postback.attempt import PostbackAttempt
from app.modules.notifications.models import Notification
from app.modules.finance.models import (
    BillingInvoice,
    BusinessBillingProfile,
    FinancialAuditEvent,
    FinancialEntry,
    FinancialIdempotencyKey,
    FinancialJobLock,
    LegalEntity,
    LegalEntityVerificationAttempt,
    PartnerPayoutProfile,
    PartnerTrafficSuspension,
    Plan,
    PlanVersion,
    ProviderWebhookEvent,
    TermsAcceptance,
    TestFinancialOperation,
)

config = context.config

database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
