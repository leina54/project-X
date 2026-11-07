import logging
import time
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from postgrest.exceptions import APIError
from supabase_auth.errors import AuthApiError

from app.api import auth, inventory, matching, payments, shops
from app.core.config import get_settings
from app.core.middleware import RequestGuardMiddleware
from app.db.supabase import (
    bind_supabase_client,
    create_supabase_client,
    get_supabase,
    unbind_supabase_client,
)

logger = logging.getLogger("software_x")
logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.validate_runtime()
    yield


app = FastAPI(
    title="Software X",
    description="Real-time local inventory matching engine",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    RequestGuardMiddleware,
    max_body_bytes=settings.max_request_body_bytes,
    window_seconds=settings.rate_limit_window_seconds,
    auth_limit=settings.auth_rate_limit_requests,
    search_limit=settings.search_rate_limit_requests,
)


@app.middleware("http")
async def log_request(request: Request, call_next) -> Response:
    started = time.monotonic()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        logger.info(
            "request method=%s path=%s status=%s duration_ms=%d",
            request.method,
            request.url.path,
            status_code,
            int((time.monotonic() - started) * 1000),
        )


@app.middleware("http")
async def bind_supabase_user_token(request: Request, call_next) -> Response:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    access_token = token.strip() if scheme.lower() == "bearer" and token.strip() else None
    settings = get_settings()
    context_token = None
    client = None
    if settings.supabase_configured:
        client = create_supabase_client(access_token)
        context_token = bind_supabase_client(client)
    try:
        return await call_next(request)
    finally:
        if context_token is not None:
            unbind_supabase_client(context_token)
        if client is not None:
            client.postgrest.aclose()
            client.auth.close()


@app.exception_handler(httpx.HTTPError)
async def handle_upstream_connection_error(
    request: Request,
    exc: httpx.HTTPError,
) -> JSONResponse:
    logger.error(
        "External service connection failed for %s %s: %s",
        request.method,
        request.url.path,
        type(exc).__name__,
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "A required external service is temporarily unavailable"},
    )


@app.exception_handler(APIError)
async def handle_supabase_error(request: Request, exc: APIError) -> JSONResponse:
    code = getattr(exc, "code", None)
    logger.error("Supabase request failed for %s %s (code=%s)", request.method, request.url.path, code)
    if code == "23505":
        status_code, detail = 409, "A record with these unique values already exists"
    elif code in {"23503", "23514", "22P02"}:
        status_code, detail = 422, "The submitted data violates a database constraint"
    else:
        status_code, detail = 503, "Supabase could not complete the request"
    return JSONResponse(status_code=status_code, content={"detail": detail})


@app.exception_handler(AuthApiError)
async def handle_supabase_auth_error(request: Request, exc: AuthApiError) -> JSONResponse:
    logger.error(
        "Supabase Auth request failed for %s %s (status=%s, code=%s)",
        request.method,
        request.url.path,
        exc.status,
        exc.code,
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "Supabase Auth could not complete the request"},
    )


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


app.include_router(auth.router)
app.include_router(shops.router)
app.include_router(inventory.router)
app.include_router(matching.router)
app.include_router(payments.router)


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready", tags=["system"])
def readiness() -> JSONResponse:
    try:
        result = get_supabase().rpc("backend_readiness").execute()
        if result.data is not True:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "dependency": "supabase_schema",
                    "next_step": (
                        "Confirm sql/001_init.sql, sql/002_validate_production_data.sql, "
                        "and sql/003_supabase_auth_rls.sql completed successfully."
                    ),
                },
            )
    except (HTTPException, httpx.HTTPError, APIError) as exc:
        logger.warning("Readiness check failed (%s)", type(exc).__name__)
        if isinstance(exc, APIError) and getattr(exc, "code", None) == "PGRST202":
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "dependency": "supabase_schema",
                    "next_step": (
                        "Apply sql/003_supabase_auth_rls.sql in the Supabase SQL Editor "
                        "after sql/001_init.sql and sql/002_validate_production_data.sql."
                    ),
                },
            )
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "dependency": "supabase_or_schema"},
        )
    return JSONResponse(status_code=200, content={"status": "ready", "dependency": "supabase"})
