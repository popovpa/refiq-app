# RefIQ Mail Kafka Readiness Inventory

Read-only inventory of Kafka infrastructure and `api` Kafka/outbox integration. No mail design. Sources: compose, application config, migrations, producers/consumers as used for conventions only.

## 1. Executive Summary

- Kafka version: **4.0.0** (`apache/kafka:4.0.0`).
- Mode: **KRaft** (broker+controller), no ZooKeeper service.
- Internal endpoint for containers on `refiq_internal`: **`kafka:19092`** (listener `PLAINTEXT`).
- Host/external endpoint: **`localhost:9092`** (listener `PLAINTEXT_HOST`).
- Topics in use: **`clickstream-events`**, **`audit-events`**; DLQ naming convention **`<source-topic>.dlq`** (consumer-side).
- Topic naming: lowercase, hyphen-separated, plural `*-events`.
- Serialization: **JSON** over string/bytes; no Schema Registry / Avro / Protobuf found.
- Producers: tracker (Spring Kafka → clickstream), API (`aiokafka` → audit via outbox), data-ingestor DLQ producer (bytes).
- `api → Kafka`: publishes **audit** events only, via transactional outbox table `outbox_event`, not synchronously from HTTP handlers.
- Transactional outbox: **active for audit** (`outbox_event` + publisher). Legacy `outbox_events` + `emit_event` remain an unused stub.
- Event envelope: **no common envelope** across RefIQ; clickstream and audit use different JSON shapes.
- Idempotency conventions in API: unique keys (`event_id`, finance idempotency, notification dedupe).
- Logging/observability: API outbox logs metadata without full payload; API has in-process outbox gauges/counters, no Prometheus export. Tracker/data-ingestor expose Prometheus.

## 2. Kafka Infrastructure

| Parameter | Value | Source |
|---|---|---|
| Image | `apache/kafka:4.0.0` | `app/docker-compose.infra.yml` |
| Hostname | `kafka` | same |
| Compose project | `refiq-infra` | same (`name:`) |
| Network | `refiq_internal` (bridge) | same |
| Ports published | `9092:9092` | same |
| Security protocol | `PLAINTEXT` on all listeners | `KAFKA_LISTENER_SECURITY_PROTOCOL_MAP` |
| Restart | `unless-stopped` | same |
| Healthcheck | `kafka-broker-api-versions.sh --bootstrap-server localhost:9092` | same |
| Volumes for Kafka data | **Not found** (no named volume for Kafka) | same |
| ZooKeeper | **Not found** | same |
| Auto topic creation (broker) | **Not found** in compose env (not overridden) | same |
| Default partitions | **Not found** in compose | same |
| Retention defaults | **Not found** in compose | same |
| Message size limits | **Not found** in compose | same |
| Replication (offsets / txn state) | factor `1`, min ISR `1` | `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR`, `KAFKA_TRANSACTION_STATE_LOG_*` |

Listeners:

| Listener | Bind | Advertised | Role |
|---|---|---|---|
| `PLAINTEXT` | `:19092` | `kafka:19092` | internal / inter-broker |
| `PLAINTEXT_HOST` | `:9092` | `localhost:9092` | host clients |
| `CONTROLLER` | `:9093` | (controller) | KRaft controller |

Sources: `app/docker-compose.infra.yml` lines 39–66.

## 3. Kafka 4 Configuration

From `app/docker-compose.infra.yml`:

| Setting | Value |
|---|---|
| `KAFKA_PROCESS_ROLES` | `broker,controller` |
| `KAFKA_NODE_ID` | `1` |
| `KAFKA_CONTROLLER_QUORUM_VOTERS` | `1@kafka:9093` |
| `KAFKA_CONTROLLER_LISTENER_NAMES` | `CONTROLLER` |
| `KAFKA_INTER_BROKER_LISTENER_NAME` | `PLAINTEXT` |
| `CLUSTER_ID` | `4L6g3nShT-eMCtK--X86sw` |
| Metadata storage volume | **Not found** (no explicit Kafka data volume) |
| ZooKeeper-related env | **Not found** |

