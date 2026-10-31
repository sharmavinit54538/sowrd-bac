from decimal import Decimal
from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.document import Document
from app.models.product import Product
from app.models.user import User
from app.schemas.base import CamelModel
from app.schemas.document import DocumentResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard & Analytics"])


class DashboardStatsResponse(CamelModel):
    total_revenue: Decimal
    active_quotations: int
    pending_orders: int
    low_stock_count: int
    total_customers: int
    total_products: int
    recent_documents: List[DocumentResponse]
    recent_activity: List[Dict[str, Any]]


@router.get("/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Returns real-time ERP summary metrics, key performance indicators,
    and recent activity records for the Sword Innovations operations cockpit.
    """
    # 1. Total Invoiced Revenue
    revenue_res = (
        db.query(func.coalesce(func.sum(Document.grand_total), 0.00))
        .filter(Document.doc_type == "TAX_INVOICE", Document.status != "CANCELLED")
        .scalar()
    )
    total_revenue = Decimal(str(revenue_res))

    # 2. Active Quotations count
    active_quotations = (
        db.query(func.count(Document.id))
        .filter(Document.doc_type == "QUOTATION", Document.status.in_(["DRAFT", "SENT", "APPROVED"]))
        .scalar()
        or 0
    )

    # 3. Pending Orders (Proforma Invoices not yet fulfilled or cancelled)
    pending_orders = (
        db.query(func.count(Document.id))
        .filter(
            Document.doc_type == "PROFORMA_INVOICE",
            Document.status.notin_(["FULFILLED", "CANCELLED"]),
        )
        .scalar()
        or 0
    )

    # 4. Low stock products count
    all_products = db.query(Product).all()
    low_stock_count = sum(1 for p in all_products if p.available_stock <= p.min_stock_level)

    # 5. Customer & Product counts
    total_customers = db.query(func.count(Customer.id)).scalar() or 0
    total_products = len(all_products)

    # 6. Recent Documents (last 5)
    recent_docs = (
        db.query(Document)
        .order_by(Document.created_at.desc())
        .limit(5)
        .all()
    )

    # 7. Recent Activity (last 8 audit logs)
    audit_logs = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(8)
        .all()
    )
    recent_activity = [
        {
            "id": str(log.id),
            "action": log.action,
            "resourceType": log.resource_type,
            "resourceId": log.resource_id,
            "userEmail": log.user_email,
            "details": log.details,
            "createdAt": log.created_at.isoformat() if log.created_at else None,
        }
        for log in audit_logs
    ]

    return DashboardStatsResponse(
        total_revenue=total_revenue,
        active_quotations=active_quotations,
        pending_orders=pending_orders,
        low_stock_count=low_stock_count,
        total_customers=total_customers,
        total_products=total_products,
        recent_documents=[DocumentResponse.model_validate(d) for d in recent_docs],
        recent_activity=recent_activity,
    )

