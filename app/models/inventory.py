from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class InventoryItem(BaseModel):
    id: str
    shop_id: str
    name: str
    normalized_name: str
    price_kes: Decimal
    quantity: int
    last_updated_at: datetime | None = None
