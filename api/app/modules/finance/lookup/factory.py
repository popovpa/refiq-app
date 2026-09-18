from __future__ import annotations

from app.common.enums import LegalEntityLookupProviderType
from app.core.config import settings
from app.modules.finance.lookup.errors import lookup_error
from app.modules.finance.lookup.protocol import LegalEntityLookupProvider
from app.modules.finance.lookup.providers.dadata import DaDataLegalEntityLookupProvider
from app.modules.finance.lookup.providers.fake import FakeLegalEntityLookupProvider, fake_lookup_provider

_override: LegalEntityLookupProvider | None = None


def set_lookup_provider_override(provider: LegalEntityLookupProvider | None) -> None:
    global _override
    _override = provider


def reset_lookup_provider_override() -> None:
    set_lookup_provider_override(None)
    fake_lookup_provider.reset()


def get_lookup_provider() -> LegalEntityLookupProvider:
    if _override is not None:
        return _override
    name = (settings.LEGAL_ENTITY_LOOKUP_PROVIDER or LegalEntityLookupProviderType.FAKE.value).lower()
    if name in {LegalEntityLookupProviderType.FAKE.value, "test"}:
        return fake_lookup_provider
    if name == LegalEntityLookupProviderType.DADATA.value:
        return DaDataLegalEntityLookupProvider()
    raise lookup_error("LEGAL_ENTITY_LOOKUP_CONFIGURATION_ERROR", status_code=503)


def current_lookup_provider_name() -> str:
    if _override is not None:
        return getattr(_override, "name", "override")
    return (settings.LEGAL_ENTITY_LOOKUP_PROVIDER or "fake").lower()
