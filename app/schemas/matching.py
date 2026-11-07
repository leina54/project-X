from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.utils.kenya import canonical_county


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    county: str | None = Field(default=None, min_length=1, max_length=100)
    user_lat: float | None = Field(default=None, ge=-90, le=90)
    user_lng: float | None = Field(default=None, ge=-180, le=180)
    limit: int = Field(default=10, ge=1, le=50)

    @model_validator(mode="after")
    def require_coordinate_pair(self) -> "SearchRequest":
        if (self.user_lat is None) != (self.user_lng is None):
            raise ValueError("user_lat and user_lng must be provided together")
        return self

    @field_validator("location", "county")
    @classmethod
    def strip_location_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Location fields must not be blank")
        return value

    @field_validator("county")
    @classmethod
    def validate_county(cls, value: str | None) -> str | None:
        return canonical_county(value) if value is not None else None


class ParsedConstraints(BaseModel):
    product: str
    max_price_kes: float | None = None
    target_price_kes: float | None = None
    location: str | None = None
    county: str | None = None
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
