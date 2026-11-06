from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr

Role = Literal["buyer", "shop"]


class User(BaseModel):
    id: str
    email: EmailStr
    hashed_password: str
    role: Role
    created_at: datetime | None = None


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    role: Role
    created_at: datetime | None = None
