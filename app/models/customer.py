import uuid
from datetime import datetime, timezone
import sqlalchemy as sa
from sqlalchemy.orm import relationship

from app.core.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = sa.Column(sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name = sa.Column(sa.String(255), nullable=False)
    billing_address = sa.Column(sa.Text, nullable=False)
    shipping_address = sa.Column(sa.Text, nullable=True)
    state_name = sa.Column(sa.String(100), nullable=False)
    state_code = sa.Column(sa.String(10), nullable=False)
    gstin = sa.Column(sa.String(20), nullable=True)
    contact_person = sa.Column(sa.String(100), nullable=True)
    phone = sa.Column(sa.String(50), nullable=True)
    email = sa.Column(sa.String(255), nullable=True)
    created_at = sa.Column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    documents = relationship("Document", back_populates="customer", cascade="all, delete-orphan")

