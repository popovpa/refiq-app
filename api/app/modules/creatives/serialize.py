from datetime import datetime, timezone

from app.modules.assets.models import Asset
from app.modules.creatives.models import Creative


def serialize_creative(creative: Creative, *, asset: Asset | None = None, file_url: str | None = None) -> dict:
    content = creative.text_content or {}
    data = creative.__dict__
    return {
        "id": creative.id,
        "offer_id": creative.offer_id,
        "partner_id": creative.partner_id,
        "campaign_id": creative.campaign_id,
        "type": creative.type,
        "source": creative.source,
        "status": creative.status,
        "title": creative.title,
        "headline": content.get("headline"),
        "body": content.get("body"),
        "cta": content.get("cta"),
        "hashtags": content.get("hashtags") or [],
        "items": content.get("items") or [],
        "descriptions": content.get("descriptions") or [],
        "primary_texts": content.get("primary_texts") or [],
        "hooks": content.get("hooks") or [],
        "captions": content.get("captions") or [],
        "ctas": content.get("ctas") or [],
        "variants": _serialize_variants(content.get("variants")),
        "asset_id": creative.asset_id,
        "asset": _serialize_asset(asset, file_url) if asset or file_url else None,
        "language": creative.language,
        "channel": creative.channel,
        "format": creative.format,
        "generation_id": creative.generation_id,
        "selected_variant": creative.selected_variant,
        "policy_status": creative.policy_status,
        "policy_issues": creative.policy_issues or [],
        "created_at": _iso(data.get("created_at")),
        "updated_at": _iso(data.get("updated_at")),
    }


def _serialize_variants(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    variants: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        hashtags = item.get("hashtags") or []
        variants.append(
            {
                "headline": item.get("headline") or None,
                "body": item.get("body") or None,
                "cta": item.get("cta") or None,
                "hashtags": hashtags if isinstance(hashtags, list) else [],
            }
        )
    return variants


def _serialize_asset(asset: Asset | None, file_url: str | None) -> dict:
    payload = {"url": file_url}
    if asset:
        payload.update(
            {
                "id": asset.id,
                "mime_type": asset.mime_type,
                "width": asset.width,
                "height": asset.height,
                "size": asset.size,
            }
        )
    return payload


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
