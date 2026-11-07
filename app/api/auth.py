from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError

from app.api.deps import get_current_user
from app.models.user import User, UserPublic
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest) -> TokenResponse:
    return auth_service.register_user(payload)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    return auth_service.login_user(payload)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest) -> TokenResponse:
    return auth_service.refresh_session(payload.refresh_token)


@router.post("/token", response_model=TokenResponse)
def login_form(form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    email = (form.username or "").strip()
    if "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be the email you registered with, not 'user'. First call POST /auth/register.",
        )
    try:
        payload = LoginRequest(email=email, password=form.password)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid username or password format",
        ) from exc
    return auth_service.login_user(payload)


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)) -> UserPublic:
    return UserPublic(id=user.id, email=user.email, role=user.role, created_at=user.created_at)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    user: User = Depends(get_current_user),
) -> Response:
    auth_service.delete_account(user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
