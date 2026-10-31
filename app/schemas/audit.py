from datetime import datetime
from typing import Any, Dict, Optional
import uuid

from app.schemas.base import CamelModel


class AuditLogResponse(CamelModel):
    id: uuid.UUID
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime

