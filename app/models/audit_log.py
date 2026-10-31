import uuid
from datetime import datetime, timezone
import sqlalchemy as sa

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = sa.Column(sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = sa.Column(sa.String(100), nullable=True)
    user_email = sa.Column(sa.String(255), nullable=True)
    user_role = sa.Column(sa.String(50), nullable=True)
    action = sa.Column(sa.String(100), nullable=False, index=True)
    resource_type = sa.Column(sa.String(50), nullable=False, index=True)
    resource_id = sa.Column(sa.String(100), nullable=True)
    details = sa.Column(sa.JSON, nullable=True)
    ip_address = sa.Column(sa.String(50), nullable=True)
    created_at = sa.Column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