Compatibility / other Kafka 4 knobs beyond the above: **Not found** in repository compose.

## 4. Kafka Environment Variables

| Variable | Service | Purpose | Default | Secret |
|---|---|---|---|---|
| `KAFKA_NODE_ID` | kafka (infra) | KRaft node id | `1` | no |
| `KAFKA_PROCESS_ROLES` | kafka | broker+controller | `broker,controller` | no |
| `KAFKA_LISTENERS` | kafka | listener binds | see §2 | no |
| `KAFKA_ADVERTISED_LISTENERS` | kafka | advertised | see §2 | no |
| `KAFKA_LISTENER_SECURITY_PROTOCOL_MAP` | kafka | PLAINTEXT map | see compose | no |
| `KAFKA_CONTROLLER_LISTENER_NAMES` | kafka | controller listener | `CONTROLLER` | no |
| `KAFKA_CONTROLLER_QUORUM_VOTERS` | kafka | quorum | `1@kafka:9093` | no |
| `KAFKA_INTER_BROKER_LISTENER_NAME` | kafka | inter-broker | `PLAINTEXT` | no |
| `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR` | kafka | offsets RF | `1` | no |
| `KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR` | kafka | txn RF | `1` | no |
| `KAFKA_TRANSACTION_STATE_LOG_MIN_ISR` | kafka | txn ISR | `1` | no |
| `KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS` | kafka | rebalance delay | `0` | no |
| `CLUSTER_ID` | kafka | KRaft cluster id | fixed in compose | no |
| `KAFKA_BOOTSTRAP_SERVERS` | api, admin-api | producer bootstrap | code default `localhost:9092`; compose override `kafka:19092` | no |
| `KAFKA_CLIENT_ID` | api | producer client id | `refiq-api` | no |
| `AUDIT_KAFKA_TOPIC` | api, admin-api | audit topic | `audit-events` | no |
| `AUDIT_OUTBOX_ENABLED` | api | feature flag | `true` | no |
| `AUDIT_OUTBOX_BATCH_SIZE` | api | publisher batch | `100` | no |
| `AUDIT_OUTBOX_POLL_INTERVAL` | api | poll seconds | `2` | no |
| `AUDIT_OUTBOX_MAX_RETRIES` | api | retry log threshold | `10` | no |
| `AUDIT_OUTBOX_RETRY_BASE_DELAY` | api | backoff base seconds | `1` | no |
| `AUDIT_OUTBOX_PUBLISH_TIMEOUT` | api | send timeout seconds | `10` | no |
| `AUDIT_OUTBOX_SHUTDOWN_TIMEOUT` | api | graceful stop seconds | `10` | no |
| `AUDIT_OUTBOX_RETENTION_SECONDS` | api | published cleanup; `0` = off | `0` | no |
| `CLICKSTREAM_KAFKA_BOOTSTRAP_SERVERS` | tracker | clickstream bootstrap | falls back to `localhost:9092` | no |
| `clickstream.topic` (YAML) | tracker | topic name | `clickstream-events` | no |
| `clickstream.retries` | tracker | producer retries | `3` | no |
| `clickstream.send-timeout-ms` | tracker | await send | `20000` | no |
| `data-ingest.source.topic` | data-ingestor | consume topic | `clickstream-events` | no |
| `data-ingest.source.group-id` | data-ingestor | consumer group | `data-ingest-clickstream` | no |
| `data-ingest.source.type` | data-ingestor | pipeline type | `clickstream` | no |
| `data-ingest.kafka.bootstrap-servers` | data-ingestor | bootstrap | `localhost:9092` | no |
| `data-ingest.kafka.max-poll-interval` | data-ingestor | max poll interval | `5m` | no |
| `DATA_INGEST_SOURCE_*` (docs/tests) | data-ingestor audit process | override topic/group for audit | e.g. `audit-events` / `data-ingest-audit` | no |

