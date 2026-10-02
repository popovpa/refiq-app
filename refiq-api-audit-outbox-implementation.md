# RefIQ API: Transactional Outbox для audit events

Read-only отчёт. Файл не предназначен для git.

## Architecture

Пилот ограничен сущностью Offer. HTTP-запрос не вызывает Kafka. Изменение Offer и запись outbox находятся в одной PostgreSQL-транзакции `get_db` (commit в конце запроса). Отдельный publisher внутри процесса API забирает непубликованные строки и отправляет их в Kafka только после commit.

```text
Offer mutation (create / update / admin pause|activate)
        ↓
PostgreSQL transaction
 ├── Offer (+ существующая запись audit_events для Admin UI)
 └── INSERT outbox_event
        ↓
COMMIT
        ↓
Outbox Publisher (api и admin-api)
        ↓
Kafka topic audit-events
        ↓
data-ingestor-audit → audit_log   (вне этого изменения)
```

Существующая таблица `audit_events` и Admin → Audit не заменялись: admin console уже читает её. Новая цепочка в `audit_log` идёт только через Kafka. API не пишет в `audit_log` и не вызывает data-ingestor.

Старая заготовка `outbox_events` (другая схема, без publisher) не используется этим потоком и не изменялась.

## Files changed

Миграция:

- `api/alembic/versions/033_audit_outbox_event.py`

Контракт и контекст:

- `api/app/modules/audit/factory.py` — `AuditEventFactory`
- `api/app/modules/audit/offer_state.py` — allowlist полей Offer
- `api/app/modules/audit/context.py` — `correlation_id`, `account_id`
- `api/app/modules/audit/events.py` — actor type `SERVICE`
- `api/app/modules/offers/audit.py` — явная постановка событий из use case Offer

Outbox:

- `api/app/modules/audit/outbox/models.py` — `AuditOutboxEvent`, таблица `outbox_event`
- `api/app/modules/audit/outbox/repository.py`
- `api/app/modules/audit/outbox/publisher.py`
- `api/app/modules/audit/outbox/retry.py`
- `api/app/modules/audit/outbox/metrics.py`
- `api/app/modules/audit/outbox/serialize.py`

Kafka и worker:

- `api/app/kafka/producer.py` — `AiokafkaAuditProducer`
- `api/app/workers/outbox_publisher.py`
- `api/app/main.py`, `api/app/admin/app.py` — lifecycle publisher

Конфигурация:

- `api/app/core/config.py`
- `api/pyproject.toml` — зависимость `aiokafka`
- `docker-compose.yml` — `KAFKA_BOOTSTRAP_SERVERS=kafka:19092` для `api` и `admin-api`
- `.env.example`

Тесты:

- `api/tests/test_audit_outbox.py`
- `api/tests/conftest.py`, `api/alembic/env.py` — регистрация модели

## Outbox schema

Таблица `outbox_event` (Alembic `033`, после `032`).

```text
id              BIGINT PK
event_id        VARCHAR(64) NOT NULL  UNIQUE (uq_outbox_event_event_id)
topic           VARCHAR(128) NOT NULL
event_type      VARCHAR(80) NOT NULL
aggregate_type  VARCHAR(50) NOT NULL
aggregate_id    VARCHAR(64) NOT NULL
partition_key   VARCHAR(64) NOT NULL
payload         JSONB NOT NULL
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
published_at    TIMESTAMPTZ NULL
retry_count     INTEGER NOT NULL DEFAULT 0
last_error      TEXT NULL
next_retry_at   TIMESTAMPTZ NULL
```

Индекс publisher — partial index, только непубликованные строки:

```sql
CREATE INDEX ix_outbox_event_pending
    ON outbox_event (next_retry_at, created_at)
    WHERE published_at IS NULL;
```

`published_at` остаётся NULL, пока publisher не получит Kafka ACK и не закоммитит отметку. `event_id` генерируется один раз (UUID) и хранится и в колонке, и в payload. Повторная отправка читает тот же payload.

## Audit contract

