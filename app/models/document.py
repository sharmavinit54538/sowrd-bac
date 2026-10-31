import uuid
from datetime import date, datetime, timezone
import sqlalchemy as sa
from sqlalchemy.orm import relationship

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = sa.Column(sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_type = sa.Column(sa.String(50), nullable=False, index=True)
    # QUOTATION | PROFORMA_INVOICE | TAX_INVOICE | DELIVERY_CHALLAN | PACKING_SLIP
    doc_number = sa.Column(sa.String(50), unique=True, index=True, nullable=False)
    doc_date = sa.Column(sa.Date, nullable=False, default=date.today)
    status = sa.Column(sa.String(50), nullable=False, default="DRAFT", index=True)
    # DRAFT | SENT | APPROVED | STOCK_RESERVED | FULFILLED | CANCELLED

    parent_doc_id = sa.Column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    parent_doc_number = sa.Column(sa.String(50), nullable=True)
    customer_id = sa.Column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Order Details
    buyer_order_ref = sa.Column(sa.String(100), nullable=True)
    buyer_order_date = sa.Column(sa.Date, nullable=True)
    mode_of_dispatch = sa.Column(sa.String(100), nullable=True)
    mode_of_payment = sa.Column(sa.String(100), nullable=True)
    place_of_supply = sa.Column(sa.String(100), nullable=True)

    # Financials
    sub_total = sa.Column(sa.Numeric(12, 2), default=0.00, nullable=False)
    cgst_rate = sa.Column(sa.Numeric(5, 2), default=0.00, nullable=False)
    cgst_amount = sa.Column(sa.Numeric(12, 2), default=0.00, nullable=False)
    sgst_rate = sa.Column(sa.Numeric(5, 2), default=0.00, nullable=False)
    sgst_amount = sa.Column(sa.Numeric(12, 2), default=0.00, nullable=False)
    igst_rate = sa.Column(sa.Numeric(5, 2), default=0.00, nullable=False)
    igst_amount = sa.Column(sa.Numeric(12, 2), default=0.00, nullable=False)
    rounding_off = sa.Column(sa.Numeric(6, 2), default=0.00, nullable=False)
    grand_total = sa.Column(sa.Numeric(12, 2), default=0.00, nullable=False)
    amount_in_words = sa.Column(sa.Text, nullable=True)

    # Logistics & Meta
    terms = sa.Column(sa.JSON, default=list, nullable=False)
    remarks = sa.Column(sa.Text, nullable=True)
    parts_value = sa.Column(sa.Numeric(12, 2), default=0.00, nullable=False)
    service_charges_value = sa.Column(sa.Numeric(12, 2), default=0.00, nullable=False)
    job_work_total_value = sa.Column(sa.Numeric(12, 2), default=0.00, nullable=False)
    transporter_name = sa.Column(sa.String(150), nullable=True)
    vehicle_no = sa.Column(sa.String(50), nullable=True)
    dispatch_date = sa.Column(sa.Date, nullable=True)
    pkg_number = sa.Column(sa.String(50), nullable=True)
    gross_weight = sa.Column(sa.String(50), nullable=True)
    payment_note = sa.Column(sa.Text, nullable=True)

    created_by = sa.Column(sa.String(100), nullable=False)
    created_by_role = sa.Column(sa.String(50), nullable=True)
    stock_reserved = sa.Column(sa.Boolean, default=False, nullable=False)
    stock_deducted = sa.Column(sa.Boolean, default=False, nullable=False)
    created_at = sa.Column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    customer = relationship("Customer", back_populates="documents")
    items = relationship(
        "DocumentItem",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentItem.sr",
    )
    parent_doc = relationship("Document", remote_side=[id], foreign_keys=[parent_doc_id])


class DocumentItem(Base):
    __tablename__ = "document_items"

    id = sa.Column(sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = sa.Column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sr = sa.Column(sa.Integer, nullable=False, default=1)
    product_id = sa.Column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    item_name = sa.Column(sa.String(255), nullable=False)
    technical_specs = sa.Column(sa.Text, nullable=True)
    hsn_code = sa.Column(sa.String(20), default="84779000", nullable=False)
    qty = sa.Column(sa.Integer, default=1, nullable=False)
    unit = sa.Column(sa.String(20), default="Nos", nullable=False)
    rate = sa.Column(sa.Numeric(12, 2), default=0.00, nullable=False)
    taxable_value = sa.Column(sa.Numeric(12, 2), default=0.00, nullable=False)
    net_weight = sa.Column(sa.String(50), nullable=True)

    # Relationships
    document = relationship("Document", back_populates="items")
    product = relationship("Product")