Sources: `app/docker-compose.infra.yml`, `app/docker-compose.yml`, `app/.env.example`, `api/app/core/config.py`, `tracker/.../application.yml`, `data-ingestor/.../application.yml`.

## 5. Existing Topics

| Topic | Producer | Consumer | Purpose |
|---|---|---|---|
| `clickstream-events` | tracker (`ClickstreamKafkaProducer`) | data-ingestor (`type=clickstream`, group `data-ingest-clickstream`) | Site/SDK clickstream ingest |
| `audit-events` | api outbox publisher (`AiokafkaAuditProducer`) | data-ingestor audit process (group `data-ingest-audit` via config override; YAML default is still clickstream) | Domain audit events |
| `clickstream-events.dlq` | data-ingestor DLQ publisher (derived) | **Not found** as a dedicated consumer | Invalid clickstream records |
| `audit-events.dlq` | data-ingestor DLQ publisher (derived) | **Not found** as a dedicated consumer | Invalid audit records |

Topic creation/provisioning scripts in compose: **Not found**. data-ingestor startup probes topic existence and fails if missing (`IngestStartupChecker` / topic probe). Consumer sets `allow.auto.create.topics=false`.

## 6. Topic and Consumer Group Naming

**Topics (observed):**

- lowercase
- hyphen `-` separator
- plural `events` suffix: `clickstream-events`, `audit-events`
- no environment prefix
- no version suffix (e.g. `.v1`)
- no underscore / dotted domain prefix in topic names
- DLQ: append `.dlq` to source topic (`KafkaDeadLetterPublisher`)

**Consumer groups:**

| Consumer | Topic | Group ID |
|---|---|---|
| data-ingestor (clickstream default) | `clickstream-events` | `data-ingest-clickstream` |
| data-ingestor (audit process, config/docs/tests) | `audit-events` | `data-ingest-audit` |

Convention: `data-ingest-<type>` where type is `clickstream` / `audit`. Client IDs: `data-ingest-<type>`, DLQ client `data-ingest-<type>-dlq`. Tracker producer client id: `tracker-clickstream`. API producer client id: `refiq-api`.

## 7. Serialization and Event Envelope

### Serialization

| Path | Format | Key | Value |
|---|---|---|---|
| tracker → Kafka | JSON string | `StringSerializer` | `StringSerializer` (UTF-8 JSON) |
| api → Kafka | JSON bytes | UTF-8 string bytes | UTF-8 JSON bytes from `json.dumps` |
| data-ingestor consume | raw bytes | `ByteArrayDeserializer` | `ByteArrayDeserializer` then JSON parse |
| data-ingestor DLQ | bytes | `ByteArraySerializer` | `ByteArraySerializer` |

- Schema Registry: **Not found**
- Avro / Protobuf: **Not found**
- Compression: **Not found** in producer configs (library defaults)

**JSON details:**

| Aspect | Clickstream | Audit (API) |
|---|---|---|
| Naming | `snake_case` (`ClickstreamKafkaJson`) | `camelCase` (`AuditEventFactory` / allowlist) |
| Encoding | UTF-8 string | UTF-8 bytes, `sort_keys=True`, compact separators |
| Datetime | numeric epoch fields `*_ts` (long) | ISO-8601 UTC string with millis, suffix `Z` (`occurredAt`) |
| Nulls | Jackson `ALWAYS` include | optional fields omitted or JSON `null` for create `before`/`changes` |
| Validation | tracker mapping + ingestor strategy | factory + ingestor `AuditEventMapper` / validator |

### Event envelope

**No common event envelope found.**

Two domain-specific shapes:

1. **Clickstream** — large flat record (`ClickstreamKafkaEvent`): `event_id`, `schema_version`, `event_type`, many `*_ts` fields, entity ids as numbers, snake_case JSON.
2. **Audit** — nested contract v1: `schemaVersion`, `eventId`, `eventType`, `occurredAt`, `actor{type,id?}`, `entity{type,id}`, `action`, optional `accountId`, `requestId`, `correlationId`, `ipAddress`, `userAgent`, `changes`/`before`/`after`, `metadata`.

