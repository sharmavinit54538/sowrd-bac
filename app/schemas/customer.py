from datetime import datetime
from typing import Optional
import uuid
from pydantic import EmailStr

from app.schemas.base import CamelModel


class CustomerBase(CamelModel):
    company_name: str
    billing_address: str
    shipping_address: Optional[str] = None
    state_name: str
    state_code: str
    gstin: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(CamelModel):
    company_name: Optional[str] = None
    billing_address: Optional[str] = None
    shipping_address: Optional[str] = None
    state_name: Optional[str] = None
    state_code: Optional[str] = None
    gstin: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None


class CustomerResponse(CustomerBase):
    id: uuid.UUID
    created_at: datetime

