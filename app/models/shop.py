from datetime import datetime

from pydantic import BaseModel


class Shop(BaseModel):
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
