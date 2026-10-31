from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
import uuid
from pydantic import Field

from app.schemas.base import CamelModel
from app.schemas.customer import CustomerResponse


class DocumentItemBase(CamelModel):
    sr: int = 1
    product_id: Optional[uuid.UUID] = None
    item_name: str
    technical_specs: Optional[str] = None
    hsn_code: str = "84779000"
    qty: int = 1
    unit: str = "Nos"
    rate: Decimal = Decimal("0.00")
    taxable_value: Decimal = Decimal("0.00")
    net_weight: Optional[str] = None


class DocumentItemCreate(CamelModel):
    sr: Optional[int] = None
    product_id: Optional[uuid.UUID] = None
    item_name: str
    technical_specs: Optional[str] = None
    hsn_code: Optional[str] = "84779000"
    qty: int = 1
    unit: Optional[str] = "Nos"
    rate: Decimal = Decimal("0.00")
    net_weight: Optional[str] = None


class DocumentItemResponse(DocumentItemBase):
    id: uuid.UUID
    document_id: uuid.UUID


class DocumentBase(CamelModel):
    doc_type: str  # QUOTATION | PROFORMA_INVOICE | TAX_INVOICE | DELIVERY_CHALLAN | PACKING_SLIP
    doc_number: Optional[str] = None
    doc_date: date = Field(default_factory=date.today)
    status: str = "DRAFT"
    parent_doc_id: Optional[uuid.UUID] = None
    parent_doc_number: Optional[str] = None
    customer_id: uuid.UUID
    buyer_order_ref: Optional[str] = None
    buyer_order_date: Optional[date] = None
    mode_of_dispatch: Optional[str] = None
    mode_of_payment: Optional[str] = None
    place_of_supply: Optional[str] = None
    terms: List[str] = []
    remarks: Optional[str] = None
    parts_value: Decimal = Decimal("0.00")
    service_charges_value: Decimal = Decimal("0.00")
    job_work_total_value: Decimal = Decimal("0.00")
    transporter_name: Optional[str] = None
    vehicle_no: Optional[str] = None
    dispatch_date: Optional[date] = None
    pkg_number: Optional[str] = None
    gross_weight: Optional[str] = None
    payment_note: Optional[str] = None


class DocumentCreate(DocumentBase):
    items: List[DocumentItemCreate] = []


class DocumentUpdate(CamelModel):
    doc_date: Optional[date] = None
    status: Optional[str] = None
    customer_id: Optional[uuid.UUID] = None
    buyer_order_ref: Optional[str] = None
    buyer_order_date: Optional[date] = None
    mode_of_dispatch: Optional[str] = None
    mode_of_payment: Optional[str] = None
    place_of_supply: Optional[str] = None
    terms: Optional[List[str]] = None
    remarks: Optional[str] = None
    parts_value: Optional[Decimal] = None
    service_charges_value: Optional[Decimal] = None
    job_work_total_value: Optional[Decimal] = None
    transporter_name: Optional[str] = None
    vehicle_no: Optional[str] = None
    dispatch_date: Optional[date] = None
    pkg_number: Optional[str] = None
    gross_weight: Optional[str] = None
    payment_note: Optional[str] = None
    items: Optional[List[DocumentItemCreate]] = None


class DocumentStatusUpdate(CamelModel):
    status: str


class ChallanCreateRequest(CamelModel):
    transporter_name: Optional[str] = None
    vehicle_no: Optional[str] = None
    dispatch_date: Optional[date] = None
    job_work_total_value: Optional[Decimal] = Decimal("0.00")
    parts_value: Optional[Decimal] = Decimal("0.00")
    remarks: Optional[str] = None
    items: Optional[List[DocumentItemCreate]] = None


class PackingSlipCreateRequest(CamelModel):
    pkg_number: Optional[str] = None
    gross_weight: Optional[str] = None
    remarks: Optional[str] = None
    item_net_weights: Optional[Dict[str, str]] = None  # sr (as str) or item_id -> net_weight


class DocumentResponse(DocumentBase):
    id: uuid.UUID
    sub_total: Decimal
    cgst_rate: Decimal
    cgst_amount: Decimal
    sgst_rate: Decimal
    sgst_amount: Decimal
    igst_rate: Decimal
    igst_amount: Decimal
    rounding_off: Decimal
    grand_total: Decimal
    amount_in_words: Optional[str] = None
    created_by: str
    created_by_role: Optional[str] = None
    stock_reserved: bool
    stock_deducted: bool
    created_at: datetime
    customer: Optional[CustomerResponse] = None
    items: List[DocumentItemResponse] = []

