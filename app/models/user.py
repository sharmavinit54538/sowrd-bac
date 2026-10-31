import uuid
from datetime import datetime, timezone
import sqlalchemy as sa
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = sa.Column(sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = sa.Column(sa.String(100), nullable=False)
    email = sa.Column(sa.String(255), unique=True, index=True, nullable=False)
    password_hash = sa.Column(sa.String(255), nullable=False)
    role = sa.Column(sa.String(50), nullable=False)  # ADMIN | INVENTORY_MANAGER | SELLER
    phone = sa.Column(sa.String(50), nullable=True)
    is_active = sa.Column(sa.Boolean, default=True, nullable=False)
    created_at = sa.Column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

