from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class RoleType(StrEnum):
    BUSINESS = "business"
    PARTNER = "partner"


class BusinessStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class MembershipRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    VIEWER = "viewer"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class PartnerStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class ProductStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class OfferStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSING = "closing"
    ARCHIVED = "archived"


class OfferVisibility(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"


class AccessPolicy(StrEnum):
    OPEN = "open"
    APPROVAL = "approval"
    INVITE_ONLY = "invite_only"


class ConversionType(StrEnum):
    SALE = "sale"
    LEAD = "lead"
    SIGNUP = "signup"
    APPLICATION = "application"
    CUSTOM = "custom"


class CommissionType(StrEnum):
    PERCENT = "percent"
    FIXED = "fixed"


class OfferPartnerStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVOKED = "revoked"
    CANCELLED = "cancelled"


class OfferPartnerSource(StrEnum):
    MARKETPLACE = "marketplace"
    INVITATION = "invitation"
    MANUAL = "manual"


class BusinessPartnerStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    PENDING = "pending"


class LinkStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class SiteStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class CampaignStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class CampaignType(StrEnum):
    GENERAL = "GENERAL"


class PromotionOwner(StrEnum):
    BUSINESS = "business"
    PARTNER = "partner"


class ConversionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"


class CommissionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    PAYABLE = "payable"
    PAID = "paid"
    CANCELLED = "cancelled"


class PayoutStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"


class CreativeType(StrEnum):
    TEXT = "text"
    SOCIAL_POST = "social_post"
    BANNER = "banner"
    EMAIL = "email"
    LANDING_TEXT = "landing_text"
    VIDEO = "video"


class CreativeSource(StrEnum):
    BUSINESS = "business"
    PARTNER = "partner"
    AI = "ai"


class CreativeStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class CreativeChannel(StrEnum):
    GENERAL = "general"
    TELEGRAM = "telegram"
    SOCIAL = "social"
    VK = "vk"
    INSTAGRAM = "instagram"
    YANDEX_DIRECT = "yandex_direct"
    META_ADS = "meta_ads"
    GOOGLE_ADS = "google_ads"
    TIKTOK_ADS = "tiktok_ads"
    OTHER = "other"


class PromoGenerationRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    FAILED = "failed"


class PromoGenerationItemStatus(StrEnum):
    QUEUED = "queued"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BannerFormat(StrEnum):
    SQUARE_1_1 = "square_1_1"
    PORTRAIT_4_5 = "portrait_4_5"
    LANDSCAPE_16_9 = "landscape_16_9"
    STORY_9_16 = "story_9_16"


class CreativePolicyStatus(StrEnum):
    VALID = "valid"
    WARNING = "warning"
    BLOCKED = "blocked"


class AiGenerationStatus(StrEnum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
