from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_current_user, require_buyer_user, require_shop_user
from app.models.user import User
from app.schemas.inquiries import (
    ProductInquiryCreate,
    ProductInquiryOut,
    ProductInquiryUpdate,
    SavedSearchCreated,
    SavedSearchOut,
    SavedSearchRequest,
)
from app.services import inquiry_service

router = APIRouter(prefix="/inquiries", tags=["inquiries"])


@router.post(
    "/searches",
    response_model=SavedSearchCreated,
    status_code=status.HTTP_201_CREATED,
)
def save_search(
    payload: SavedSearchRequest,
    user: User = Depends(require_buyer_user),
) -> SavedSearchCreated:
    return inquiry_service.create_saved_search(user, payload)


@router.get("/searches", response_model=list[SavedSearchOut])
def list_searches(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_buyer_user),
) -> list[SavedSearchOut]:
    return inquiry_service.list_saved_searches(user, limit=limit, offset=offset)


@router.delete("/searches/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_search(
    search_id: str,
    user: User = Depends(require_buyer_user),
) -> Response:
    inquiry_service.delete_saved_search(user, search_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/products",
    response_model=ProductInquiryOut,
    status_code=status.HTTP_201_CREATED,
)
def create_product_request(
    payload: ProductInquiryCreate,
    user: User = Depends(require_buyer_user),
) -> ProductInquiryOut:
    return inquiry_service.create_product_inquiry(user, payload)


@router.get("/products", response_model=list[ProductInquiryOut])
def list_product_requests(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
) -> list[ProductInquiryOut]:
    return inquiry_service.list_product_inquiries(user, limit=limit, offset=offset)


@router.patch("/products/{inquiry_id}", response_model=ProductInquiryOut)
def update_product_request(
    inquiry_id: str,
    payload: ProductInquiryUpdate,
    user: User = Depends(require_shop_user),
) -> ProductInquiryOut:
    return inquiry_service.update_product_inquiry(user, inquiry_id, payload)
