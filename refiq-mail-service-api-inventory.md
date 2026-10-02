# RefIQ API → Mail Service Technical Inventory

## 1. Executive Summary

- **Current stack:** Python 3.12 (requires `>=3.11`), FastAPI, SQLAlchemy 2.x asyncio + asyncpg, Pydantic v2 + pydantic-settings, Alembic, Redis, structlog, httpx, boto3. Source: `api/pyproject.toml`, `api/Dockerfile`.
- **Current email architecture:** In-process module `app.modules.email` inside `api`. Sync boto3 SESv2 client wrapped with `asyncio.to_thread`; send happens inline in the HTTP request path (not queued). Callers fail-open (exceptions swallowed after logging).
- **Provider:** Yandex Cloud Postbox (Amazon-compatible SESv2 HTTP API via boto3). Not SMTP. Source: `api/app/modules/email/postbox.py`.
- **Email types found:** **2** — account confirmation; password reset. No partner/business/offer/payout/billing emails. In-app `notifications` module is separate and does not send email.
- **Sync/async model:** Async FastAPI app; DB async; email provider call is sync boto3 offloaded to a thread; outer `asyncio.wait_for` timeout.
- **Background processing for email:** **None.** No Celery/Redis queue/Kafka consumer/outbox worker for mail. (Other domains use asyncio loops and FastAPI `BackgroundTasks` for AI/finance — not email.)
- **Service-to-service communication pattern:** No dedicated internal HTTP client pattern for `api → other_service` found. External integrations use ad-hoc `httpx.AsyncClient` (AI, DaData, TBank) or boto3 (S3, Postbox). No shared service-token / JWT S2S auth for internal services found in `api`.
- **Main technical constraints for extraction:** Email send is tightly coupled to auth flows inside the open DB transaction (pre-`get_db` commit); MessageId unused; no mail log / bounce webhooks / retry queue; credentials live in `api` Settings; templates are Python string functions (not Jinja); fail-open means “user created / OK response even if email never sent.”

---

## 2. API Technology Stack

| Component | Technology | Version | Source |
|---|---|---|---|
| Language | Python | 3.12 image; `requires-python >=3.11`; ruff `py312` | `api/Dockerfile`, `api/pyproject.toml` |
| Web framework | FastAPI | `>=0.115.0` | `api/pyproject.toml` |
| ASGI server | uvicorn | `>=0.30.0`, workers=1 | `api/pyproject.toml`, `api/entrypoint.sh` |
| ORM | SQLAlchemy (asyncio) | `>=2.0.35` | `api/pyproject.toml`, `api/app/core/database.py` |
| DB driver | asyncpg | `>=0.30.0` | `api/pyproject.toml` |
| Validation | Pydantic | `>=2.9.0` | `api/pyproject.toml` |
| Settings | pydantic-settings | `>=2.6.0` | `api/app/core/config.py` |
| Migrations | Alembic | `>=1.14.0` | `api/pyproject.toml`, `api/alembic/` |
| Dependency manager | pip + pyproject.toml / setuptools | setuptools `>=75.0` | `api/pyproject.toml`, `api/Dockerfile` |
| Cache/sessions | redis | `>=5.2.0` | `api/pyproject.toml`, `api/app/core/redis.py` |
| Logging | structlog | `>=24.4.0` | `api/pyproject.toml` |
| HTTP client | httpx | `>=0.27.0` | used by AI/finance/lookup — not by email |
| Email provider SDK | boto3 (sesv2) | `>=1.35.0` | `api/app/modules/email/postbox.py` |
| Email address validation | email-validator | `>=2.2.0` | schema validation only, not sending |
| Auth hashing | argon2-cffi | `>=23.1.0` | passwords |
| Architecture | Async request/response; sync provider offload | — | `api/app/main.py`, `postbox.py` |
| Entry point | `app.main:app` | — | `api/app/main.py`, `api/entrypoint.sh` |
| Launch | Docker `entrypoint.sh` → `alembic upgrade head` → `uvicorn ... --port 8000 --workers 1` | — | `api/entrypoint.sh` |

---

## 3. API Project Structure

