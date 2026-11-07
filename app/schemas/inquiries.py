from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.matching import ParsedConstraints, SearchRequest, SearchResponse

InquiryStatus = Literal["new", "responded", "closed"]


class SavedSearchOut(BaseModel):
    id: str
    buyer_id: str
    query: str
    parsed_constraints: ParsedConstraints
    created_at: datetime


class SavedSearchCreated(BaseModel):
    id: str
    created_at: datetime
    result: SearchResponse


class ProductInquiryCreate(BaseModel):
    shop_id: str
    item_id: str
    message: str = Field(min_length=1, max_length=1000)

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message must not be blank")
        return value


class ProductInquiryUpdate(BaseModel):
    status: InquiryStatus | None = None
    shop_reply: str | None = Field(default=None, max_length=2000)

    @field_validator("shop_reply")
    @classmethod
    def strip_reply(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Reply must not be blank")
        return value

    @model_validator(mode="after")
    def require_valid_changes(self) -> "ProductInquiryUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide a status or shop reply")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("Status cannot be null")
        return self


class ProductInquiryOut(BaseModel):
    id: str
    buyer_id: str
    shop_id: str
    item_id: str
    message: str
    shop_reply: str | None = None
    status: InquiryStatus
    created_at: datetime
    updated_at: datetime


class SavedSearchRequest(SearchRequest):
    pass
