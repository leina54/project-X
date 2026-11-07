from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import require_shop_user
from app.models.user import User
from app.schemas.inventory import InventoryCreate, InventoryOut, InventoryUpdate
from app.services import inventory_service

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("", response_model=list[InventoryOut])
def list_items(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_shop_user),
) -> list[InventoryOut]:
    return inventory_service.list_inventory(user, limit=limit, offset=offset)


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


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_item(item_id: str, user: User = Depends(require_shop_user)) -> Response:
    inventory_service.archive_item(user, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
