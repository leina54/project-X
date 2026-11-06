from decimal import Decimal

from fastapi import HTTPException, status

from app.db.supabase import get_supabase
from app.models.inventory import InventoryItem
from app.models.user import User
from app.schemas.inventory import InventoryCreate, InventoryOut, InventoryUpdate
from app.services import maps_service
from app.utils.helpers import normalize_name, utcnow


def _to_out(row: dict) -> InventoryOut:
    item = InventoryItem.model_validate(row)
    return InventoryOut(
        id=item.id,
        shop_id=item.shop_id,
        name=item.name,
        normalized_name=item.normalized_name,
        price_kes=Decimal(str(item.price_kes)).quantize(Decimal("0.01")),
        quantity=item.quantity,
        last_updated_at=item.last_updated_at,
    )


def _shop_for_owner(owner_id: str, shop_id: str | None = None) -> dict:
    client = get_supabase()
    query = client.table("shops").select("*").eq("owner_id", owner_id)
    if shop_id:
        query = query.eq("id", shop_id)
    result = query.limit(1).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Create a shop before managing inventory",
        )
    return result.data[0]


def list_inventory(user: User, shop_id: str | None = None) -> list[InventoryOut]:
    shop = _shop_for_owner(user.id, shop_id)
    client = get_supabase()
    result = (
        client.table("inventory_items")
        .select("*")
        .eq("shop_id", shop["id"])
        .order("last_updated_at", desc=True)
        .execute()
    )
    return [_to_out(row) for row in result.data or []]


def create_item(user: User, payload: InventoryCreate) -> InventoryOut:
    shop = _shop_for_owner(user.id, payload.shop_id)
    client = get_supabase()
    row = {
        "shop_id": shop["id"],
        "name": payload.name.strip(),
        "normalized_name": normalize_name(payload.name),
        "price_kes": format(payload.price_kes, ".2f"),
        "quantity": payload.quantity,
        "last_updated_at": utcnow().isoformat(),
    }
    created = client.table("inventory_items").insert(row).execute()
    if not created.data:
        raise HTTPException(status_code=500, detail="Could not create inventory item")
    return _to_out(created.data[0])


def update_item(user: User, item_id: str, payload: InventoryUpdate) -> InventoryOut:
    shop = _shop_for_owner(user.id)
    client = get_supabase()
    existing = (
        client.table("inventory_items")
        .select("*")
        .eq("id", item_id)
        .eq("shop_id", shop["id"])
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is not None:
        changes["normalized_name"] = normalize_name(changes["name"])
        changes["name"] = changes["name"].strip()
    if "price_kes" in changes and changes["price_kes"] is not None:
        changes["price_kes"] = format(changes["price_kes"], ".2f")
    changes["last_updated_at"] = utcnow().isoformat()

    updated = (
        client.table("inventory_items")
        .update(changes)
        .eq("id", item_id)
        .eq("shop_id", shop["id"])
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=500, detail="Could not update inventory item")
    return _to_out(updated.data[0])


def list_live_inventory() -> list[dict]:
    client = get_supabase()
    items = (
        client.table("inventory_items")
        .select("*")
        .gt("quantity", 0)
        .execute()
    )
    shops = client.table("shops").select("*").execute()
    shops_by_id = {shop["id"]: shop for shop in shops.data or []}
    live = []
    for item in items.data or []:
        shop = shops_by_id.get(item["shop_id"])
        if not shop:
            continue
        live.append({"item": item, "shop": shop})
    return live


def maybe_geocode_shop(shop: dict) -> dict:
    if shop.get("lat") is not None and shop.get("lng") is not None:
        return shop
    place = shop.get("location") or shop.get("neighborhood") or shop.get("address")
    coords = maps_service.geocode(place) if place else None
    if not coords:
        return shop
    shop = {**shop, "lat": coords[0], "lng": coords[1]}
    get_supabase().table("shops").update({"lat": coords[0], "lng": coords[1]}).eq("id", shop["id"]).execute()
    return shop