```text
api/
├── Dockerfile
├── entrypoint.sh
├── entrypoint-admin.sh
├── pyproject.toml
├── alembic.ini
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/          # 001…032 migrations
├── seed.py
├── deploy/internal/       # empty placeholder
├── tests/
│   ├── conftest.py
│   ├── test_email_confirmation.py
│   ├── test_password_reset.py
│   └── …                  # domain tests
└── app/
    ├── main.py            # FastAPI app, routers, /health /ready
    ├── admin/             # admin-api surface (same image, other entrypoint)
    ├── common/            # enums, events (outbox helper)
    ├── core/              # config, database, exceptions, middleware, sessions, redis, security, ids
    ├── db/                # package stub (__init__.py only)
    └── modules/
        ├── email/         # provider, service, templates, errors, log, deps, dto
        │   └── templates/
        ├── auth/          # register, confirmation, password reset (email callers)
        ├── users/
        ├── businesses/
        ├── partners/
        ├── offers/
        ├── notifications/ # in-app only (not email)
        ├── finance/
        ├── ai/
        ├── assets/        # also uses boto3 (S3)
        └── …              # links, campaigns, conversions, payouts, postback, sdk, sites, tracker, …
```

Key locations:
- Routers: `app/modules/*/router*.py`, wired in `app/main.py`
- Schemas: typically `schemas.py` per module
- Models: `models.py` per module; Base in `app/core/database.py`
- Services: `service.py` / domain services (e. andg. `EmailService`)
- Repositories: selective (`sites`, `postback`, `sdk`, `ai/usage`) — **email has no repository**
- Config: `app/core/config.py`
- Integrations/clients: `email/postbox.py`, `assets/s3.py`, `finance/providers/`, `ai/providers/`, `finance/lookup/providers/`
- Background workers: `app/main.py` lifespan (promo + finance loops); AI `BackgroundTasks` via `app/modules/ai/jobs.py`
- Templates: `app/modules/email/templates/*.py` (Python, not Jinja files)
- Tests: `api/tests/`
- Migrations: `api/alembic/versions/`

---

## 4. Database Architecture

| Topic | Finding | Source |
|---|---|---|
| Engine | PostgreSQL 16 (compose) | `docker-compose.infra.yml` |
| URL | `DATABASE_URL` = `postgresql+asyncpg://…` | `config.py`, compose |
| Driver | **async** asyncpg | `database.py` |
| Session | `async_sessionmaker`; `get_db` yields session, **commits on success**, rolls back on exception | `app/core/database.py` |
| Transactions | Request-scoped; nested `begin_nested` used for finance idempotency | `finance/idempotency.py` |
| Base | `class Base(DeclarativeBase)` | `database.py` |
| IDs | Numeric `BigInteger` (+ Identity in migrations); SQLite variant `Integer` for tests via `EntityId` | `app/core/ids.py`, migrations |
| UUID/ULID | Not used as primary keys | — |
| Timezone | `DateTime(timezone=True)`; app uses `datetime.now(timezone.utc)` | models, auth services |
| `created_at` / `updated_at` | Common pattern with `server_default=func.now()`, `onupdate` where needed | e.g. `users`, settings |
| `deleted_at` / soft delete | **Not found** | grep across `app/` |
| Enums | Mostly **string columns** + Python enums/constants; **no PostgreSQL ENUM types** in migrations reviewed | alembic versions |
| JSON/JSONB | PostgreSQL `JSONB` widely (settings, audit, outbox, notifications metadata) | models |
| Repository pattern | Used in some modules; email uses service + provider protocol only | — |

**Patterns relevant to a future `mail` service (existing conventions only):**
- Async SQLAlchemy + `get_db`-style commit-on-success
- `pk_column` / `fk_column` from `app.core.ids`
- Timestamptz columns; snake_case table names; `ix_` / `uq_` index/constraint prefixes
- Pydantic settings for env
- Domain errors as exceptions (see Error Handling); email currently uses plain `EmailError` hierarchy **not** mapped through `AppError`

---

## 5. Migration Architecture

| Topic | Finding |
|---|---|
| Location | `api/alembic/versions/` |
| Naming | `{NNN}_{slug}.py` (e.g. `018_password_reset_tokens.py`, `032_audit_events.py`) |
| Template | `api/alembic/script.py.mako` |
| Metadata | Single `Base.metadata`; models imported in `alembic/env.py` |
| Generation | Standard Alembic (autogenerate possible via env); revisions are hand-numbered strings `"001"`…`"032"` |
| Apply | `alembic upgrade head` |
| Auto on start | **Yes** — `entrypoint.sh` / `entrypoint-admin.sh` run migrations before uvicorn | `api/entrypoint.sh` |
| Enum types | String columns; no `sa.Enum` / `CREATE TYPE` found in versions |
| Indexes/constraints | Explicit `op.create_index` / `UniqueConstraint` / `ForeignKey` in migrations |