JSON, `schemaVersion = 1`. Поля совпадают с контрактом `data-ingestor` (`AuditEventMapper`): обязательны `schemaVersion`, `eventId`, `eventType`, `occurredAt`, `actor.type`, `entity.type`, `entity.id`, `action`. `accountId` и `actor.id` опускаются, если их нет.

```json
{
  "schemaVersion": 1,
  "eventId": "550e8400-e29b-41d4-a716-446655440000",
  "eventType": "OFFER_UPDATED",
  "occurredAt": "2026-10-03T12:30:15.123Z",
  "accountId": "123",
  "actor": {"type": "USER", "id": "456"},
  "entity": {"type": "OFFER", "id": "789"},
  "action": "UPDATE",
  "requestId": "…",
  "correlationId": "…",
  "ipAddress": "127.0.0.1",
  "userAgent": "…",
  "changes": {"holdPeriodDays": {"before": 7, "after": 14}},
  "before": {"holdPeriodDays": 7},
  "after": {"holdPeriodDays": 14},
  "metadata": {
    "sourceService": "api",
    "sourceOperation": "offers.update",
    "businessId": "123"
  }
}
```

Идентификаторы в контракте — строки. Числовые id API (`offer.id`, `user.id`, `business.id`) приводятся к строке. Отдельного префикса `off_` / `usr_` в API нет, поэтому он не выдумывался. `eventId` — UUID: в проекте нет генератора публичных id для событий; request id уже UUID.

`accountId` для Offer — id бизнеса-владельца. `correlationId` равен `requestId`: отдельного correlation id в API нет. IP берётся из socket peer (`request.client.host`). `X-Forwarded-For` не читается: доверенный proxy allowlist не настроен.

Actor types, которые принимает ingestor: `USER`, `ADMIN`, `SYSTEM`, `SERVICE`, `API_CLIENT`. Для кабинета бизнеса — `USER` и id пользователя. Для admin pause/activate — `ADMIN` и id admin user. Id не подставляется, если его нет.

Allowlist полей Offer (camelCase), плюс `commissionRules` (`type`, `value`, `currency`). Секреты в этот список не входят; неизвестные ключи, включая `password` / `token` / `api_key`, отбрасываются. Поверх allowlist остаётся существующий sanitizer.

Статусы пишутся как в модели: `draft`, `active`, `paused`, `closing`, `archived`.

## Offer events

Аудит ставится явно из `record_offer_created` / `record_offer_mutations`, не из ORM listener и не из контроллера напрямую. Контроллеры по-прежнему вызывают эти функции внутри той же сессии.

| Операция | eventType | action |
| --- | --- | --- |
| Создание | `OFFER_CREATED` | `CREATE` |
| Обычное изменение полей | `OFFER_UPDATED` | `UPDATE` |
| Смена status, включая admin pause/activate | `OFFER_STATUS_CHANGED` | `STATUS_CHANGE` |
| Hold | `OFFER_HOLD_CHANGED` | `UPDATE` |
| Geo / allowed / forbidden traffic | `OFFER_TRAFFIC_POLICY_CHANGED` | `UPDATE` |
| access policy / visibility | `OFFER_ACCESS_POLICY_CHANGED` | `UPDATE` |
| product | `OFFER_PRODUCT_CHANGED` | `UPDATE` |

CREATE: `before = null`, `changes = null`, `after` — allowlist-снимок после создания, включая commission rules.

UPDATE / STATUS_CHANGE: `changes`, `before` и `after` содержат только реально изменившиеся поля. Если снимок не изменился, событие не создаётся.

Изменение commission rules добавляется к `OFFER_UPDATED` (вместе с `termsVersion`, который и так увеличивается при смене правила). Если других полей нет, пишется отдельный `OFFER_UPDATED`.

Partner approve/reject — это `OfferPartnerAccess`, не мутация Offer. Отдельные `APPROVE` / `REJECT` / `DELETE` для Offer не добавлялись: таких операций у сущности нет. Archive/pause/close проходят как смена status.

## Transaction boundaries

Граница — сессия запроса (`get_db` / admin dependency): commit один, в конце успешного запроса.

