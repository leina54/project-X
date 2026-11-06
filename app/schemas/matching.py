from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    user_lat: float | None = Field(default=None, ge=-90, le=90)
    user_lng: float | None = Field(default=None, ge=-180, le=180)
    limit: int = Field(default=10, ge=1, le=50)


class ParsedConstraints(BaseModel):
    product: str
    max_price_kes: float | None = None
    target_price_kes: float | None = None
    location: str | None = None
    extras: list[str] = Field(default_factory=list)
    parser: str = "offline"


class ScoreBreakdown(BaseModel):
    relevance: float
    price_fit: float
    distance: float
    freshness: float
    total: float


class MatchResult(BaseModel):
    shop_id: str
    shop_name: str
    location: str | None = None
    county: str | None = None
    neighborhood: str | None = None
    item_id: str
    item_name: str
    price_kes: Decimal
    quantity: int
    distance_km: float | None = None
    last_updated_at: datetime | None = None
    score: ScoreBreakdown


class SearchResponse(BaseModel):
    query: str
    constraints: ParsedConstraints
    matches: list[MatchResult]
