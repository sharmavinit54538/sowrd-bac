from typing import List, Optional
from pydantic import EmailStr

from app.schemas.base import CamelModel


class CompanyProfileBase(CamelModel):
    name: str = "SWORD INNOVATIONS"
    tagline: Optional[str] = None
    address: str
    city: str = "Jaipur"
    state_name: str = "Rajasthan"
    state_code: str = "08"
    gstin: str = "08AGIPN6872D1Z4"
    pan: str = "AGIPN6872D"
    iec: str = "AGIPN6872D"
    phones: List[str] = []
    email: EmailStr = "sales@swordinn.biz"
    founder: Optional[str] = None
    founder_mobile: Optional[str] = None
    jurisdiction: str = "Jaipur"


class CompanyProfileUpdate(CamelModel):
    name: Optional[str] = None
    tagline: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state_name: Optional[str] = None
    state_code: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    iec: Optional[str] = None
    phones: Optional[List[str]] = None
    email: Optional[EmailStr] = None
    founder: Optional[str] = None
    founder_mobile: Optional[str] = None
    jurisdiction: Optional[str] = None


class CompanyProfileResponse(CompanyProfileBase):
    id: int

