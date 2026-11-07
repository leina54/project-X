from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator


class InventoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200, description="Product description, up to 20 words")
    price_kes: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    quantity: int = Field(ge=0)
    shop_id: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Product name must not be blank")
        if len(value.split()) > 20:
            raise ValueError("Product name must be 20 words or fewer")
        return value


class InventoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200, description="Product description, up to 20 words")
    price_kes: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    quantity: int | None = Field(default=None, ge=0)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Product name must not be blank")
        if len(value.split()) > 20:
            raise ValueError("Product name must be 20 words or fewer")
        return value

    @model_validator(mode="after")
    def require_changes(self) -> "InventoryUpdate":
        if not any(getattr(self, field) is not None for field in self.model_fields_set):
            raise ValueError("At least one inventory field must be provided")
        return self


class InventoryOut(BaseModel):
    id: str
    shop_id: str
    name: str
    normalized_name: str
    price_kes: Decimal
    quantity: int
    is_active: bool = True
    last_updated_at: datetime | None = None
