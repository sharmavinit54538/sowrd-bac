from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_roles
from app.models.customer import Customer
from app.models.user import User
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/customers", tags=["Customers Management"])


@router.get("", response_model=List[CustomerResponse])
def get_customers(
    search: Optional[str] = Query(None, description="Search by company name, contact, gstin, or email"),
    state_code: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all ERP customers (Authorized for all authenticated roles)."""
    query = db.query(Customer)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Customer.company_name.ilike(s),
                Customer.contact_person.ilike(s),
                Customer.gstin.ilike(s),
                Customer.email.ilike(s),
            )
        )
    if state_code:
        query = query.filter(Customer.state_code == state_code.strip())

    customers = query.order_by(Customer.company_name.asc()).offset(skip).limit(limit).all()
    return [CustomerResponse.model_validate(c) for c in customers]


@router.get("/{id}", response_model=CustomerResponse)
def get_customer_by_id(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get customer details by UUID."""
    customer = db.query(Customer).filter(Customer.id == id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return CustomerResponse.model_validate(customer)


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    customer_in: CustomerCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    """Create a new customer (ADMIN only)."""
    customer = Customer(
        company_name=customer_in.company_name,
        billing_address=customer_in.billing_address,
        shipping_address=customer_in.shipping_address or customer_in.billing_address,
        state_name=customer_in.state_name,
        state_code=customer_in.state_code.strip().zfill(2),
        gstin=customer_in.gstin.strip().upper() if customer_in.gstin else None,
        contact_person=customer_in.contact_person,
        phone=customer_in.phone,
        email=customer_in.email,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    client_ip = request.client.host if request.client else None
    create_audit_log(
        db=db,
        user=current_user,
        action="CREATE_CUSTOMER",
        resource_type="CUSTOMER",
        resource_id=str(customer.id),
        details={"company_name": customer.company_name, "state_code": customer.state_code},
        ip_address=client_ip,
    )
    db.commit()

    return CustomerResponse.model_validate(customer)


@router.put("/{id}", response_model=CustomerResponse)
def update_customer(
    id: uuid.UUID,
    customer_in: CustomerUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    """Update customer details (ADMIN only)."""
    customer = db.query(Customer).filter(Customer.id == id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    update_data = customer_in.model_dump(exclude_unset=True)
    if "state_code" in update_data and update_data["state_code"]:
        update_data["state_code"] = update_data["state_code"].strip().zfill(2)
    if "gstin" in update_data and update_data["gstin"]:
        update_data["gstin"] = update_data["gstin"].strip().upper()

    for field, value in update_data.items():
        setattr(customer, field, value)

    db.commit()
    db.refresh(customer)

    client_ip = request.client.host if request.client else None
    create_audit_log(
        db=db,
        user=current_user,
        action="UPDATE_CUSTOMER",
        resource_type="CUSTOMER",
        resource_id=str(customer.id),
        details=update_data,
        ip_address=client_ip,
    )
    db.commit()

    return CustomerResponse.model_validate(customer)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    """Delete a customer record (ADMIN only)."""
    customer = db.query(Customer).filter(Customer.id == id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    client_ip = request.client.host if request.client else None
    create_audit_log(
        db=db,
        user=current_user,
        action="DELETE_CUSTOMER",
        resource_type="CUSTOMER",
        resource_id=str(customer.id),
        details={"company_name": customer.company_name},
        ip_address=client_ip,
    )

    db.delete(customer)
    db.commit()
    return None