**Reference migrations:**
1. `018_password_reset_tokens.py` — token table for password reset (hash unique index).
2. `019_email_confirmation_tokens.py` — confirmation tokens (same shape).
3. `032_audit_events.py` — canonical JSONB + indexes + `request_id` pattern.

---

## 6. Current Mail Architecture

```text
HTTP /api/v1/auth/register
  → AuthService.register (flush User)
  → EmailConfirmationService.issue
       → persist EmailConfirmationToken (hash only)
       → EmailService.send_account_confirmation
            → render_account_confirmation → layout HTML+text
            → provider.send (YandexCloudPostboxProvider / Disabled)
                 → boto3 sesv2 send_email
  → get_db commit (after request succeeds)

HTTP /api/v1/auth/forgot-password
  → PasswordResetService.request_reset
       → rate limit (Redis)
       → persist PasswordResetToken (hash only)
       → EmailService.send_password_reset
            → render_password_reset → layout
            → provider.send
  → get_db commit
```

ASCII:

```text
Business flow (auth) → EmailConfirmationService / PasswordResetService
                     → EmailService (templates + timeout)
                     → EmailProvider protocol
                     → YandexCloudPostboxProvider (boto3 sesv2)
                     → Yandex Cloud Postbox endpoint
```

No bounce/delivery callback handlers found. Provider `MessageId` return value is **not captured**.

---

## 7. Mail-related Files

| File | Responsibility | Called by | Candidate for migration |
|---|---|---|---|
| `api/app/modules/email/service.py` | Orchestrate render + send + timeout | auth services | Yes |
| `api/app/modules/email/postbox.py` | Yandex Postbox SESv2 client | `deps.get_email_provider` | Yes |
| `api/app/modules/email/provider.py` | `EmailProvider` Protocol | service/deps | Yes |
| `api/app/modules/email/deps.py` | Singleton provider / Disabled / test setter | service, tests | Yes |
| `api/app/modules/email/dto.py` | `EmailMessage` dataclass | provider/service | Yes |
| `api/app/modules/email/errors.py` | `EmailError`, `EmailNotConfigured`, `EmailSendError` | email module | Yes |
| `api/app/modules/email/log.py` | Domain-only logging helpers | email module | Yes |
| `api/app/modules/email/templates/layout.py` | Shared HTML+text layout | templates | Yes |
| `api/app/modules/email/templates/account_confirmation.py` | Confirmation template | EmailService | Yes |
| `api/app/modules/email/templates/password_reset.py` | Reset template | EmailService | Yes |
| `api/app/modules/email/__init__.py` | Re-export EmailService | — | Yes |
| `api/app/modules/auth/email_confirmation.py` | Token issue/confirm + trigger send | AuthService, router | **Partial** — send call moves; token/business stays |
| `api/app/modules/auth/password_reset.py` | Token issue/reset + trigger send | router | **Partial** |
| `api/app/modules/auth/service.py` | `register` → `issue` | router | Stay (trigger only) |
| `api/app/modules/auth/router.py` | Auth HTTP endpoints | FastAPI | Stay |
| `api/app/core/config.py` | Postbox + EMAIL_* settings | everywhere | Postbox settings → mail |
| `api/app/admin/queries/overview.py` | Admin health flag `email_sending` / `postbox_enabled` | admin overview | Adjust (config presence) |
| `api/tests/test_email_confirmation.py` | Confirmation + email mocks | pytest | Split later |
| `api/tests/test_password_reset.py` | Reset + email mocks | pytest | Split later |
| `api/pyproject.toml` | `boto3` dependency (also S3) | build | boto3 stays for S3; mail-specific usage moves |

**Not email (do not confuse):**
- `app/modules/notifications/*` — in-app notifications DB + API
- `app/modules/catalog/data.py` — catalog labels containing “EMAIL_*”
- `app/admin/queries/search.py` / `partners/privacy.py` — email regex for search/PII checks

---

## 8. Mail Provider

