from datetime import datetime
from typing import Optional
import uuid

from app.schemas.base import CamelModel


class InventoryAdjustmentCreate(CamelModel):
    product_id: uuid.UUID
    action: str  # STOCK_IN | STOCK_OUT | ADJUSTMENT
    quantity: int
    notes: Optional[str] = None


class InventoryLogResponse(CamelModel):
    id: uuid.UUID
    product_id: uuid.UUID
    action: str
    quantity: int
    reference_doc_id: Optional[uuid.UUID] = None
    reference_doc_number: Optional[str] = None
    notes: Optional[str] = None
    created_by: str
    created_at: datetime


class InventorySummaryResponse(CamelModel):
    total_skus: int
    total_stock_count: int
    total_reserved_count: int
    low_stock_count: int

