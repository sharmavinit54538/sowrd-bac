from typing import List
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/users", tags=["Users Management"])


@router.get("", response_model=List[UserResponse])
def get_all_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    """List all registered users (ADMIN only)."""
    users = db.query(User).offset(skip).limit(limit).all()
    return [UserResponse.model_validate(u) for u in users]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    """Create a new user account (ADMIN only)."""
    existing_user = db.query(User).filter(User.email == user_in.email.strip().lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    valid_roles = ["ADMIN", "INVENTORY_MANAGER", "SELLER"]
    if user_in.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Role must be one of {valid_roles}.",
        )

    user = User(
        name=user_in.name,
        email=user_in.email.strip().lower(),
        password_hash=get_password_hash(user_in.password),
        role=user_in.role,
        phone=user_in.phone,
        is_active=user_in.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client_ip = request.client.host if request.client else None
    create_audit_log(
        db=db,
        user=current_user,
        action="CREATE_USER",
        resource_type="USER",
        resource_id=str(user.id),
        details={"name": user.name, "email": user.email, "role": user.role},
        ip_address=client_ip,
    )
    db.commit()

    return UserResponse.model_validate(user)


@router.get("/{id}", response_model=UserResponse)
def get_user_by_id(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    """Get single user by UUID (ADMIN only)."""
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse.model_validate(user)


@router.put("/{id}", response_model=UserResponse)
def update_user(
    id: uuid.UUID,
    user_in: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    """Update user attributes (ADMIN only)."""
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user_in.email and user_in.email.strip().lower() != user.email:
        existing = db.query(User).filter(User.email == user_in.email.strip().lower()).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists.",
            )
        user.email = user_in.email.strip().lower()

    if user_in.name is not None:
        user.name = user_in.name
    if user_in.role is not None:
        valid_roles = ["ADMIN", "INVENTORY_MANAGER", "SELLER"]
        if user_in.role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role. Role must be one of {valid_roles}.",
            )
        user.role = user_in.role
    if user_in.phone is not None:
        user.phone = user_in.phone
    if user_in.is_active is not None:
        user.is_active = user_in.is_active
    if user_in.password:
        user.password_hash = get_password_hash(user_in.password)

    db.commit()
    db.refresh(user)

    client_ip = request.client.host if request.client else None
    create_audit_log(
        db=db,
        user=current_user,
        action="UPDATE_USER",
        resource_type="USER",
        resource_id=str(user.id),
        details={"name": user.name, "email": user.email, "role": user.role},
        ip_address=client_ip,
    )
    db.commit()

    return UserResponse.model_validate(user)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    """Delete a user account (ADMIN only)."""
    if current_user.id == id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own active administrator account.",
        )
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    client_ip = request.client.host if request.client else None
    create_audit_log(
        db=db,
        user=current_user,
        action="DELETE_USER",
        resource_type="USER",
        resource_id=str(user.id),
        details={"name": user.name, "email": user.email},
        ip_address=client_ip,
    )

    db.delete(user)
    db.commit()
    return None

