import uuid
from datetime import datetime, timezone
import sqlalchemy as sa
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.sql import case

from app.core.database import Base


class Product(Base):
    __tablename__ = "products"

    id = sa.Column(sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku = sa.Column(sa.String(100), unique=True, index=True, nullable=False)
    item_name = sa.Column(sa.String(255), nullable=False)
    technical_specs = sa.Column(sa.Text, nullable=True)
    category = sa.Column(sa.String(100), nullable=True)
    hsn_code = sa.Column(sa.String(20), default="84779000", nullable=False)
    unit = sa.Column(sa.String(20), default="Nos", nullable=False)
    rate = sa.Column(sa.Numeric(12, 2), default=0.00, nullable=False)
    total_stock = sa.Column(sa.Integer, default=0, nullable=False)
    reserved_stock = sa.Column(sa.Integer, default=0, nullable=False)
    min_stock_level = sa.Column(sa.Integer, default=5, nullable=False)
    created_at = sa.Column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    @hybrid_property
    def available_stock(self) -> int:
        total = self.total_stock if self.total_stock is not None else 0
        reserved = self.reserved_stock if self.reserved_stock is not None else 0
        return max(0, total - reserved)

    @available_stock.expression
    def available_stock(cls):
        diff = cls.total_stock - cls.reserved_stock
        return case((diff > 0, diff), else_=0)

    inventory_logs = relationship(
        "InventoryLog",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="desc(InventoryLog.created_at)"
    )

