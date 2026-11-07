from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, require_shop_user
from app.db.supabase import get_supabase
from app.models.user import User
from app.schemas.shop import ShopCreate, ShopOut, ShopUpdate

router = APIRouter(prefix="/shops", tags=["shops"])


def _to_out(row: dict) -> ShopOut:
    return ShopOut.model_validate(row)


@router.post("", response_model=ShopOut, status_code=status.HTTP_201_CREATED)
def create_shop(payload: ShopCreate, user: User = Depends(require_shop_user)) -> ShopOut:
    client = get_supabase()
    existing = client.table("shops").select("id").eq("owner_id", user.id).limit(1).execute()
    if existing.data:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Shop already exists for this account")
    row = {**payload.model_dump(), "owner_id": user.id}
    created = client.table("shops").insert(row).execute()
    if not created.data:
        raise HTTPException(status_code=500, detail="Could not create shop")
    return _to_out(created.data[0])


@router.get("/me", response_model=ShopOut)
def get_my_shop(user: User = Depends(get_current_user)) -> ShopOut:
    client = get_supabase()
    result = client.table("shops").select("*").eq("owner_id", user.id).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No shop found")
    return _to_out(result.data[0])


@router.patch("/me", response_model=ShopOut)
def update_my_shop(payload: ShopUpdate, user: User = Depends(require_shop_user)) -> ShopOut:
    client = get_supabase()
    existing = client.table("shops").select("*").eq("owner_id", user.id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No shop found")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return _to_out(existing.data[0])
    updated = client.table("shops").update(changes).eq("id", existing.data[0]["id"]).execute()
    if not updated.data:
        raise HTTPException(status_code=500, detail="Could not update shop")
    return _to_out(updated.data[0])