`record_offer_*` делает `session.add` + `flush` для outbox в этой же сессии и сам не коммитит. Если insert outbox падает, исключение выходит из запроса, `get_db` делает rollback, и изменение Offer откатывается вместе с локальной записью `audit_events`.

Незакоммиченная пара Offer + outbox не видна другой сессии. После commit видны оба.

Kafka в этой транзакции не участвует. Недоступный брокер не мешает commit.

`AUDIT_OUTBOX_ENABLED=false` отключает только insert outbox и старт publisher. Создание и изменение Offer продолжают работать. Запись в существующую `audit_events` при этом сохраняется.

## Kafka

- Topic: `audit-events` (`AUDIT_KAFKA_TOPIC`, default `audit-events`).
- Key: `partition_key` = `aggregate_id` = строковый `offer.id`. Все события одного Offer используют один key.
- Value: UTF-8 JSON bytes, каноническая сериализация (`sort_keys`) из сохранённого payload.
- Producer (`aiokafka`): `acks=all`, `enable_idempotence=true`. `retries` не выставляется в 0. Kafka transactions не используются.
- Bootstrap: `KAFKA_BOOTSTRAP_SERVERS`, default `localhost:9092`. В compose для контейнеров API — `kafka:19092` (listener `PLAINTEXT` брокера).
- ACK: `send_and_wait`. `published_at` пишется только после успешного await и commit этой отметки.

## Publisher

Процесс: цикл в `api` и в `admin-api`. Отдельного сервиса нет. В тестах цикл не стартует (`has_test_job_runner`).

Poll:

```text
published_at IS NULL
AND (next_retry_at IS NULL OR next_retry_at <= now())
AND нет более старой unpublished строки с тем же partition_key
ORDER BY created_at, id
LIMIT AUDIT_OUTBOX_BATCH_SIZE   (default 100)
```

На PostgreSQL к выборке добавляется `FOR UPDATE SKIP LOCKED`. Две реплики не берут одну и ту же строку одновременно. Более новое событие Offer не уходит, пока более старое того же Offer не опубликовано, поэтому `OFFER_CREATED` не обгоняется последующим `OFFER_UPDATED` при retry.

Интервал опроса: `AUDIT_OUTBOX_POLL_INTERVAL` (default 2 секунды). Ноль заменяется на 50 мс, busy-loop нет.

Retry: `published_at` остаётся NULL, `retry_count += 1`, `last_error` заполняется усечённым текстом ошибки, `next_retry_at = now + delay`. Расписание при base delay 1s: 1, 5, 15, 30, 60 секунд, дальше держится 60 × base. Строка не удаляется. `AUDIT_OUTBOX_MAX_RETRIES` (default 10) — порог error-лога, не остановка доставки: после восстановления Kafka backlog уходит.

Cleanup: `delete_published_before`, только если `AUDIT_OUTBOX_RETENTION_SECONDS > 0`. Default `0` — cleanup выключен.

Shutdown: выставляется stop, текущий цикл дорабатывается, новый batch не берётся. Ожидание ограничено `AUDIT_OUTBOX_SHUTDOWN_TIMEOUT` (default 10s), затем task отменяется. Неопубликованные строки остаются в таблице. Повторная отправка после рестарта допустима и несёт тот же `eventId`.

Метрики — in-process counters/gauges в том же стиле, что `app.modules.finance.metrics`. Prometheus в API нет, новый стек не добавлялся.

```text
outbox.pending
outbox.published
outbox.publish.errors
outbox.retries
outbox.publish.latency
outbox.oldest.pending.age
```

Лог INFO/WARNING содержит `event_id`, `event_type`, `aggregate_type`, `aggregate_id`, `topic`, `retry_count`, `request_id`, `correlation_id`. Полный payload не логируется.

## Failure scenarios

Kafka unavailable. Запрос Offer коммитит сущность и outbox. Publisher ловит ошибку, увеличивает `retry_count`, пишет `last_error`, ставит `next_retry_at`. После восстановления следующий poll, когда `next_retry_at` наступил, публикует backlog.

