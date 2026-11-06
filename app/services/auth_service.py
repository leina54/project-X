from fastapi import HTTPException, status

from app.core.security import create_access_token, hash_password, verify_password
from app.db.supabase import get_supabase
from app.models.user import User, UserPublic
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


def _to_user(row: dict) -> User:
    return User.model_validate(row)


def register_user(payload: RegisterRequest) -> TokenResponse:
    client = get_supabase()
    existing = client.table("users").select("id").eq("email", payload.email.lower()).execute()
    if existing.data:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    row = {
        "email": payload.email.lower(),
        "hashed_password": hash_password(payload.password),
        "role": payload.role,
    }
    created = client.table("users").insert(row).execute()
    if not created.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create user")
    user = _to_user(created.data[0])
    return _token_for(user)


def login_user(payload: LoginRequest) -> TokenResponse:
    client = get_supabase()
    result = client.table("users").select("*").eq("email", payload.email.lower()).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    user = _to_user(result.data[0])
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return _token_for(user)


def get_user_by_id(user_id: str) -> User:
    client = get_supabase()
    result = client.table("users").select("*").eq("id", user_id).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return _to_user(result.data[0])


def _token_for(user: User) -> TokenResponse:
    token = create_access_token(user.id, extra={"role": user.role})
    public = UserPublic(id=user.id, email=user.email, role=user.role, created_at=user.created_at)
    return TokenResponse(access_token=token, user=public)
