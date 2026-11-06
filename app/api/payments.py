from fastapi import APIRouter

from app.services.payment_service import mvp_status

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/status")
def payment_status() -> dict:
    return mvp_status()