API упал до Kafka send. `published_at` NULL. После старта publisher отправляет исходный payload.

API упал после Kafka ACK, до записи `published_at`. Строка снова unpublished. Повторная отправка содержит тот же `eventId`. Это at-least-once. Exactly-once между PostgreSQL и Kafka не строится. Идемпотентность на стороне `data-ingestor-audit` — по `event_id`.

Duplicate publish. Тот же outbox row, тот же `eventId`, тот же key.

PostgreSQL failure на insert outbox. Rollback всей транзакции, включая изменение Offer.

Несколько реплик. `FOR UPDATE SKIP LOCKED` на PostgreSQL. SQLite в тестах этот clause не выполняет; контракт проверяется компиляцией SQL под PostgreSQL dialect и отдельным тестом, что более старая unpublished строка блокирует более новую того же Offer.

## Tests

Файл `api/tests/test_audit_outbox.py`. Проект не использует Testcontainers; suite живёт на SQLite, Kafka в unit-тестах заменена recording producer. Отдельный тест ходит в живой брокер, если `KAFKA_BOOTSTRAP_SERVERS` доступен.

Покрыто:

- Offer и outbox не видны до commit и видны вместе после commit.
- Ошибка insert outbox откатывает смену status Offer.
- Ровно один `OFFER_CREATED` на создание, `before = null`, `after` со снимком и commission rules.
- `OFFER_HOLD_CHANGED` с `before` / `after` / `changes`.
- `OFFER_STATUS_CHANGED` / `action = STATUS_CHANGE`.
- No-op patch не добавляет outbox row.
- `AUDIT_OUTBOX_ENABLED=false` не мешает создать Offer и не пишет outbox.
- HTTP create не вызывает Kafka producer.
- Ошибка Kafka: `published_at` NULL, `retry_count` и `last_error` заполнены, слишком ранний poll ничего не шлёт, после `next_retry_at` уходит тот же `eventId` и key = offer id.
- Потеря ACK после успешного send: повтор несёт тот же `eventId`.
- Порядок одного Offer и общий Kafka key.
- Admin actor `ADMIN`.
- Cleanup удаляет только давно опубликованные строки.
- Shutdown завершает текущий цикл и останавливает producer.
- Producer конфигурируется с `acks=all` и `enable_idempotence=true`.
- Live round-trip в локальный Kafka `audit-events`: payload и key проверены, `published_at` выставлен. Прогон прошёл (брокер был доступен).

`tests/test_audit.py` (существующий audit_events / Admin UI) — passed.

Полный `pytest` API: **417 passed, 6 failed**. Шесть падений не идут через outbox:

- `test_offer_approval_request.py`, `test_offers.py::test_partner_approval_and_link_flow`, оба теста `test_partner_privacy.py` — `403 SAME_USER_BUSINESS_MEMBER` на approve/invite. Это текущий `assert_not_self_deal`: действующий участник бизнеса, приглашающий другого партнёра, попадает в этот код. Outbox на этом пути не пишется.
- `test_promo_kit.py` (2 теста) — `502 AI_INVALID_RESPONSE` у fake provider на regenerate. К аудиту Offer не относится.

## Regression

Контракт HTTP Offer не менялся: create/update по-прежнему возвращают те же поля, commit по-прежнему один на запрос. Классификация событий в `audit_events` сохранена, Admin → Audit events продолжает читать эту таблицу. No-op update по-прежнему не создаёт audit noise. Partner approve/reject, каталог и ссылки не получили новых audit event.

Дополнительная запись — только `outbox_event` в той же транзакции, и только когда флаг включён. При выключенном флаге мутации Offer остаются прежними.

## Remaining work

Не делалось в этой задаче:

1. Проверить end-to-end: API → outbox → Kafka → data-ingestor-audit → audit_log.
2. Реализовать Admin → Аудит поверх `audit_log` (текущий Admin UI читает API-таблицу `audit_events`).
3. После проверки пилота Offer постепенно подключать: Account, Product, Partner relations, TrackingLink, Campaign, Conversion, Commission, Payout, Integrations, Permissions.
