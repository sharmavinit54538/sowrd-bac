from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog


def create_audit_log(
    db: Session,
    user: Optional[Any],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    """Records an audit trail log entry into PostgreSQL."""
    user_id = str(user.id) if user and hasattr(user, "id") else None
    user_email = user.email if user and hasattr(user, "email") else None
    user_role = user.role if user and hasattr(user, "role") else None

    log_entry = AuditLog(
        user_id=user_id,
        user_email=user_email,
        user_role=user_role,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        details=details,
        ip_address=ip_address,
    )
    db.add(log_entry)
    db.flush()
    return log_entry

