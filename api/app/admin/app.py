from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.admin.api.deps import get_current_admin
from app.admin.api.routers import (
    actions_router,
    audit_router,
    overview_router,
    resources_router,
    search_router,
    trace_router,
)
from app.admin.auth.router import router as auth_router
from app.admin.auth.router import serialize_admin
from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import register_exception_handlers
from app.core.middleware import RequestIDMiddleware, StructuredLoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="RefIQ Admin API",
    version="0.1.0",
    docs_url="/api/docs" if settings.APP_ENV == "development" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.admin_cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.add_middleware(StructuredLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)
register_exception_handlers(app)

PREFIX = "/api/admin/v1"

app.include_router(auth_router, prefix=f"{PREFIX}/auth", tags=["admin-auth"])
app.include_router(overview_router, prefix=PREFIX, tags=["admin"])
app.include_router(search_router, prefix=PREFIX, tags=["admin"])
app.include_router(trace_router, prefix=PREFIX, tags=["admin"])
app.include_router(resources_router, prefix=PREFIX, tags=["admin"])
app.include_router(actions_router, prefix=PREFIX, tags=["admin-actions"])
app.include_router(audit_router, prefix=PREFIX, tags=["admin"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "admin"}


@app.get(f"{PREFIX}/me", tags=["admin-auth"])
async def me(admin=Depends(get_current_admin)):
    return serialize_admin(admin)