There is no shared `{ eventId, eventType, eventVersion, occurredAt, payload }` wrapper used by both.

## 8. IDs, Timestamps and Correlation

| Concept | Clickstream | Audit (API outbox) | API HTTP |
|---|---|---|---|
| Event ID | numeric `event_id` (long) | UUID string `eventId` (also `outbox_event.event_id`) | n/a |
| Request ID | logged as `request_id` in tracker HTTP flow | copied into payload `requestId` from `request.state.request_id` | UUID via `RequestIDMiddleware`, header `X-Request-ID` |
| Correlation ID | **Not found** as standard field | `correlationId` = `requestId` fallback | **Not found** separately |
| Entity / partition key | Kafka key `siteKey` or `siteKey:session` | Kafka key = offer id string (`partition_key`) | numeric entity ids in ORM |
| Timestamps | epoch-style longs (`occurred_ts`, `sent_ts`, …) | ISO-8601 UTC with milliseconds | middleware duration in ms |

Correlation between HTTP and Kafka for audit: yes for audited Offer mutations — `requestId` / `correlationId` stored in outbox payload from request context. No general Kafka header propagation found.

## 9. Existing Kafka Producers

| Service | Producer implementation | Topic | Library |
|---|---|---|---|
| tracker | `ClickstreamKafkaProducer` + `ClickstreamKafkaConfiguration` | `clickstream-events` | Spring Kafka / `KafkaTemplate` |
| api | `AiokafkaAuditProducer` via outbox publisher | `audit-events` (configurable) | `aiokafka` |
| data-ingestor | `KafkaDeadLetterPublisher` / `dlqProducerFactory` | `<source>.dlq` | Spring Kafka |

### Tracker producer characteristics

Source: `ClickstreamKafkaConfiguration.java`, `ClickstreamProperties.java`, `ClickstreamKafkaProducer.java`.

- sync await of futures (`future.get(sendTimeoutMs)`) after async send
- `acks=all`
- `enable.idempotence=true`
- `retries=3` (property)
- `linger.ms=5`
- `request.timeout.ms=5000`
- `delivery.timeout.ms=15000`
- `retry.backoff.ms=200`
- `max.in.flight.requests.per.connection=5`
- compression: library default (not set)
- failures: event marked failed in batch result; logged with `site_key` / `event_id`; does not crash whole process for single event

### API producer characteristics

Source: `api/app/kafka/producer.py`, `api/app/modules/audit/outbox/publisher.py`.

- `send_and_wait` (sync relative to publisher loop)
- `acks=all`
- `enable_idempotence=True`
- retries: **not set to 0**; comment says client default remains
- `request_timeout_ms=10000`
- `retry_backoff_ms=200`
- compression / linger / delivery timeout: **library defaults** (not set)
- errors: caught in publisher → outbox retry fields; HTTP path unaffected

### data-ingestor DLQ producer (convention only)

- `acks=all`, `enable.idempotence=true`
- byte key/value
- failures raise retryable ingest exception

## 10. API Kafka Integration

| Question | Finding | Source |
|---|---|---|
| Kafka dependency | yes, `aiokafka>=0.11.0` | `api/pyproject.toml` |
| Producer | `AiokafkaAuditProducer` | `api/app/kafka/producer.py` |
| Shared Kafka abstraction | minimal: producer module + `AuditEventProducer` protocol | `kafka/`, `outbox/publisher.py` |
| Events published | Offer audit events only (pilot) | `offers/audit.py` |
| Where written | same DB session as Offer mutation → `outbox_event` | `offers/audit.py`, `outbox/repository.py` |
| Where sent to Kafka | background worker after commit | `workers/outbox_publisher.py`, `main.py`, `admin/app.py` |
| Lifecycle | start on app lifespan if `AUDIT_OUTBOX_ENABLED` and not test job runner; stop on shutdown | same |
| Direct Kafka from controller | **No** | tests assert HTTP create does not call producer |

`api` does publish to Kafka, but only through the audit outbox path. No other Kafka producers found in `api`.

