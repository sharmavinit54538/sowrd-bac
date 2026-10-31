from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_roles
from app.models.product import Product
from app.models.user import User
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/products", tags=["Master Products"])


@router.get("", response_model=List[ProductResponse])
def get_products(
    search: Optional[str] = Query(None, description="Search by SKU, item name, or category"),
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all Master Products with dynamic available stock calculation."""
    query = db.query(Product)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Product.sku.ilike(s),
                Product.item_name.ilike(s),
                Product.category.ilike(s),
                Product.technical_specs.ilike(s),
            )
        )
    if category:
        query = query.filter(Product.category.ilike(f"%{category.strip()}%"))

    products = query.order_by(Product.sku.asc()).offset(skip).limit(limit).all()
    return [ProductResponse.model_validate(p) for p in products]


@router.get("/low-stock", response_model=List[ProductResponse])
def get_low_stock_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retrieve products where available stock is below or equal to min stock level."""
    products = db.query(Product).all()
    low_stock_items = [p for p in products if p.available_stock <= p.min_stock_level]
    return [ProductResponse.model_validate(p) for p in low_stock_items]


@router.get("/{id}", response_model=ProductResponse)
def get_product_by_id(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get single product detail with available stock."""
    product = db.query(Product).filter(Product.id == id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return ProductResponse.model_validate(product)


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    product_in: ProductCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    """Create a new Master Product (ADMIN only)."""
    existing = db.query(Product).filter(Product.sku == product_in.sku.strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product with SKU '{product_in.sku}' already exists.",
        )

    product = Product(
        sku=product_in.sku.strip(),
        item_name=product_in.item_name,
        technical_specs=product_in.technical_specs,
        category=product_in.category,
        hsn_code=product_in.hsn_code,
        unit=product_in.unit,
        rate=product_in.rate,
        total_stock=product_in.total_stock,
        reserved_stock=product_in.reserved_stock,
        min_stock_level=product_in.min_stock_level,
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    client_ip = request.client.host if request.client else None
    create_audit_log(
        db=db,
        user=current_user,
        action="CREATE_PRODUCT",
        resource_type="PRODUCT",
        resource_id=str(product.id),
        details={"sku": product.sku, "item_name": product.item_name, "rate": float(product.rate)},
        ip_address=client_ip,
    )
    db.commit()

    return ProductResponse.model_validate(product)


@router.put("/{id}", response_model=ProductResponse)
def update_product(
    id: uuid.UUID,
    product_in: ProductUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    """Update a Master Product (ADMIN only)."""
    product = db.query(Product).filter(Product.id == id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    if product_in.sku and product_in.sku.strip() != product.sku:
        existing = db.query(Product).filter(Product.sku == product_in.sku.strip()).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product with SKU '{product_in.sku}' already exists.",
            )
        product.sku = product_in.sku.strip()

    update_data = product_in.model_dump(exclude_unset=True)
    if "sku" in update_data:
        del update_data["sku"]

    for field, value in update_data.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)

    client_ip = request.client.host if request.client else None
    create_audit_log(
        db=db,
        user=current_user,
        action="UPDATE_PRODUCT",
        resource_type="PRODUCT",
        resource_id=str(product.id),
        details={"sku": product.sku, "item_name": product.item_name},
        ip_address=client_ip,
    )
    db.commit()

    return ProductResponse.model_validate(product)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    """Delete a Master Product (ADMIN only)."""
    product = db.query(Product).filter(Product.id == id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    client_ip = request.client.host if request.client else None
    create_audit_log(
        db=db,
        user=current_user,
        action="DELETE_PRODUCT",
        resource_type="PRODUCT",
        resource_id=str(product.id),
        details={"sku": product.sku, "item_name": product.item_name},
        ip_address=client_ip,
    )

    db.delete(product)
    db.commit()
    return None

