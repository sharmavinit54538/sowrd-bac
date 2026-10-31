from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.models.inventory_log import InventoryLog
from app.models.product import Product
from app.models.user import User
from app.schemas.inventory import (
    InventoryAdjustmentCreate,
    InventoryLogResponse,
    InventorySummaryResponse,
)
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/inventory", tags=["Inventory Operations"])


@router.post("/adjust", response_model=InventoryLogResponse)
def adjust_inventory(
    adj_in: InventoryAdjustmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "INVENTORY_MANAGER"])),
):
    """
    Adjust product stock level with row-level locking (SELECT ... FOR UPDATE).
    Supported actions: STOCK_IN, STOCK_OUT, ADJUSTMENT.
    """
    action = adj_in.action.upper()
    valid_actions = ["STOCK_IN", "STOCK_OUT", "ADJUSTMENT"]
    if action not in valid_actions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action '{adj_in.action}'. Allowed: {valid_actions}",
        )

    # Atomic transaction with row-level locking
    query = db.query(Product).filter(Product.id == adj_in.product_id)
    if db.bind and db.bind.dialect.name == "postgresql":
        query = query.with_for_update()
    product = query.first()

    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    qty = adj_in.quantity

    if action == "STOCK_IN":
        if qty <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="STOCK_IN quantity must be greater than zero",
            )
        product.total_stock += qty

    elif action == "STOCK_OUT":
        if qty <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="STOCK_OUT quantity must be greater than zero",
            )
        if product.available_stock < qty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient available stock for product '{product.item_name}' (SKU: {product.sku}). "
                    f"Available: {product.available_stock}, Requested deduction: {qty}"
                ),
            )
        product.total_stock -= qty

    elif action == "ADJUSTMENT":
        new_total = product.total_stock + qty
        if new_total < product.reserved_stock:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Adjustment would cause total stock ({new_total}) to fall below "
                    f"reserved stock ({product.reserved_stock}) for '{product.item_name}'."
                ),
            )
        product.total_stock = new_total

    # Create Inventory Log
    inv_log = InventoryLog(
        product_id=product.id,
        action=action,
        quantity=qty,
        notes=adj_in.notes,
        created_by=current_user.name,
    )
    db.add(inv_log)

    client_ip = request.client.host if request.client else None
    create_audit_log(
        db=db,
        user=current_user,
        action=f"INVENTORY_{action}",
        resource_type="INVENTORY",
        resource_id=str(product.id),
        details={
            "sku": product.sku,
            "action": action,
            "quantity": qty,
            "new_total_stock": product.total_stock,
            "available_stock": product.available_stock,
            "notes": adj_in.notes,
        },
        ip_address=client_ip,
    )

    db.commit()
    db.refresh(inv_log)
    return InventoryLogResponse.model_validate(inv_log)


@router.get("/logs", response_model=List[InventoryLogResponse])
def get_inventory_logs(
    product_id: Optional[uuid.UUID] = None,
    action: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "INVENTORY_MANAGER"])),
):
    """Retrieve historical inventory change logs (ADMIN & INVENTORY_MANAGER)."""
    query = db.query(InventoryLog)
    if product_id:
        query = query.filter(InventoryLog.product_id == product_id)
    if action:
        query = query.filter(InventoryLog.action == action.upper())

    logs = query.order_by(InventoryLog.created_at.desc()).offset(skip).limit(limit).all()
    return [InventoryLogResponse.model_validate(log) for log in logs]


@router.get("/summary", response_model=InventorySummaryResponse)
def get_inventory_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "INVENTORY_MANAGER"])),
):
    """Get high-level inventory totals and alerts (ADMIN & INVENTORY_MANAGER)."""
    products = db.query(Product).all()

    total_skus = len(products)
    total_stock_count = sum(p.total_stock or 0 for p in products)
    total_reserved_count = sum(p.reserved_stock or 0 for p in products)
    low_stock_count = sum(1 for p in products if p.available_stock <= p.min_stock_level)

    return InventorySummaryResponse(
        total_skus=total_skus,
        total_stock_count=total_stock_count,
        total_reserved_count=total_reserved_count,
        low_stock_count=low_stock_count,
    )