## 11. Transactional Outbox

Two tables / mechanisms exist:

### Legacy: `outbox_events` + `emit_event`

- Model: `app.modules.system.models.OutboxEvent`
- Helper: `app.common.events.emit_event`
- Call sites of `emit_event`: **none** outside its definition
- Publisher for this table: **Not found**

**Status A** for this path: unused stub.

### Active audit outbox: `outbox_event`

- Model: `AuditOutboxEvent`
- Written from Offer audit use cases
- Publisher: `OutboxPublisherWorker` + `publish_once`
- Chain: business transaction → `outbox_event` → publisher → Kafka `audit-events`

**Status C** for the audit path:

`business transaction → outbox → publisher → Kafka`

Overall for mail planning: the **working** pattern in `api` is **C** on table `outbox_event` (singular); the plural `outbox_events` table is still **A**.

## 12. Outbox Schema

### Legacy table `outbox_events` (migration `001`)

| Column | Type | Nullable | Default | Purpose |
|---|---|---|---|---|
| `id` | BIGINT PK | no | identity | internal PK |
| `event_type` | VARCHAR(100) | no | — | event type (indexed) |
| `aggregate_type` | VARCHAR(50) | yes | — | aggregate type |
| `aggregate_id` | VARCHAR(50) | yes | — | aggregate id string |
| `payload` | JSONB | yes | `{}` | opaque payload |
| `processed_at` | TIMESTAMPTZ | yes | null | processed marker (unused by publisher) |
| `created_at` | TIMESTAMPTZ | yes | `now()` | created |

Unique event id: **Not found**. Retry columns: **Not found**. Topic column: **Not found**.

### Active table `outbox_event` (migration `033`)

| Column | Type | Nullable | Default | Purpose |
|---|---|---|---|---|
| `id` | BIGINT PK | no | autoincrement | internal PK |
| `event_id` | VARCHAR(64) | no | — | public unique event id |
| `topic` | VARCHAR(128) | no | — | Kafka topic |
| `event_type` | VARCHAR(80) | no | — | event type |
| `aggregate_type` | VARCHAR(50) | no | — | e.g. `OFFER` |
| `aggregate_id` | VARCHAR(64) | no | — | entity id string |
| `partition_key` | VARCHAR(64) | no | — | Kafka message key |
| `payload` | JSONB | no | — | full Kafka JSON document |
| `created_at` | TIMESTAMPTZ | no | `now()` | created |
| `published_at` | TIMESTAMPTZ | yes | null | set only after Kafka ACK |
| `retry_count` | INTEGER | no | `0` | failed publish attempts |
| `last_error` | TEXT | yes | null | last error summary |
| `next_retry_at` | TIMESTAMPTZ | yes | null | backoff schedule |

Constraints / indexes:

- `PRIMARY KEY (id)`
- `UNIQUE (event_id)` → `uq_outbox_event_event_id`
- Partial index `ix_outbox_event_pending (next_retry_at, created_at) WHERE published_at IS NULL`

## 13. Outbox Transaction Semantics

Active path (`outbox_repository.add`):

- Receives existing `AsyncSession` from the request/use case (`offers/audit.py`).
- `session.add` + `await session.flush()`; **no independent commit**.
- Request DB dependency `get_db` commits once at end of successful request (`api/app/core/database.py`).
- Offer mutation + outbox insert share one transaction → atomic commit.
- On exception: `get_db` rolls back → Offer change and outbox row both discarded (covered by tests).

Legacy `emit_event`:

- Also takes `AsyncSession` and only `db.add` (no commit). Unused.

Sources: `api/app/core/database.py`, `api/app/modules/audit/outbox/repository.py`, `api/app/modules/offers/audit.py`, `api/app/common/events.py`, `api/tests/test_audit_outbox.py`.

## 14. Outbox Publisher

**Found** for `outbox_event` only.

