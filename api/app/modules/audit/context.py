from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from app.core.ids import parse_optional_id
from app.modules.audit.events import ActorType

_MAX_USER_AGENT = 2000
_MAX_IP = 45


@dataclass(frozen=True, slots=True)
class AuditContext:
    actor_type: str
    source_service: str
    user_id: int | None = None
    admin_id: int | None = None
    business_id: int | None = None
    partner_id: int | None = None
    request_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None


def _optional_id(value) -> int | None:
    if value in (None, ""):
        return None
    return parse_optional_id(value)


def _client_ip(request: Request) -> str | None:
    if request.client and request.client.host:
        return request.client.host[:_MAX_IP]
    return None


def _user_agent(request: Request) -> str | None:
    value = request.headers.get("user-agent")
    if not value:
        return None
    return value[:_MAX_USER_AGENT]


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def audit_context_from_request(
    request: Request,
    *,
    actor_type: str,
    source_service: str,
    user_id: int | None = None,
    admin_id: int | None = None,
    business_id: int | None = None,
    partner_id: int | None = None,
) -> AuditContext:
    return AuditContext(
        actor_type=actor_type,
        source_service=source_service,
        user_id=user_id,
        admin_id=admin_id,
        business_id=business_id,
        partner_id=partner_id,
        request_id=_request_id(request),
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )


def audit_context_from_http(
    request: Request,
    session_data: dict,
    *,
    source_service: str = "api",
    actor_type: str = ActorType.USER,
) -> AuditContext:
    return audit_context_from_request(
        request,
        actor_type=actor_type,
        source_service=source_service,
        user_id=_optional_id(session_data.get("user_id")),
        business_id=_optional_id(session_data.get("active_business_id")),
        partner_id=_optional_id(session_data.get("active_partner_id")),
    )
