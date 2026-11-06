from fastapi import APIRouter, Depends, status

from app.api.deps import require_shop_user
from app.models.user import User
from app.schemas.inventory import InventoryCreate, InventoryOut, InventoryUpdate
from app.services import inventory_service

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("", response_model=list[InventoryOut])
def list_items(user: User = Depends(require_shop_user)) -> list[InventoryOut]:
    return inventory_service.list_inventory(user)


@router.post("", response_model=InventoryOut, status_code=status.HTTP_201_CREATED)
def add_item(payload: InventoryCreate, user: User = Depends(require_shop_user)) -> InventoryOut:
    return inventory_service.create_item(user, payload)


@router.patch("/{item_id}", response_model=InventoryOut)
def update_item(
    item_id: str,
    payload: InventoryUpdate,
    user: User = Depends(require_shop_user),
) -> InventoryOut:
    return inventory_service.update_item(user, item_id, payload)
