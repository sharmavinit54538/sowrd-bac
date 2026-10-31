import uuid
from datetime import datetime, timezone
import sqlalchemy as sa
from sqlalchemy.orm import relationship

from app.core.database import Base


class InventoryLog(Base):
    __tablename__ = "inventory_logs"

    id = sa.Column(sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = sa.Column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action = sa.Column(sa.String(50), nullable=False)
    # STOCK_IN | STOCK_OUT | RESERVED | UNRESERVED | ADJUSTMENT
    quantity = sa.Column(sa.Integer, nullable=False)
    reference_doc_id = sa.Column(sa.UUID(as_uuid=True), nullable=True)
    reference_doc_number = sa.Column(sa.String(50), nullable=True)
    notes = sa.Column(sa.Text, nullable=True)
    created_by = sa.Column(sa.String(100), nullable=False)
    created_at = sa.Column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    product = relationship("Product", back_populates="inventory_logs")