| Aspect | Detail |
|---|---|
| Provider | **Yandex Cloud Postbox** |
| SDK/API | boto3 client `"sesv2"`; method `send_email` |
| Transport | **HTTP** to Amazon-compatible API (**not SMTP**) |
| Endpoint | `YANDEX_POSTBOX_ENDPOINT` (default `https://postbox.cloud.yandex.net`) |
| Region | `YANDEX_POSTBOX_REGION` (default `ru-central1`) |
| Auth | Access key ID + secret access key (`YANDEX_POSTBOX_*`) |
| Init | Lazy singleton in `get_email_provider()`; if keys empty → `DisabledEmailProvider` |
| Enabled gate | `settings.postbox_enabled` = both key fields non-empty |
| Timeout | botocore `connect_timeout` ≤ 3s; `read_timeout` = clamped `EMAIL_SEND_TIMEOUT_SECONDS` (1–15); outer `asyncio.wait_for` same setting (default 8s) |
| Retry | botocore `retries={"max_attempts": 1, "mode": "standard"}` — effectively **no application retry** beyond one attempt |
| Error handling | `ClientError`/`BotoCoreError` → `EmailSendError`; unexpected → `EmailSendError`; logs via `log_email_error` |
| Provider message ID | **Not read / not stored** (`send_email` response ignored) |
| Rate limiting | **Not found** at app layer (Redis rate limit only on forgot-password requests) |
| Webhook/callback | **Not found** |
| Sandbox/test mode | **No explicit sandbox flag.** Unconfigured keys → disabled provider that raises `EmailNotConfigured`. Tests inject fake providers via `set_email_provider`. |

---

## 9. Mail Environment Variables

| Variable | Where used | Purpose | Secret |
|---|---|---|---|
| `YANDEX_POSTBOX_ACCESS_KEY_ID` | `config.py`, `postbox.py` | Provider access key | Yes |
| `YANDEX_POSTBOX_SECRET_ACCESS_KEY` | `config.py`, `postbox.py` | Provider secret | Yes |
| `YANDEX_POSTBOX_REGION` | `config.py`, `postbox.py` | Region name | No |
| `YANDEX_POSTBOX_ENDPOINT` | `config.py`, `postbox.py` | API base URL | No |
| `EMAIL_FROM` | `config.py`, `postbox.py` | Sender address (default `no-reply@refiq.ru`) | No |
| `EMAIL_FROM_NAME` | `config.py`, `postbox.py` | Sender display name (default `RefIQ`) | No |
| `EMAIL_SEND_TIMEOUT_SECONDS` | `config.py`, `service.py`, `postbox.py` | Send timeout | No |
| `FRONTEND_URL` / `APP_PUBLIC_URL` | `config.public_app_url`; auth URL builders | Public links in emails | No |
| `SECRET_KEY` | `password_reset.hash_reset_token` | HMAC for token hashes (not sent in email body as key) | Yes |

Notes:
- `.env.example` documents Postbox keys, region, endpoint, and `EMAIL_SEND_TIMEOUT_SECONDS`; **does not document `EMAIL_FROM` / `EMAIL_FROM_NAME`** (defaults in code).
- Secret **values** are not included in this report.

Related non-mail but URL-affecting: `FRONTEND_URL`, `APP_PUBLIC_URL`.

---

## 10. Email Templates

Engine: **Python functions** returning `(subject, text, html)` via shared `render_landing_email` (manual HTML strings + `html.escape`). **Not Jinja/Mako/Django.**

| Template | Business event | Variables | Caller |
|---|---|---|---|
| `templates/account_confirmation.py` | Account / email confirmation after register | **Required:** `confirm_url`, `ttl_hours` | `EmailService.send_account_confirmation` |
| `templates/password_reset.py` | Password reset request | **Required:** `reset_url`, `ttl_minutes` | `EmailService.send_password_reset` |
| `templates/layout.py` | Shared layout (not a business template) | subject, heading, intro, cta_label, cta_url, footer; optional `fallback_label` | both templates |

| Property | Finding |
|---|---|
| Subjects | Confirmation: `Подтвердите аккаунт — RefIQ`; Reset: `Восстановление пароля — RefIQ` |
| HTML + text | Both always produced |
| Locale | Hardcoded Russian (`lang="ru"` in HTML); no i18n framework |
| Versioning | **Not found** |
| Localization | **Not found** (single RU copy) |
| Text fallback | Yes — plain text sibling |
| Shared layout | Yes — `layout.render_landing_email` |
| Reusable components | Layout only; no partial components beyond that |

---

## 11. Email Business Flows

