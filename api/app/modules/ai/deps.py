from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.database import async_session_factory

_usage_session_factory: async_sessionmaker = async_session_factory


def get_usage_session_factory() -> async_sessionmaker:
    return _usage_session_factory


def set_usage_session_factory(factory: async_sessionmaker) -> None:
    global _usage_session_factory
    _usage_session_factory = factory

