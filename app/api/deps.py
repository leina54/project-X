from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from supabase_auth.errors import AuthApiError

from app.db.supabase import get_supabase
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    try:
        auth_user = get_supabase().auth.get_user(token)
    except AuthApiError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if not auth_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return User.model_validate(
            get_supabase()
            .table("profiles")
            .select("id,email,role,created_at")
            .eq("id", auth_user.user.id)
            .limit(1)
            .execute()
            .data[0]
        )
    except (IndexError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account profile is not available; contact support",
        ) from exc


def require_shop_user(user: User = Depends(get_current_user)) -> User:
    if user.role != "shop":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Shop account required",
        )
    return user
