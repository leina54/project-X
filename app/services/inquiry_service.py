from fastapi import HTTPException, status

from app.db.supabase import get_supabase
from app.models.user import User
from app.schemas.inquiries import (
    ProductInquiryCreate,
    ProductInquiryOut,
    ProductInquiryUpdate,
    SavedSearchCreated,
    SavedSearchOut,
    SavedSearchRequest,
)
from app.services import matching_engine
from app.utils.helpers import utcnow


def create_saved_search(user: User, payload: SavedSearchRequest) -> SavedSearchCreated:
    result = matching_engine.search(payload)
    created = (
        get_supabase()
        .table("saved_searches")
        .insert(
            {
                "buyer_id": user.id,
                "query": payload.query.strip(),
                "parsed_constraints": result.constraints.model_dump(mode="json"),
            }
        )
        .execute()
    )
    if not created.data:
        raise HTTPException(status_code=500, detail="Could not save search inquiry")
    return SavedSearchCreated(
        id=created.data[0]["id"],
        created_at=created.data[0]["created_at"],
        result=result,
    )


def list_saved_searches(
    user: User,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[SavedSearchOut]:
    result = (
        get_supabase()
        .table("saved_searches")
        .select("id,buyer_id,query,parsed_constraints,created_at")
        .eq("buyer_id", user.id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return [SavedSearchOut.model_validate(row) for row in result.data or []]


def delete_saved_search(user: User, search_id: str) -> None:
    client = get_supabase()
    existing = (
        client
        .table("saved_searches")
        .select("id")
        .eq("id", search_id)
        .eq("buyer_id", user.id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved search not found")
    (
        client.table("saved_searches")
        .delete()
        .eq("id", search_id)
        .eq("buyer_id", user.id)
        .execute()
    )


def create_product_inquiry(user: User, payload: ProductInquiryCreate) -> ProductInquiryOut:
    client = get_supabase()
    item = (
        client.table("inventory_items")
        .select("id")
        .eq("id", payload.item_id)
        .eq("shop_id", payload.shop_id)
        .eq("is_active", True)
        .gt("quantity", 0)
        .limit(1)
        .execute()
    )
    if not item.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active in-stock product not found for this shop",
        )

    created = (
        client.table("product_inquiries")
        .insert(
            {
                "buyer_id": user.id,
                "shop_id": payload.shop_id,
                "item_id": payload.item_id,
                "message": payload.message,
            }
        )
        .execute()
    )
    if not created.data:
        raise HTTPException(status_code=500, detail="Could not create product inquiry")
    return ProductInquiryOut.model_validate(created.data[0])


def list_product_inquiries(
    user: User,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[ProductInquiryOut]:
    client = get_supabase()
    query = client.table("product_inquiries").select("*")
    if user.role == "buyer":
        query = query.eq("buyer_id", user.id)
    else:
        shops = (
            client.table("shops")
            .select("id")
            .eq("owner_id", user.id)
            .execute()
        )
        shop_ids = [shop["id"] for shop in shops.data or []]
        if not shop_ids:
            return []
        query = query.in_("shop_id", shop_ids)
    result = (
        query.order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return [ProductInquiryOut.model_validate(row) for row in result.data or []]


def update_product_inquiry(
    user: User,
    inquiry_id: str,
    payload: ProductInquiryUpdate,
) -> ProductInquiryOut:
    client = get_supabase()
    shops = (
        client.table("shops")
        .select("id")
        .eq("owner_id", user.id)
        .execute()
    )
    shop_ids = [shop["id"] for shop in shops.data or []]
    if not shop_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inquiry not found")

    changes = payload.model_dump(exclude_unset=True)
    if "shop_reply" in changes and changes["shop_reply"] is not None:
        if "status" not in changes:
            changes["status"] = "responded"
    changes["updated_at"] = utcnow().isoformat()
    updated = (
        client.table("product_inquiries")
        .update(changes)
        .eq("id", inquiry_id)
        .in_("shop_id", shop_ids)
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inquiry not found")
    return ProductInquiryOut.model_validate(updated.data[0])