| Event | Caller | Recipient | Template | Provider call |
|---|---|---|---|---|
| Account confirmation | `AuthService.register` → `EmailConfirmationService.issue` via `POST /api/v1/auth/register` | New user email | `render_account_confirmation` | `YandexCloudPostboxProvider.send` / Disabled |
| Password reset | `PasswordResetService.request_reset` via `POST /api/v1/auth/forgot-password` | Active user email (if exists) | `render_password_reset` | same |

No other transactional email scenarios found (no invitations, offer approval, payout, billing, partner/business notification emails).

---

## 12. Transaction Boundaries

`get_db` commits **after** the route handler returns successfully (`database.py`). Email send runs **inside** the handler, after `flush`, **before** that commit.

| Flow | Model |
|---|---|
| Register → confirmation email | **B (effectively inside open transaction)** + fail-open: send exceptions caught in `issue`, user still created; then request commits |
| Forgot-password → reset email | **B** + fail-open: exceptions caught; always returns `GENERIC_OK`; then commit |

Not A (before any DB writes): tokens are flushed before send.  
Not C (after commit): send happens before `get_db` commit.  
Not D (background task): synchronous await in request.

### Potential consistency issues (inventory only — not fixed)

1. **`business state saved, but email not sent`**
   - Register: token + user flushed; email fails → exception swallowed → commit still happens → user exists without delivered mail (`email_confirmation.py`).
   - Forgot-password: token committed even if send fails; response still OK (`password_reset.py`).
   - Provider not configured: same fail-open path.
2. **`email sent, but DB transaction rolled back`**
   - Possible if send succeeds then a later step in the same request fails before `get_db` commit (less common on these endpoints because little happens after send; still architecturally open because send is pre-commit).
   - Register path: after `issue`, `refresh` runs; if that failed after a successful send, rollback could orphan a delivered email without durable token — theoretical given current code shape.

---

## 13. Background Processing

| Mechanism | Used for email? | Notes |
|---|---|---|
| FastAPI `BackgroundTasks` | **No** | Used for AI creative generation (`ai/jobs.py`, creatives routers) |
| asyncio tasks (lifespan) | **No** | Promo pump + finance jobs in `main.py` lifespan |
| Celery | **Not found** | — |
| Redis | Sessions + forgot-password rate limit; **not** mail queue | `password_reset.py`, sessions |
| RabbitMQ | **Not found** | — |
| Kafka | Present in `docker-compose.infra.yml`; **no api consumer/producer usage found for mail** | infra only |
| APScheduler / cron | **Not found** as library; finance loop is asyncio sleep 60s | `main.py` |
| DB-backed queue / outbox | `outbox_events` table + `emit_event` helper exist; **`emit_event` has no callers**; **no worker processes outbox**; **not used for email** | `common/events.py`, `system/models.py` |
| Custom mail worker | **Not found** | — |

**Conclusion:** Email has **no** background processing, retry queue, or delivery worker today.

---

## 14. Internal Service Communication

| Pattern | Finding |
|---|---|
| Dedicated `api → internal service` HTTP client | **Not found** |
| Tracker | Click redirect lives **inside** `api` (`modules/tracker/router.py`); separate tracker repo is out of this audit scope; no HTTP client to tracker found in `api` email path |
| External HTTP | Ad-hoc `httpx.AsyncClient(timeout=…)` per integration (AI, DaData, TBank) |
| boto3 | S3 (`assets/s3.py`) and Postbox (`email/postbox.py`) |
| Auth to externals | Provider API keys in Settings |
| Service tokens / JWT S2S | **Not found** for internal services |
| Correlation / request ID | `RequestIDMiddleware` sets `request.state.request_id` + `X-Request-ID` response header; **not passed into email provider calls** |
| Connection pooling | New `httpx.AsyncClient` per call in several providers; boto3 client singleton for Postbox |
| Error handling | Domain-specific exceptions (`AiError`, finance errors, `EmailSendError`) |

Most common external pattern: **short-lived httpx client + timeout + optional manual retry loop**. Email uniquely uses **boto3 sesv2**.

No existing `api → mail` pattern to copy; only adjacent patterns above.

---

## 15. Configuration

| Topic | Finding |
|---|---|
| Location | `api/app/core/config.py` — single `Settings(BaseSettings)` |
| pydantic-settings | Yes (`SettingsConfigDict(env_file=".env", extra="ignore")`) |
| Hierarchy / nested settings | Flat fields + `@property` helpers (`postbox_enabled`, `public_app_url`, …) |
| Env separation | `APP_ENV` (`development` / `production` checks e.g. docs URL, finance test router) |
| `.env` | Loaded by pydantic-settings; compose injects `env_file: .env` + overrides |
| Secrets | Env vars; empty string defaults for keys |

