from datetime import datetime
from typing import Optional
import uuid
from pydantic import EmailStr

from app.schemas.base import CamelModel


class UserBase(CamelModel):
    name: str
    email: EmailStr
    role: str  # ADMIN | INVENTORY_MANAGER | SELLER
    phone: Optional[str] = None
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserUpdate(CamelModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserResponse(UserBase):
    id: uuid.UUID
    created_at: datetime

