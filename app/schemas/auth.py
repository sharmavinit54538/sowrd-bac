from typing import Optional
from pydantic import EmailStr

from app.schemas.base import CamelModel
from app.schemas.user import UserResponse


class LoginRequest(CamelModel):
    email: EmailStr
    password: str


class Token(CamelModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenPayload(CamelModel):
    sub: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None

