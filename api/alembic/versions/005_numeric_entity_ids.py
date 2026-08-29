"""Convert entity IDs from UUID to bigint.

Revision ID: 005
Revises: 004
Create Date: 2026-08-16

Existing UUID databases are rebuilt. Fresh installs that already used bigint skip this.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    row = bind.execute(
        sa.text(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'users'
              AND column_name = 'id'
            """
        )
    ).fetchone()
    if row is None or row[0] != "uuid":
        return

    from app.core.database import Base
    from app.modules.users.models import User, UserRole  # noqa: F401
    from app.modules.businesses.models import Business, BusinessMembership  # noqa: F401
    from app.modules.partners.models import PartnerProfile, BusinessPartner  # noqa: F401
    from app.modules.products.models import Product  # noqa: F401
    from app.modules.offers.models import Offer, OfferCommissionRule, OfferPartnerAccess  # noqa: F401
    from app.modules.campaigns.models import Campaign  # noqa: F401
    from app.modules.links.models import TrackingLink  # noqa: F401
    from app.modules.conversions.models import Conversion  # noqa: F401
    from app.modules.commissions.models import Commission  # noqa: F401
    from app.modules.payouts.models import Payout, PayoutItem  # noqa: F401
    from app.modules.system.models import (  # noqa: F401
        AuditLog,
        OutboxEvent,
        UserSettings,
        BusinessSettings,
        PartnerSettings,
    )
    from app.modules.billing.models import BusinessSubscription, PlatformFee, BillingTransaction  # noqa: F401

    Base.metadata.drop_all(bind)
    Base.metadata.create_all(bind)


def downgrade() -> None:
    pass