| Aspect | Behavior | Source |
|---|---|---|
| Where started | API lifespan; admin-api lifespan | `main.py`, `admin/app.py`, `workers/outbox_publisher.py` |
| Selection | unpublished, due by `next_retry_at`, oldest per partition_key first | `outbox/repository.py` |
| Locking | `FOR UPDATE SKIP LOCKED` on PostgreSQL | same |
| Poll interval | `AUDIT_OUTBOX_POLL_INTERVAL` (default 2s) | config + worker |
| Batch size | `AUDIT_OUTBOX_BATCH_SIZE` (default 100) | config |
| Kafka publish | `send_and_wait` with timeout | `publisher.py`, `kafka/producer.py` |
| Mark published | `published_at = now` after ACK, then commit | `publisher.py` |
| Retry | exponential schedule 1×,5×,15×,30×,60× base delay; row kept | `retry.py` |
| Crash after ACK before DB | row republished with same `event_id` (at-least-once) | design + tests |
| Graceful shutdown | stop event; finish current cycle; timeout then cancel | `OutboxPublisherWorker.shutdown` |
| Tests | publisher not started when AI test job runner active | `start_outbox_publisher` |

Publisher for legacy `outbox_events`: **Not found**.

## 15. Delivery Semantics

| Pipeline | Semantics | Why (code) |
|---|---|---|
| API audit outbox → Kafka | **at-least-once** | `published_at` only after ACK; crash between ACK and DB commit re-sends same `eventId`; producer idempotence does not make cross-system EOS |
| data-ingestor audit consume | effectively deduped at sink by **`event_id` unique** on `audit_logs` (ingest schema) | migration `034` / model unique `event_id` |
| tracker clickstream → Kafka | at-least-once producer retries; HTTP may report kafka_failed for failed events | producer retries + await; no outbox on tracker path |

Exactly-once between PostgreSQL and Kafka: **not implemented**.

## 16. Existing Idempotency Patterns

Reusable patterns in `api` (not mail-specific):

| Pattern | Where |
|---|---|
| Unique `event_id` on outbox / audit log | `outbox_event.event_id`, `audit_logs.event_id` |
| Finance `FinancialIdempotencyKey` + `claim_idempotency` | `finance/idempotency.py` |
| Unique `idempotency_key` on invoices / payouts / billing transactions | finance/billing/payouts models |
| Provider webhook unique `(provider, external_event_id)` | `ProviderWebhookEvent` |
| Notification dedupe `(user_id, dedupe_key)` | `notifications` |
| Stable Kafka key per aggregate | audit `partition_key` = offer id |

## 17. Kafka Error Handling and Retry

### API producer / outbox publisher

| Failure | Behavior |
|---|---|
| Broker unavailable / timeout | publish fails → `retry_count++`, `last_error`, `next_retry_at`; metrics; warning log; business commit already done |
| Serialization | would fail publish same way (payload prepared before send) |
| Message too large | **Not specially handled**; would surface as publish error + retry |
| Cycle-level exception | `audit_outbox_cycle_failed` logged; loop continues |

HTTP Offer request does not depend on Kafka availability.

### Tracker producer

| Failure | Behavior |
|---|---|
| Send / await failure | event added to failed list; warn log; batch continues |
| Serialization reject | failed list; warn log |

### data-ingestor (retry/DLQ conventions only)

- Consumer retry backoff: `initial-backoff` 200ms, `max-backoff` 5s (`application.yml`)
- Invalid records → DLQ topic `<source>.dlq`
- No retry-topic pattern found beyond consumer retry + DLQ

## 18. DLQ

| Kind | Status |
|---|---|
| Kafka DLQ topics | Convention **`<sourceTopic>.dlq`** (`KafkaDeadLetterPublisher`) |
| Documented/expected | `clickstream-events.dlq`, `audit-events.dlq` |
| Dead-letter tables in API | **Not found** |
| Rejected event storage in API outbox | failures stay in `outbox_event` unpublished (`published_at` null) |

API audit path has **no Kafka DLQ**; it keeps failed rows in PostgreSQL outbox.

## 19. Logging and Observability

### API Kafka / outbox logging

