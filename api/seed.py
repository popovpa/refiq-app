"""Seed development database with demo data."""
import asyncio
import json
import secrets
from datetime import datetime, timezone, timedelta

from sqlalchemy import text
from app.core.database import async_session_factory
from app.core.security import hash_password
from app.modules.links.short_code import generate_short_code


class _Ids:
    def __init__(self):
        self._n = 0

    def __call__(self) -> int:
        self._n += 1
        return self._n


async def seed():
    async with async_session_factory() as db:
        existing = await db.execute(text("SELECT id FROM users WHERE email = 'business@example.com'"))
        if existing.scalar_one_or_none():
            print("Database already seeded.")
            return

        password_hash = hash_password("password123")
        now = datetime.now(timezone.utc)

        next_id = _Ids()

        # Users
        business_user_id = next_id()
        partner_user_id = next_id()
        both_user_id = next_id()

        await db.execute(text("""
            INSERT INTO users (id, email, password_hash, first_name, last_name, timezone, language, status, created_at, updated_at)
            VALUES
                (:bu_id, 'business@example.com', :pw, 'Алексей', 'Петров', 'Europe/Moscow', 'ru', 'active', :now, :now),
                (:pu_id, 'partner@example.com', :pw, 'Мария', 'Иванова', 'Europe/Moscow', 'ru', 'active', :now, :now),
                (:both_id, 'both@example.com', :pw, 'Дмитрий', 'Сидоров', 'Europe/Moscow', 'ru', 'active', :now, :now)
        """), {
            "bu_id": business_user_id, "pu_id": partner_user_id, "both_id": both_user_id,
            "pw": password_hash, "now": now,
        })

        # Roles
        await db.execute(text("""
            INSERT INTO user_roles (id, user_id, role, status, created_at)
            VALUES
                (:id1, :bu_id, 'business', 'active', :now),
                (:id2, :pu_id, 'partner', 'active', :now),
                (:id3, :both_id, 'business', 'active', :now),
                (:id4, :both_id, 'partner', 'active', :now)
        """), {
            "id1": next_id(), "id2": next_id(), "id3": next_id(), "id4": next_id(),
            "bu_id": business_user_id, "pu_id": partner_user_id, "both_id": both_user_id,
            "now": now,
        })

        # Businesses
        business1_id = next_id()
        business2_id = next_id()

        await db.execute(text("""
            INSERT INTO businesses (id, name, legal_name, country, currency, status, created_at, updated_at)
            VALUES
                (:b1_id, 'ТехноСофт', 'ООО ТехноСофт', 'RU', 'RUB', 'active', :now, :now),
                (:b2_id, 'Дмитрий Corp', 'ИП Сидоров', 'RU', 'RUB', 'active', :now, :now)
        """), {"b1_id": business1_id, "b2_id": business2_id, "now": now})

        # Business Memberships
        await db.execute(text("""
            INSERT INTO business_memberships (id, business_id, user_id, permission_role, status, created_at)
            VALUES
                (:id1, :b1_id, :bu_id, 'owner', 'active', :now),
                (:id2, :b2_id, :both_id, 'owner', 'active', :now)
        """), {
            "id1": next_id(), "id2": next_id(),
            "b1_id": business1_id, "b2_id": business2_id,
            "bu_id": business_user_id, "both_id": both_user_id,
            "now": now,
        })

        # Partner Profiles
        partner1_id = next_id()
        partner2_id = next_id()

        await db.execute(text("""
            INSERT INTO partner_profiles (id, user_id, display_name, description, status, created_at, updated_at)
            VALUES
                (:p1_id, :pu_id, 'Мария Иванова', 'Маркетолог с опытом в IT', 'active', :now, :now),
                (:p2_id, :both_id, 'Дмитрий Сидоров', 'Digital-продвижение', 'active', :now, :now)
        """), {
            "p1_id": partner1_id, "p2_id": partner2_id,
            "pu_id": partner_user_id, "both_id": both_user_id,
            "now": now,
        })

        # Products
        product1_id = next_id()
        product2_id = next_id()
        product3_id = next_id()

        await db.execute(text("""
            INSERT INTO products (id, business_id, name, description, url, status, created_at, updated_at)
            VALUES
                (:p1, :b1, 'CRM Pro', 'Система управления клиентами', 'https://crmpro.example.com', 'active', :now, :now),
                (:p2, :b1, 'TaskFlow', 'Менеджер задач для команд', 'https://taskflow.example.com', 'active', :now, :now),
                (:p3, :b2, 'DataAnalytics', 'Аналитика данных', 'https://dataanalytics.example.com', 'active', :now, :now)
        """), {
            "p1": product1_id, "p2": product2_id, "p3": product3_id,
            "b1": business1_id, "b2": business2_id, "now": now,
        })

        # Offers
        offer1_id = next_id()
        offer2_id = next_id()
        offer3_id = next_id()

        await db.execute(text("""
            INSERT INTO offers (id, business_id, product_id, name, description, status, visibility, access_policy, conversion_type, attribution_window_days, hold_period_days, currency, category, category_id, geo, allowed_traffic, forbidden_traffic, partner_notes, materials, created_at, updated_at)
            VALUES
                (:o1, :b1, :p1, 'CRM Pro — Подписка', 'Партнёрская программа CRM Pro. Комиссия за каждую оплаченную подписку.', 'active', 'public', 'open', 'sale', 30, 0, 'RUB', 'CRM', :crm_id, 'RU,KZ,BY', CAST(:traffic AS JSON), CAST(:forbidden AS JSON), 'Используйте промокод PARTNER20 на посадочной странице.', CAST(:materials1 AS JSON), :now, :now),
                (:o2, :b1, :p2, 'TaskFlow — Регистрация', 'Комиссия за регистрацию пользователя в TaskFlow.', 'active', 'public', 'approval', 'signup', 14, 0, 'RUB', 'CRM', :crm_id, 'RU', CAST(:traffic AS JSON), CAST(:forbidden AS JSON), 'Нельзя использовать брендовые запросы в PPC.', CAST(:materials2 AS JSON), :now, :now),
                (:o3, :b2, :p3, 'DataAnalytics — Enterprise', 'Партнёрка DataAnalytics Enterprise.', 'active', 'public', 'open', 'sale', 60, 0, 'RUB', 'PAYMENT_SERVICES', :pay_id, 'US', CAST(:traffic AS JSON), CAST(:forbidden AS JSON), 'Подходит для B2B-аудитории.', CAST(:materials3 AS JSON), :now, :now)
        """), {
            "o1": offer1_id, "o2": offer2_id, "o3": offer3_id,
            "b1": business1_id, "b2": business2_id,
            "p1": product1_id, "p2": product2_id, "p3": product3_id,
            "now": now,
            "crm_id": (await db.execute(text("SELECT id FROM offer_categories WHERE code = 'CRM'"))).scalar_one(),
            "pay_id": (await db.execute(text("SELECT id FROM offer_categories WHERE code = 'PAYMENT_SERVICES'"))).scalar_one(),
            "traffic": json.dumps(["SEO", "WEBSITE_CONTENT", "SOCIAL_ORGANIC", "VIDEO_CONTENT", "MESSENGERS"]),
            "forbidden": json.dumps([]),
            "materials1": json.dumps([
                {"type": "text", "title": "Оффер", "content": "CRM Pro — система для продаж и сопровождения клиентов."},
                {"type": "text", "title": "CTA", "content": "Попробуйте CRM Pro 14 дней бесплатно."},
            ]),
            "materials2": json.dumps([
                {"type": "text", "title": "Оффер", "content": "TaskFlow помогает командам закрывать задачи вовремя."},
            ]),
            "materials3": json.dumps([
                {"type": "text", "title": "Оффер", "content": "DataAnalytics Enterprise для компаний, которым нужна отчётность."},
            ]),
        })

        # Commission Rules
        await db.execute(text("""
            INSERT INTO offer_commission_rules (id, offer_id, type, value, currency, created_at, updated_at)
            VALUES
                (:id1, :o1, 'percent', 20.0, 'RUB', :now, :now),
                (:id2, :o2, 'fixed', 500.0, 'RUB', :now, :now),
                (:id3, :o3, 'percent', 15.0, 'RUB', :now, :now)
        """), {
            "id1": next_id(), "id2": next_id(), "id3": next_id(),
            "o1": offer1_id, "o2": offer2_id, "o3": offer3_id,
            "now": now,
        })

        # Offer Partner Access
        await db.execute(text("""
            INSERT INTO offer_partner_access (id, offer_id, partner_id, status, source, created_at, approved_at)
            VALUES
                (:id1, :o1, :p1, 'approved', 'marketplace', :now, :now),
                (:id2, :o2, :p1, 'pending', 'marketplace', :now, NULL),
                (:id3, :o3, :p2, 'approved', 'marketplace', :now, :now),
                (:id4, :o1, :p2, 'approved', 'marketplace', :now, :now)
        """), {
            "id1": next_id(), "id2": next_id(), "id3": next_id(), "id4": next_id(),
            "o1": offer1_id, "o2": offer2_id, "o3": offer3_id,
            "p1": partner1_id, "p2": partner2_id,
            "now": now,
        })

        # Business Partners
        await db.execute(text("""
            INSERT INTO business_partners (id, business_id, partner_id, status, created_at, updated_at)
            VALUES
                (:id1, :b1, :p1, 'active', :now, :now),
                (:id2, :b1, :p2, 'active', :now, :now),
                (:id3, :b2, :p2, 'active', :now, :now)
        """), {
            "id1": next_id(), "id2": next_id(), "id3": next_id(),
            "b1": business1_id, "b2": business2_id,
            "p1": partner1_id, "p2": partner2_id,
            "now": now,
        })

        # Tracking Links
        link1_id = next_id()
        link2_id = next_id()
        link3_id = next_id()

        codes: set[str] = set()
        while len(codes) < 3:
            codes.add(generate_short_code())
        sc1, sc2, sc3 = codes

        await db.execute(text("""
            INSERT INTO tracking_links (id, offer_id, partner_id, short_code, destination_url, name, traffic_source, status, created_at, updated_at)
            VALUES
                (:l1, :o1, :p1, :sc1, 'https://crmpro.example.com/pricing', 'Telegram', 'MESSENGERS', 'ACTIVE', :now, :now),
                (:l2, :o1, :p2, :sc2, 'https://crmpro.example.com/pricing', 'Блог', 'WEBSITE_CONTENT', 'ACTIVE', :now, :now),
                (:l3, :o3, :p2, :sc3, 'https://dataanalytics.example.com/enterprise', 'YouTube', 'VIDEO_CONTENT', 'ACTIVE', :now, :now)
        """), {
            "l1": link1_id, "l2": link2_id, "l3": link3_id,
            "o1": offer1_id, "o3": offer3_id,
            "p1": partner1_id, "p2": partner2_id,
            "sc1": sc1, "sc2": sc2, "sc3": sc3,
            "now": now,
        })

        alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
        used_codes: set[str] = set()

        def next_rqcid() -> str:
            while True:
                code = "".join(secrets.choice(alphabet) for _ in range(12))
                if code not in used_codes:
                    used_codes.add(code)
                    return code

        for i in range(48):
            click_id = next_id()
            days_ago = 30 - (i % 30)
            created = now - timedelta(days=days_ago, hours=i % 12)
            lid = link1_id if i < 28 else link2_id
            await db.execute(text("""
                INSERT INTO clicks (id, tracking_link_id, rqcid, created_at)
                VALUES (:id, :lid, :rqcid, :created)
            """), {
                "id": click_id,
                "lid": lid,
                "rqcid": next_rqcid(),
                "created": created,
            })

        # Conversions
        conv_ids = [next_id() for _ in range(8)]
        amounts = [4990, 4990, 4990, 4990, 4990, 4990, 4990, 4990]
        commission_amounts = [998, 998, 998, 998, 998, 998, 998, 998]
        statuses = ["approved", "approved", "approved", "pending", "pending", "approved", "paid", "rejected"]

        for i, (cid, amount, comm, st) in enumerate(zip(conv_ids, amounts, commission_amounts, statuses)):
            days_ago = 30 - i * 3
            converted_at = now - timedelta(days=days_ago)
            approved_at = converted_at + timedelta(days=1) if st in ("approved", "paid") else None
            await db.execute(text("""
                INSERT INTO conversions (id, business_id, offer_id, partner_id, tracking_link_id, click_id, external_id, amount, currency, commission_amount, status, converted_at, approved_at, created_at, updated_at)
                VALUES (:id, :bid, :oid, :pid, :lid, :click, :ext, :amount, 'RUB', :comm, :status, :converted, :approved, :created, :created)
            """), {
                "id": cid,
                "bid": business1_id,
                "oid": offer1_id,
                "pid": partner1_id if i < 4 else partner2_id,
                "lid": link1_id if i < 4 else link2_id,
                "click": f"click_{secrets.token_hex(8)}",
                "ext": f"order_{1000 + i}",
                "amount": amount,
                "comm": comm,
                "status": st,
                "converted": converted_at,
                "approved": approved_at,
                "created": converted_at,
            })

        # Commissions for approved/paid conversions
        for i, (cid, st) in enumerate(zip(conv_ids, statuses)):
            if st in ("approved", "paid"):
                comm_status = "paid" if st == "paid" else "approved"
                await db.execute(text("""
                    INSERT INTO commissions (id, conversion_id, business_id, partner_id, amount, currency, status, created_at, updated_at)
                    VALUES (:id, :cid, :bid, :pid, 998, 'RUB', :status, :now, :now)
                """), {
                    "id": next_id(),
                    "cid": cid,
                    "bid": business1_id,
                    "pid": partner1_id if i < 4 else partner2_id,
                    "status": comm_status,
                    "now": now,
                })

        # Payout
        payout_id = next_id()
        await db.execute(text("""
            INSERT INTO payouts (id, partner_id, amount, currency, status, created_at, paid_at)
            VALUES (:id, :pid, 998, 'RUB', 'paid', :now, :now)
        """), {"id": payout_id, "pid": partner1_id, "now": now - timedelta(days=5)})

        for table in (
            "users",
            "user_roles",
            "businesses",
            "business_memberships",
            "partner_profiles",
            "products",
            "offers",
            "offer_commission_rules",
            "offer_partner_access",
            "business_partners",
            "tracking_links",
            "clicks",
            "conversions",
            "commissions",
            "payouts",
        ):
            await db.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 1))"
            ))

        await db.commit()
        print("Seed data created successfully!")
        print("\nDemo accounts:")
        print("  business@example.com / password123")
        print("  partner@example.com  / password123")
        print("  both@example.com     / password123")


if __name__ == "__main__":
    asyncio.run(seed())
