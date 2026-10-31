from datetime import datetime
from decimal import Decimal
from typing import Optional
import uuid

from app.schemas.base import CamelModel


class ProductBase(CamelModel):
    sku: str
    item_name: str
    technical_specs: Optional[str] = None
    category: Optional[str] = None
    hsn_code: str = "84779000"
    unit: str = "Nos"
    rate: Decimal = Decimal("0.00")
    total_stock: int = 0
    reserved_stock: int = 0
    min_stock_level: int = 5


class ProductCreate(ProductBase):
    pass


class ProductUpdate(CamelModel):
    sku: Optional[str] = None
    item_name: Optional[str] = None
    technical_specs: Optional[str] = None
    category: Optional[str] = None
    hsn_code: Optional[str] = None
    unit: Optional[str] = None
    rate: Optional[Decimal] = None
    total_stock: Optional[int] = None
    reserved_stock: Optional[int] = None
    min_stock_level: Optional[int] = None


class ProductResponse(ProductBase):
    id: uuid.UUID
    available_stock: int
    created_at: datetime