Logged fields: `event_id`, `event_type`, `aggregate_type`, `aggregate_id`, `topic`, `retry_count`, `request_id`, `correlation_id`, error summary.

- Full payload on INFO: **No**
- Kafka headers logging: **Not found**
- Partition/offset: **Not found** in API logs

### Metrics

| Stack | Status |
|---|---|
| API outbox counters/gauges | in-process (`outbox.pending`, `published`, `publish.errors`, `retries`, `publish.latency`, `oldest.pending.age`) — not Prometheus-exported |
| API Prometheus / Grafana / OTel | **Not found** |
| Tracker Prometheus | yes (`management` endpoints) |
| data-ingestor Prometheus / Micrometer | yes (`data.ingest.*`, DLQ counter) |
| Consumer lag metrics in API | **Not found** |

## 20. Docker / Networking

| Item | Value | Source |
|---|---|---|
| Kafka hostname | `kafka` | infra compose |
| Internal port | `19092` | advertised `PLAINTEXT` |
| External/host port | `9092` | published + `PLAINTEXT_HOST` |
| Network | `refiq_internal` | infra creates; app compose joins as external |
| App services on network | `api`, `frontend`, `admin-api`, `admin-front` (+ infra postgres/redis/kafka/clickhouse) | compose files |
| API Kafka bootstrap in containers | `kafka:19092` | `app/docker-compose.yml` |
| Host-side default in API settings / `.env.example` | `localhost:9092` | config / env example |

### Compose convention for services (from `api` / infra)

| Convention | Observed |
|---|---|
| Service naming | short lowercase (`api`, `admin-api`, `postgres`, `kafka`) |
| Image | infra uses public images; apps `build.context` + `dockerfile` |
| `env_file` | `.env` for app services |
| Restart | `unless-stopped` |
| Networks | internal shared `refiq_internal`; some also `external` bridge |
| Volumes | named volumes where needed (postgres/redis/clickhouse/assets); Kafka none |
| Healthcheck | present on infra services; **Not found** on `api` service |
| `depends_on` | frontend→api, admin-front→admin-api; api does not declare depends_on kafka |
| Entrypoint | `api`: `./entrypoint.sh` (alembic then uvicorn); `admin-api`: `./entrypoint-admin.sh` |

data-ingestor: no docker-compose in its repo root found; Kafka connection is configuration-driven (`bootstrap-servers`).

## 21. PostgreSQL and Migration Ownership

| Item | Value | Source |
|---|---|---|
| Image / version | `postgres:16-alpine` | `docker-compose.infra.yml` |
| Hostname (compose) | `postgres` | same |
| Database name | from `POSTGRES_DB` (example `refiq`) | `.env.example` |
| API connection | single DB via `DATABASE_URL` | config |
| Separate schemas for modules | **Not found** as standard (tables in default schema) | migrations |
| Migrations ownership | API owns Alembic under `api/alembic/versions` | repo layout |
| Auto-run migrations | yes, `entrypoint.sh` runs `alembic upgrade head` before uvicorn | `api/entrypoint.sh` |
| Separate migration history per service | only API Alembic found in `app`; tracker/data-ingestor use their own stacks | Cannot claim a shared multi-service migration tool |

Note: `audit_logs` was replaced for ingest schema in migrations `034`/`035`; ingest writer and API `AuditLog` ORM target the ingest-shaped table. Legacy API-style rows preserved temporarily then dropped.

## 22. API Email Delta

Relative to current in-repo email implementation (spot check only):

| Item | Status |
|---|---|
| `app.modules.email` | **Still present** |
| Yandex Postbox | **Still used** (`postbox.py`, Postbox env vars) |
| Account confirmation | **Still present** |
| Password reset | **Still present** |
| New email types beyond those two | **Not found** in `EmailService` |
| Email queue | **Not found** |
| Mail log table / durable mail_log | **Not found** (`email/log.py` is logging helpers only) |
| Kafka integration for email | **Not found** |

Email remains synchronous in-process from auth flows; no Kafka handoff.

