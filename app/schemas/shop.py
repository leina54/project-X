from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.utils.kenya import canonical_county


class ShopCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    location: str = Field(min_length=1, max_length=200)
    county: str = Field(min_length=1, max_length=100)
    address: str | None = None
    neighborhood: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("name", "location")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank")
        return value

    @field_validator("county")
    @classmethod
    def validate_county(cls, value: str) -> str:
        return canonical_county(value.strip())

    @model_validator(mode="after")
    def require_coordinate_pair(self) -> "ShopCreate":
        if (self.lat is None) != (self.lng is None):
            raise ValueError("lat and lng must be provided together")
        return self


class ShopUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    county: str | None = Field(default=None, min_length=1, max_length=100)
    address: str | None = None
    neighborhood: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("name", "location")
    @classmethod
    def strip_nonblank_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank")
        return value

    @field_validator("county")
    @classmethod
    def validate_county(cls, value: str | None) -> str | None:
        return canonical_county(value.strip()) if value is not None else None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "ShopUpdate":
        for field in ("name", "location", "county"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ShopOut(BaseModel):
    id: str
    owner_id: str
    name: str
    location: str | None = None
    county: str | None = None
    address: str | None = None
    neighborhood: str | None = None
    lat: float | None = None
    lng: float | None = None
    created_at: datetime | None = None
