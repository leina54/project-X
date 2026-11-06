from functools import lru_cache

from fastapi import HTTPException, status
from supabase import Client, create_client

from app.core.config import get_settings


@lru_cache
def get_supabase() -> Client:
    settings = get_settings()
    if not settings.supabase_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Supabase is not configured. Set SUPABASE_URL and SUPABASE_KEY "
                "in .env and run sql/001_init.sql in the Supabase SQL editor."
            ),
        )
    return create_client(settings.supabase_url, settings.supabase_key)
