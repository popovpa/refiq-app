from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me"

    DATABASE_URL: str = "postgresql+asyncpg://refiq:refiq_dev_password@localhost:5432/refiq"
    REDIS_URL: str = "redis://localhost:6379/0"

    SESSION_COOKIE_NAME: str = "refiq_session"
    SESSION_TTL_SECONDS: int = 86400
    SESSION_COOKIE_SECURE: bool = False

    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    FRONTEND_URL: str = "http://localhost:3000"
    APP_PUBLIC_URL: str = ""

    ADMIN_HOST: str = "admin.int.refiq.ru"
    ADMIN_SESSION_COOKIE_NAME: str = "refiq_admin_session"
    ADMIN_SESSION_COOKIE_SECURE: bool = False
    ADMIN_CORS_ORIGINS: str = "http://localhost:3100,http://127.0.0.1:3100,http://localhost:5174"
    ADMIN_FRONTEND_URL: str = "http://localhost:3100"

    YANDEX_POSTBOX_ACCESS_KEY_ID: str = ""
    YANDEX_POSTBOX_SECRET_ACCESS_KEY: str = ""
    YANDEX_POSTBOX_REGION: str = "ru-central1"
    YANDEX_POSTBOX_ENDPOINT: str = "https://postbox.cloud.yandex.net"
    EMAIL_FROM: str = "no-reply@refiq.ru"
    EMAIL_FROM_NAME: str = "RefIQ"

    AI_PROVIDER: str = "openai"
    AI_TEXT_PROVIDER: str = ""
    AI_IMAGE_PROVIDER: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-5.6-luna"
    OPENAI_PROMO_MODEL: str = "gpt-5.6-luna"
    OPENAI_PROMO_REASONING_EFFORT: str = "none"
    PROMO_GENERATION_CONCURRENCY: int = 1
    OPENAI_IMAGE_MODEL: str = "gpt-image-1"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    AI_TIMEOUT_SECONDS: float = 45
    AI_IMAGE_TIMEOUT_SECONDS: float = 90
    AI_MAX_RETRIES: int = 1
    AI_GUIDANCE_MAX_CHARS: int = 4000
    OPENAI_GUARD_MODEL: str = "gpt-4.1-mini"
    AI_GUARD_MODEL: str = ""
    AI_SEMANTIC_GUARD_ENABLED: bool = True
    AI_SEMANTIC_GUARD_FAIL_CLOSED: bool = True
    AI_OUTPUT_GROUNDING_ENABLED: bool = True
    AI_SEMANTIC_GROUNDING_ENABLED: bool = False
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_PROMO_MODEL: str = "deepseek-v4-pro"
    DEEPSEEK_FAST_MODEL: str = "deepseek-v4-flash"
    DEEPSEEK_TIMEOUT_SECONDS: float = 60
    DEEPSEEK_MAX_RETRIES: int = 1
    YANDEX_AI_API_KEY: str = ""
    YANDEX_AI_FOLDER_ID: str = ""
    YANDEX_AI_IMAGE_MODEL: str = "aliceai-image-art-3.0"
    YANDEX_AI_BASE_URL: str = "https://ai.api.cloud.yandex.net"
    YANDEX_AI_IMAGE_PROMPT_MAX_CHARS: int = 500
    YANDEX_AI_IMAGE_TIMEOUT_SECONDS: float = 90
    ASSET_STORAGE_DIR: str = "./data/assets"

    S3_ENDPOINT_URL: str = "https://storage.yandexcloud.net"
    S3_REGION: str = "ru-central1"
    S3_BUCKET: str = "refiq-files"
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""

    FINANCIAL_TRANSACTIONS_ENABLED: bool = False
    FINANCIAL_PROVIDER: str = "TBANK"
    PAYOUT_MIN_AMOUNT: str = "500.00"
    PAYOUT_INTERVAL_DAYS: int = 14
    PAYOUT_DUE_DAYS: int = 3
    SUBSCRIPTION_TRIAL_DAYS: int = 14
    SUBSCRIPTION_GRACE_DAYS: int = 30
    PLAN_PRO_AMOUNT: str = "4990.00"
    PAYOUT_REMINDERS_PER_DAY: int = 2
    TBANK_TERMINAL_KEY: str = ""
    TBANK_PASSWORD: str = ""
    TBANK_E2C_TERMINAL_KEY: str = ""
    TBANK_E2C_PASSWORD: str = ""
    TBANK_ACQUIRING_BASE_URL: str = "https://securepay.tinkoff.ru/v2"
    TBANK_E2C_BASE_URL: str = "https://securepay.tinkoff.ru/e2c/v2"
    TBANK_NOTIFICATION_URL: str = ""

    LEGAL_ENTITY_LOOKUP_PROVIDER: str = "fake"
    DADATA_API_KEY: str = ""
    DADATA_HOST: str = "suggestions.dadata.ru"
    DADATA_API_PREFIX: str = "/suggestions/api/4_1/rs"
    LEGAL_ENTITY_LOOKUP_SEARCH_TIMEOUT_SECONDS: float = 2.5
    LEGAL_ENTITY_LOOKUP_RESOLVE_TIMEOUT_SECONDS: float = 6.0

    @property
    def s3_enabled(self) -> bool:
        return bool(self.S3_ACCESS_KEY_ID and self.S3_SECRET_ACCESS_KEY)

    @property
    def postbox_enabled(self) -> bool:
        return bool(self.YANDEX_POSTBOX_ACCESS_KEY_ID and self.YANDEX_POSTBOX_SECRET_ACCESS_KEY)

    @property
    def public_app_url(self) -> str:
        return (self.APP_PUBLIC_URL or self.FRONTEND_URL).rstrip("/")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def admin_cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ADMIN_CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def tbank_payment_credentials_configured(self) -> bool:
        return bool(self.TBANK_TERMINAL_KEY and self.TBANK_PASSWORD)

    @property
    def tbank_payout_credentials_configured(self) -> bool:
        key = self.TBANK_E2C_TERMINAL_KEY or self.TBANK_TERMINAL_KEY
        password = self.TBANK_E2C_PASSWORD or self.TBANK_PASSWORD
        return bool(key and password)

    @property
    def financial_provider_is_tbank(self) -> bool:
        return (self.FINANCIAL_PROVIDER or "TBANK").upper() == "TBANK"

    @property
    def live_financial_transactions_allowed(self) -> bool:
        return (
            self.FINANCIAL_TRANSACTIONS_ENABLED
            and self.financial_provider_is_tbank
            and self.tbank_payment_credentials_configured
            and self.tbank_payout_credentials_configured
        )

    @property
    def financial_mode_label(self) -> str:
        return "LIVE" if self.live_financial_transactions_allowed else "TEST"


settings = Settings()
