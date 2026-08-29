# RefIQ API

FastAPI service for the partner-sales product. Run with Docker Compose from the repository root (`localhost:8000`).

Internal admin console (separate process + `admin-front`) is documented in [`../ADMIN.md`](../ADMIN.md). Public `app.main:app` does not serve `/api/admin/*`.

## Environment

Copy `.env.example` to `.env`. Application settings are loaded in `app/core/config.py`.

### AI

| Variable | Default | Purpose |
| --- | --- | --- |
| `AI_PROVIDER` | `openai` | Fallback provider when split vars are empty (`openai`, `deepseek`, `yandex`, or `fake` in tests). |
| `AI_TEXT_PROVIDER` | empty | Text/structured provider (`openai`, `deepseek`, `fake`). Empty falls back to `AI_PROVIDER`. |
| `AI_IMAGE_PROVIDER` | empty | Image provider (`openai`, `yandex`, `fake`). Empty falls back to `AI_PROVIDER`. |
| `DEEPSEEK_API_KEY` | empty | Secret for the DeepSeek text adapter. Never send to the frontend or logs. |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek Chat Completions base URL. |
| `DEEPSEEK_PROMO_MODEL` | `deepseek-v4-pro` | Default Promo Materials text model. |
| `DEEPSEEK_FAST_MODEL` | `deepseek-v4-flash` | Optional cheaper model for compact rewrite. |
| `YANDEX_AI_API_KEY` | empty | Yandex Cloud API key for Alice AI ART. |
| `YANDEX_AI_FOLDER_ID` | empty | Folder used in `art://{folder}/aliceai-image-art-3.0`. |
| `YANDEX_AI_IMAGE_MODEL` | `aliceai-image-art-3.0` | Alice image model name. |
| `YANDEX_AI_BASE_URL` | `https://ai.api.cloud.yandex.net` | Yandex Images API host. |
| `YANDEX_AI_IMAGE_PROMPT_MAX_CHARS` | `500` | Alice adapter only. Promo image prompts for OpenAI have no 500-char cap. |
| `OPENAI_API_KEY` | empty | Secret for the OpenAI adapter. Store only as an environment variable / secret manager. Never send it to the frontend, API responses, logs, PostgreSQL, or git. |
| `OPENAI_MODEL` | `gpt-5.6-luna` | Model name passed to the OpenAI text adapter. |
| `OPENAI_IMAGE_MODEL` | `gpt-image-1` | Image model for `IMAGE_GENERATION` (adapter only). |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible API base URL (adapter only). |
| `AI_TIMEOUT_SECONDS` | `45` | Provider HTTP timeout for text. |
| `AI_IMAGE_TIMEOUT_SECONDS` | `90` | Provider HTTP timeout for image generation. |
| `AI_MAX_RETRIES` | `1` | Extra attempts for retryable provider errors (timeouts, 429, 5xx). |
| `ASSET_STORAGE_DIR` | `./data/assets` | Local object storage root for generated banner files. |

If `OPENAI_API_KEY` is empty and `AI_PROVIDER=openai`, AI endpoints return a normalized `AI_NOT_CONFIGURED` error. Offer CRUD keeps working.

`OPENAI_MODEL` must be a model the key can call on `OPENAI_BASE_URL`. The example value `gpt-5.6-luna` is a placeholder; the public OpenAI API typically needs a model such as `gpt-4o`. A 429 from OpenAI is often `insufficient_quota` (billing/quota), not a local RefIQ throttle.

## AI module layout

```text
use case (draft / edit / rewrite)
  → OfferAIContextBuilder + versioned prompts
  → TextGenerationProvider (generate / generate_structured)
  → ProviderResolver
  → OpenAI adapter | Fake provider
  → local schema validation
  → DTO for the frontend (Offer is not saved)

+ AiUsageService (every success and failure)
```

Offer use cases never import the OpenAI SDK or HTTP types. Structured JSON is validated locally before it reaches the client. The draft/edit/rewrite endpoints do not call `Offer` persistence.

### Adding a second provider

1. Implement `TextGenerationProvider` or `ImageGenerationProvider` next to the existing adapters.
2. Map it in `app/modules/ai/resolver.py` from `AI_TEXT_PROVIDER` / `AI_IMAGE_PROVIDER` (fallback `AI_PROVIDER`). DeepSeek and Alice AI ART are already mapped.
3. Keep OpenAI-specific request/response fields inside the adapter; convert to `GenerationResult` / `ProviderUsage`. Extra telemetry goes to `AiUsage.provider_metadata` JSONB.

Image generation is implemented as `IMAGE_GENERATION` via `OpenAIImageGenerationProvider`. `IMAGE_EDIT` and `VIDEO_GENERATION` still return `AI_CAPABILITY_UNAVAILABLE`. Creatives are a product `Creative` entity (`source=business|partner|ai`), not `AiBanner` / `AiPost` tables. `OfferPromotionContextBuilder` builds promotion context for copy and banners.
