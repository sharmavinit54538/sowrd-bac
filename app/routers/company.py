from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_roles
from app.models.company import CompanyProfile
from app.models.user import User
from app.schemas.company import CompanyProfileResponse, CompanyProfileUpdate
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/company", tags=["Company Profile"])


@router.get("", response_model=CompanyProfileResponse)
def get_company_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get the Sword Innovations company profile."""
    company = db.query(CompanyProfile).filter(CompanyProfile.id == 1).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not configured. Run database seeding.",
        )
    return CompanyProfileResponse.model_validate(company)


@router.put("", response_model=CompanyProfileResponse)
def update_company_profile(
    company_in: CompanyProfileUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    """Update Sword Innovations company profile (ADMIN only)."""
    company = db.query(CompanyProfile).filter(CompanyProfile.id == 1).first()
    if not company:
        company = CompanyProfile(id=1, name="SWORD INNOVATIONS", address="Jaipur")
        db.add(company)

    update_data = company_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)

    db.commit()
    db.refresh(company)

    client_ip = request.client.host if request.client else None
    create_audit_log(
        db=db,
        user=current_user,
        action="UPDATE_COMPANY_PROFILE",
        resource_type="COMPANY",
        resource_id="1",
        details=update_data,
        ip_address=client_ip,
    )
    db.commit()

    return CompanyProfileResponse.model_validate(company)

