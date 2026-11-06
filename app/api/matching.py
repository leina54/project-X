from fastapi import APIRouter

from app.schemas.matching import SearchRequest, SearchResponse
from app.services import matching_engine

router = APIRouter(prefix="/matching", tags=["matching"])


@router.post("/search", response_model=SearchResponse)
def search(payload: SearchRequest) -> SearchResponse:
    return matching_engine.search(payload)