## 23. Sensitive Data Considerations

Existing patterns that matter for future mail events:

| Pattern | Status |
|---|---|
| Full Kafka payload in API INFO logs | avoided for audit outbox |
| Raw payload stored in outbox JSONB | **yes** (`outbox_event.payload` = full AuditEvent) |
| Kafka retention configured | **Not found** (broker defaults) |
| Outbox retention cleanup | configurable; default **disabled** (`AUDIT_OUTBOX_RETENTION_SECONDS=0`) |
| Email logging | logs `to_domain`, subject, kind — not full address in success path helpers; errors may include exception text |
| Tracing of HTTP/Kafka bodies | **Not found** (no OTel body capture in API) |
| Audit allowlist / sanitizer | secrets keys redacted / non-allowlisted Offer fields dropped before Kafka payload |

No secret values listed in this inventory.

## 24. Relevant Source Files

### Kafka infrastructure

- `app/docker-compose.infra.yml`
- `app/docker-compose.yml`
- `app/.env.example`

### API Kafka integration

- `api/app/kafka/producer.py`
- `api/app/kafka/__init__.py`
- `api/app/core/config.py`
- `api/pyproject.toml`
- `api/app/main.py`
- `api/app/admin/app.py`
- `api/app/workers/outbox_publisher.py`

### API outbox

- `api/app/modules/audit/outbox/models.py`
- `api/app/modules/audit/outbox/repository.py`
- `api/app/modules/audit/outbox/publisher.py`
- `api/app/modules/audit/outbox/retry.py`
- `api/app/modules/audit/outbox/serialize.py`
- `api/app/modules/audit/outbox/metrics.py`
- `api/app/modules/audit/factory.py`
- `api/app/modules/offers/audit.py`
- `api/alembic/versions/033_audit_outbox_event.py`
- `api/app/modules/system/models.py` (`OutboxEvent` legacy)
- `api/app/common/events.py` (`emit_event` unused)
- `api/alembic/versions/001_initial.py` (legacy `outbox_events`)
- `api/tests/test_audit_outbox.py`

### Docker / deployment

- `api/Dockerfile`
- `api/entrypoint.sh`
- `api/entrypoint-admin.sh`

### Configuration

- `api/app/core/config.py`
- `api/app/core/database.py`
- `api/app/core/middleware.py`

### Relevant producer implementations (conventions)

- `tracker/src/main/java/ru/refiq/clickstream/kafka/ClickstreamKafkaConfiguration.java`
- `tracker/src/main/java/ru/refiq/clickstream/kafka/ClickstreamKafkaProducer.java`
- `tracker/src/main/java/ru/refiq/clickstream/ClickstreamProperties.java`
- `tracker/src/main/resources/application.yml`
- `data-ingestor/src/main/resources/application.yml` (topic/group/bootstrap defaults)
- `data-ingestor/src/main/java/ru/refiq/config/IngestKafkaConfiguration.java` (consumer + DLQ producer conventions)
- `data-ingestor/src/main/java/ru/refiq/error/KafkaDeadLetterPublisher.java` (DLQ topic naming)

## 25. Missing Information / Uncertainties

- Broker defaults not overridden in compose: auto-create topics, default partitions, retention, max message bytes — **Cannot be determined from current repository** without image/runtime inspection.
- Whether `audit-events` / DLQ topics are pre-created in each environment — **Cannot be determined from current repository** (no provisioning scripts found; ingestor expects topic to exist).
- Production/staging Kafka topology beyond local compose — **Not found** in this workspace.
- Whether admin-api and api both running publishers will double-poll the same DB safely: code uses `SKIP LOCKED` (safe on PostgreSQL); operational replica count — environment-dependent.
- Live consumer group membership / lag — runtime only; **Not found** as code facts.
- data-ingestor deployment compose for attaching to `refiq_internal` — **Not found** in data-ingestor repo (config-only connection).
- Drift risk: documentation may mention process names; YAML default for data-ingestor remains clickstream until overridden — code/config precedence: runtime override required for audit process.