**Existing pattern a new service would mirror (descriptive, not a design):** flat `Settings` class with env-backed fields, feature `*_enabled` properties from credential presence, defaults in code, `.env.example` documentation.

---

## 16. Logging

| Topic | Finding |
|---|---|
| Library | structlog |
| Configure processors / JSONRenderer | **No explicit `structlog.configure` found** in `api` — relies on defaults / environment |
| HTTP logs | `StructuredLoggingMiddleware`: method, path, status, duration_ms, request_id, user_id |
| Email logs | `email_send_started/succeeded`; errors via `log_email_error` (structlog + stderr print + traceback) |
| PII in email logs | Logs **email domain only** (`email_domain`), subject, kind — not full recipient address |
| Correlation | `request_id` on HTTP; **not wired into email log events** |
| Automatic secret redaction | **Not found** (no filter masking tokens/API keys in logs) |

---

## 17. Observability

| Mechanism | Status | Source |
|---|---|---|
| Prometheus / `/metrics` | **Not found** | — |
| Health | `GET /health` → `{"status":"ok"}` | `main.py` |
| Readiness | `GET /ready` — DB `SELECT 1` + Redis ping | `main.py` |
| Liveness | No separate probe beyond `/health` | — |
| OpenTelemetry / tracing | **Not found** | — |
| Sentry | **Not found** | — |
| Admin email health | Overview `email_sending` based on `postbox_enabled` (configured vs not); when enabled reports healthy **without** last-send timestamp | `admin/queries/overview.py` |

Docker Compose services **do not** define healthchecks on `api` (infra services do).

---

## 18. Error Handling

| Layer | Pattern |
|---|---|
| HTTP domain | `AppError` / `NotFoundError` / `ConflictError` / `ForbiddenError` → JSON `{error:{code,message,request_id}}` | `core/exceptions.py` |
| Validation | Pydantic `ValidationError` → 422 | same |
| Unhandled | 500 `INTERNAL_ERROR` | same |
| Email | `EmailError` hierarchy **not** registered with FastAPI handlers; callers catch broad `Exception` and log | `email/errors.py`, auth services |
| Retryable classification | Exists for **AI** (`is_retryable_provider_error`) and DaData status set — **not for email** | `ai/errors.py`, `dadata.py` |

Reusable for mail service (existing): structured `code` + `message` + `status_code` errors; provider-specific subclasses with metadata (AI pattern); logging helpers that avoid full email addresses.

---

## 19. Security Relevant to Mail Service

| Aspect | Finding |
|---|---|
| User auth | Session cookie (`refiq_session`) + Redis sessions |
| Authorization | Role/workspace permissions modules |
| Service-to-service auth | **Not found** |
| Secrets | Env-based Postbox keys; HMAC `SECRET_KEY` for token hashes |
| Tokens in email | **Plaintext** confirmation/reset tokens only in **URL query**; DB stores **HMAC-SHA256 hash** only |
| CORS | Configured origins for public API |
| Admin isolation | `admin-api` on loopback `127.0.0.1:8002`, internal network only |
| IP restrictions | Not for email; X-Forwarded-For used for clicks |
| Internal network | Compose `refiq_internal` shared with postgres/redis/kafka/clickhouse |

---

## 20. Docker & Deployment

### Dockerfile (`api/Dockerfile`)
| Item | Value |
|---|---|
| Base | `python:3.12-slim` |
| Packages | gcc, libpq-dev via apt |
| Install | `pip install --no-cache-dir .` from `pyproject.toml` |
| User | `appuser` (non-root) |
| Workdir | `/app` |
| Entrypoint | `./entrypoint.sh` (admin image override `./entrypoint-admin.sh`) |
| Command | Implicit via entrypoint → uvicorn |
| Healthcheck | **None in Dockerfile** |
| Volumes | Assets volume at runtime (`/data/assets`) |
| Port | 8000 |

Reusable shape for another Python service: slim 3.12 image, non-root user, pip install from pyproject, entrypoint script.

### Compose
- App: `docker-compose.yml` — services `api`, `frontend`, `admin-api`, `admin-front`; networks `refiq_internal` (external) + `external`; env from `.env`.
- Infra: `docker-compose.infra.yml` — `postgres`, `redis`, `kafka`, `clickhouse`.
- No reverse proxy / monitoring stack in these compose files.
- `api` has **no** `depends_on` health gate in compose (relies on operator starting infra first).

