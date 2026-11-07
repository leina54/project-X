from typing import Any

from fastapi import HTTPException, status
from supabase_auth.errors import AuthApiError

from app.db.supabase import get_supabase
from app.models.user import User, UserPublic
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


def register_user(payload: RegisterRequest) -> TokenResponse:
    client = get_supabase()
    try:
        response = client.auth.sign_up(
            {
                "email": str(payload.email).lower(),
                "password": payload.password,
                "options": {"data": {"role": payload.role}},
            }
        )
    except AuthApiError as exc:
        if exc.code in {"email_exists", "user_already_exists"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            ) from exc
        raise

    auth_user = response.user
    session = response.session
    if session:
        client.postgrest.auth(session.access_token)
        user = _profile_for_id(client, auth_user.id)
    else:
        user = User(
            id=auth_user.id,
            email=auth_user.email,
            role=_role_from_metadata(auth_user.user_metadata),
            created_at=auth_user.created_at,
        )
    return _token_response(user, session)


def login_user(payload: LoginRequest) -> TokenResponse:
    client = get_supabase()
    try:
        response = client.auth.sign_in_with_password(
            {"email": str(payload.email).lower(), "password": payload.password}
        )
    except AuthApiError as exc:
        if exc.code == "email_not_confirmed":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Confirm your email before signing in",
            ) from exc
        if exc.code in {"invalid_credentials", "user_not_found"}:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            ) from exc
        raise

    if not response.session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not create an authenticated session",
        )
    client.postgrest.auth(response.session.access_token)
    user = _profile_for_id(client, response.user.id)
    return _token_response(user, response.session)


def refresh_session(refresh_token: str) -> TokenResponse:
    client = get_supabase()
    try:
        response = client.auth.refresh_session(refresh_token)
    except AuthApiError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or expired",
        ) from exc
    if not response.session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not refresh the session",
        )
    client.postgrest.auth(response.session.access_token)
    user = _profile_for_id(client, response.user.id)
    return _token_response(user, response.session)


def get_current_user(user_id: str) -> User:
    return _profile_for_id(get_supabase(), user_id)


def delete_account(user: User) -> None:
    del user
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Account deletion requires a private Supabase Auth admin key. "
            "Contact an administrator to remove this account."
        ),
    )


def _profile_for_id(client: Any, user_id: str) -> User:
    result = (
        client.table("profiles")
        .select("id,email,role,created_at")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account profile is not available; contact support",
        )
    return User.model_validate(result.data[0])


def _role_from_metadata(metadata: dict[str, Any] | None) -> str:
    role = (metadata or {}).get("role")
    return role if role in {"buyer", "shop"} else "buyer"


def _token_response(user: User, session: Any | None) -> TokenResponse:
    public = UserPublic(
        id=user.id,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
    )
    return TokenResponse(
        access_token=session.access_token if session else None,
        refresh_token=session.refresh_token if session else None,
        requires_email_confirmation=session is None,
        user=public,
    )
