from functools import lru_cache
from contextvars import ContextVar, Token

from fastapi import HTTPException, status
from supabase import Client, create_client

from app.core.config import get_settings

request_supabase_client: ContextVar[Client | None] = ContextVar(
    "request_supabase_client",
    default=None,
)


def create_supabase_client(access_token: str | None = None) -> Client:
    settings = get_settings()
    if not settings.supabase_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Supabase is not configured. Set SUPABASE_URL and "
                "SUPABASE_PUBLISHABLE_KEY in .env.local and run "
                "sql/003_supabase_auth_rls.sql."
            ),
        )
    client = create_client(settings.supabase_url, settings.supabase_key.get_secret_value())
    if access_token:
        client.postgrest.auth(access_token)
    return client


def get_supabase() -> Client:
    client = request_supabase_client.get()
    return client if client is not None else create_supabase_client()


def bind_supabase_client(client: Client) -> Token[Client | None]:
    return request_supabase_client.set(client)


def unbind_supabase_client(token: Token[Client | None]) -> None:
    request_supabase_client.reset(token)