### Deployment
- Primary local/prod-like path observed: **Docker Compose**.
- Kubernetes / Helm / GitHub Actions / GitLab CI for this repo: **Not found** under `app/` (no `.github/workflows` at app root).
- Pattern to mirror: separate infra compose + app compose; service DNS names (`postgres`, `redis`); `env_file` + environment overrides; migrations on container start.

---

## 21. Testing Architecture

| Topic | Finding |
|---|---|
| Framework | pytest + pytest-asyncio (`asyncio_mode = auto`) |
| DB | In-memory/async SQLite via aiosqlite in `conftest` (JSONB→JSON compile); creates all tables |
| HTTP | httpx `ASGITransport` against FastAPI app |
| Factories / testcontainers | **Not found** as libraries |
| Email mocking | `set_email_provider` + in-memory capturing / failing / hanging providers |

### Email tests

| File | What it tests | What is mocked |
|---|---|---|
| `tests/test_email_confirmation.py` | Register creates user + sends mail; login blocked until confirm; confirm; confirm+login; invalid/expired tokens; HTML style; hang/timeout still returns register OK | Fake `EmailProvider` via `set_email_provider`; timeout via monkeypatch `EMAIL_SEND_TIMEOUT_SECONDS` |
| `tests/test_password_reset.py` | Forgot known/unknown (same response); token hashing/expiry; reset once; invalid/expired; password policy; provider failure does not leak; invalidate previous token; concurrent single-use; HTML style | Capturing / `FailingEmailProvider` via `set_email_provider` |

---

## 22. Existing Idempotency Patterns

| Pattern | Where | Mail relevance |
|---|---|---|
| `financial_idempotency_keys` + `claim_idempotency` | Finance payouts/billing | DB unique key claim with nested transaction |
| Unique `idempotency_key` columns | invoices, billing_transactions, payouts | UniqueConstraint |
| Notification `dedupe_key` | `uq_notifications_user_dedupe` | In-app only |
| Token hash unique indexes | password_reset / email_confirmation | Prevents duplicate hash rows; **does not** dedupe email sends |
| Request ID | Middleware UUID | Observability, not idempotency store |

**No mail-send idempotency key exists today.** Closest reusable idea: finance `claim_idempotency` / unique business keys — currently finance-scoped only.

---

## 23. Existing Retry Patterns

| Integration | Library / approach | Count / backoff | Retryable errors |
|---|---|---|---|
| Email / Postbox | botocore retries max_attempts=1 | No app retry | N/A |
| AI OpenAI/DeepSeek/Yandex | Manual while-loop + httpx | `AI_MAX_RETRIES` / `DEEPSEEK_MAX_RETRIES` default **1** (i.e. up to 2 attempts); no exponential backoff found | 429/5xx except quota/model_not_found (`is_retryable_provider_error`) |
| DaData lookup | Manual `for attempt in range(2)` | 2 attempts; no backoff | HTTP 500/502/503/504 + timeouts |
| TBank | httpx single call | Timeout only; no retry loop found in skim of provider | — |
| Postbacks | Attempt model exists | Domain-specific; not email | — |

**No tenacity/celery retry for email.**

---

## 24. Dependencies Related to Mail

| Dependency | Used where | Needed in API after mail extraction? |
|---|---|---|
| `boto3` | Postbox **and** S3 assets | **Yes** (S3 remains) |
| `botocore` (transitive) | Postbox Config/errors | Via boto3 for S3 |
| `email-validator` | Pydantic EmailStr validation | **Yes** (auth schemas) |
| Python stdlib `html` | Template escaping | Moves with templates |
| `httpx` | Not used by email | Stays for other integrations |
| Jinja2 / SMTP libs | **Not present** | — |

---

## 25. Sensitive Data Considerations

Present in email-related flows (do **not** store plaintext in a future `mail_log` without explicit policy):

| Data | In email? | In DB |
|---|---|---|
| Password reset **plaintext token** | Yes, in `reset_url` query | No — only HMAC hash |
| Account confirmation **plaintext token** | Yes, in `confirm_url` | No — only HMAC hash |
| User email address | Recipient | `users.email` |
| Password / password_hash | Not in email | hash only |
| Auth session IDs | Not in these emails | Redis sessions |
| Bank / payout data | **Not in any email found** | finance tables |

