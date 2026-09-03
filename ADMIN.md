# RefIQ Admin Console

Internal operational console for RefIQ staff. It is **not** the partner/business cabinet.

## URLs

| Environment | UI | API |
| --- | --- | --- |
| Production (internal network / VPN only) | `https://admin.int.refiq.ru/` | `https://admin.int.refiq.ru/api/admin/v1/*` |
| Local Docker | `http://127.0.0.1:3100/` | `http://127.0.0.1:8002/api/admin/v1/*` |
| Local Vite | `http://localhost:5174/` | proxied to `localhost:8002` |

Public product stays on `app.refiq.ru` / `api.refiq.ru` (`localhost:3000` / `localhost:8000`). Admin routes are **not** mounted on the public FastAPI app.

## Architecture

```text
api/app/admin/          isolated admin module inside the existing API codebase
  app.py                FastAPI entrypoint: app.admin.app:app
  api/                  REST routers under /api/admin/v1
  auth/                 AdminUser, cookie session (Redis prefix admin_session:)
  audit/                immutable admin_audit_events
  queries/              read-side DTOs (JOIN/aggregation, no write rules)
  services/actions.py   explicit domain actions via existing services
  bootstrap.py          first-admin CLI

admin-front/            separate React + Vite app (own bundle, own image)
```

Both deployments share PostgreSQL and Alembic. Admin writes call domain services; they never run arbitrary `UPDATE`.

## Local run

From `/Users/pavel/Projects/refiq/app` (or the compose root):

```bash
docker compose up -d --build postgres redis api admin-api admin-front
```

Public UI remains `localhost:3000`. Admin binds to loopback only:

* UI `127.0.0.1:3100` (nginx also proxies `/api` to `admin-api`)
* API `127.0.0.1:8002`

Without Docker:

```bash
# API repo
uvicorn app.admin.app:app --host 127.0.0.1 --port 8002 --reload

# admin-front
cd admin-front && npm install && npm run dev   # Vite :5174 → /api → :8002
```

## First admin account

No password is stored in the repository.

```bash
docker compose exec admin-api python -m app.admin.bootstrap create-admin --email ops@refiq.ru --role super
# password from ADMIN_BOOTSTRAP_PASSWORD or an interactive prompt (min 8 chars)
```

Roles:

* `support` → `ADMIN_READ`, `ADMIN_OPERATIONS`
* `finance` → `ADMIN_READ`, `ADMIN_FINANCE`
* `super` → all, including `ADMIN_SUPER`

Backend permission checks are authoritative. The UI hides finance/actions the session cannot use.

## Authentication

Separate `admin_users` table. A BUSINESS/PARTNER user is **not** an admin.

Browser session cookie:

* name `ADMIN_SESSION_COOKIE_NAME` (default `refiq_admin_session`)
* HttpOnly, SameSite=Strict, path `/`
* **no** `Domain=.refiq.ru`
* Secure in production (`ADMIN_SESSION_COOKIE_SECURE` or `APP_ENV=production`)

MFA can be added later on `AdminAuthService.login` without changing the cookie contract.

## Global Search

`GET /api/admin/v1/search?q=`

Exact identifiers first (no `%LIKE%` on rqcid / shortCode / numeric IDs / normalized email / domain). Human-readable names use escaped `LIKE`. An rqcid hit includes `primary_action: open_trace`.

## rqcid Trace

`GET /api/admin/v1/trace/{rqcid}` and UI `/trace/{rqcid}` (also `/admin/trace/{rqcid}`).

The API assembles TrackingLink → Click → PostbackAttempt → Conversion → Commission → Payout from PostgreSQL. Behavioral/SDK events come from `ClickstreamProvider`. ClickHouse is **not** wired; the provider returns no fake events and the UI shows SDK as unavailable.

Diagnostic summary is deterministic from structured statuses and reason codes (not logs, not AI).

`RqcidLink` always navigates to `/trace/{rqcid}`.

## Adding an admin action

1. Add an explicit `POST /api/admin/v1/.../{id}/<verb>` that accepts `{ "reason": "..." }`.
2. Implement it on `AdminActionService` using existing domain services/status enums.
3. Call `record_admin_action(...)` in the same transaction.
4. Reject empty reason (`REASON_REQUIRED`).
5. Do **not** add `PATCH /admin/entity/{id}` or hard delete.
6. Do **not** update financial amounts with raw SQL.

Audit UI is read-only (`Administration → Audit`).

## Deployment isolation

* Public process: `app.main:app` (`entrypoint.sh`)
* Admin process: `app.admin.app:app` (`entrypoint-admin.sh`)
* Compose services `admin-api` and `admin-front` sit on the `internal` network only and bind `127.0.0.1` (`3100` UI, `8002` API)
* `admin-front` nginx proxies `/api` to `admin-api`, never to `api`
* Production: attach `deploy/internal/nginx-admin.int.refiq.ru.conf` to an **internal** load balancer / VPN ingress. Do not publish it on the public ingress used by `api.refiq.ru`

This repository has no Kubernetes manifests. Equivalent isolation is separate Deployments/Services plus an internal Ingress that is not internet-facing.

## Tests

```bash
cd api && pytest tests/test_admin.py
cd admin-front && npm test
```