Also avoid logging full recipient emails (current code logs domain only — good pattern to preserve).

---

## 26. API Code That Will Potentially Move to Mail

- Entire `app/modules/email/` package (provider, service, templates, dto, errors, log, deps)
- Postbox-specific Settings fields and `postbox_enabled`
- boto3 sesv2 usage for mail (S3 stays)
- Email send timeout configuration
- Provider MessageId handling / future bounce webhooks / send logging / retry queue (none exist yet — would be born in mail)
- Admin “is Postbox configured” check may move to mail health or stay as remote probe

---

## 27. Code That Must Remain in API

- Decision to notify (register / forgot-password)
- User lookup, status checks, rate limiting (forgot-password Redis)
- Generation and storage of **token hashes**; building public URLs using `public_app_url`
- Auth HTTP endpoints and responses (including generic OK / confirmation messages)
- `EmailConfirmationToken` / `PasswordResetToken` models and migrations
- Activation / password change business logic
- In-app `notifications` module (unrelated channel)

---

## 28. Existing Patterns Mail Service Should Follow

(Existing conventions only — not a mail design.)

- Python 3.12 + FastAPI + uvicorn workers=1 entrypoint
- pydantic-settings flat `Settings` + env_file
- Async SQLAlchemy + Alembic numbered migrations + migrate-on-start
- Numeric BigInteger IDs via `pk_column`/`fk_column`
- Timestamptz; snake_case tables; `ix_` / `uq_` names
- structlog + `X-Request-ID` middleware pattern
- `/health` and `/ready` endpoints
- Domain error objects with `code` / `message` / HTTP status for public APIs
- Docker Compose service on `refiq_internal`
- pytest-asyncio + provider injection seams for tests (`set_email_provider`-style)
- Fail-soft logging helpers that avoid full email addresses
- Feature enablement via “credentials present” properties

---

## 29. Missing Information / Uncertainties

- Production deployment beyond Docker Compose (K8s/Helm/CI): **Cannot be determined from current repository** (`app/`).
- Whether Yandex Postbox bounce/complaint webhooks are used outside this repo: **Not found** in `api`.
- Actual structlog formatter in production (JSON vs console): **Cannot be determined** — no `structlog.configure` in repo.
- Whether `outbox_events` was planned for email: table exists, **no producers/consumers** found.
- Whether separate `tracker` service currently calls `api` for mail: **Not examined** (out of scope; no client in `api`).
- Real deployed values of `EMAIL_FROM*` / Postbox credentials: intentionally not read; presence only via code defaults / `.env.example`.
- Kafka usage by any RefIQ component for notifications: **Not found** in `api` code.

---

## 30. Source File Index

```text
api/pyproject.toml
api/Dockerfile
api/entrypoint.sh
api/entrypoint-admin.sh
api/alembic.ini
api/alembic/env.py
api/alembic/script.py.mako
api/alembic/versions/001_initial.py
api/alembic/versions/018_password_reset_tokens.py
api/alembic/versions/019_email_confirmation_tokens.py
api/alembic/versions/032_audit_events.py
api/app/main.py
api/app/core/config.py
api/app/core/database.py
api/app/core/exceptions.py
api/app/core/middleware.py
api/app/core/ids.py
api/app/common/events.py
api/app/modules/email/__init__.py
api/app/modules/email/service.py
api/app/modules/email/postbox.py
api/app/modules/email/provider.py
api/app/modules/email/deps.py
api/app/modules/email/dto.py
api/app/modules/email/errors.py
api/app/modules/email/log.py
api/app/modules/email/templates/layout.py
api/app/modules/email/templates/account_confirmation.py
api/app/modules/email/templates/password_reset.py
api/app/modules/auth/router.py
api/app/modules/auth/service.py
api/app/modules/auth/email_confirmation.py
api/app/modules/auth/password_reset.py
api/app/modules/auth/models.py
api/app/modules/system/models.py
api/app/modules/notifications/service.py
api/app/modules/notifications/models.py
api/app/modules/finance/idempotency.py
api/app/modules/ai/errors.py
api/app/modules/ai/jobs.py
api/app/modules/finance/lookup/providers/dadata.py
api/app/modules/assets/s3.py
api/app/admin/queries/overview.py
api/tests/conftest.py
api/tests/test_email_confirmation.py
api/tests/test_password_reset.py
docker-compose.yml
docker-compose.infra.yml
.env.example
```
