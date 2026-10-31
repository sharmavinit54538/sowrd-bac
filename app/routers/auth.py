from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserResponse
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=Token,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {
                        "$ref": "#/components/schemas/LoginRequest"
                    }
                },
                "application/x-www-form-urlencoded": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string"},
                            "password": {"type": "string"},
                        },
                        "required": ["username", "password"],
                    }
                },
            }
        }
    },
)
async def login(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Login endpoint supporting JSON payload, form data, and Swagger UI OAuth2 Authorize flow.
    """
    email = None
    password = None

    content_type = request.headers.get("content-type", "").lower()

    if "application/json" in content_type:
        try:
            body = await request.json()
            if isinstance(body, dict):
                email = body.get("email") or body.get("username")
                password = body.get("password")
        except Exception:
            pass
    elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        try:
            form = await request.form()
            email = form.get("username") or form.get("email")
            password = form.get("password")
        except Exception:
            pass
    else:
        # Fallback: attempt json then form
        try:
            body = await request.json()
            if isinstance(body, dict):
                email = body.get("email") or body.get("username")
                password = body.get("password")
        except Exception:
            try:
                form = await request.form()
                email = form.get("username") or form.get("email")
                password = form.get("password")
            except Exception:
                pass

    if email:
        email = str(email).strip().lower()

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required. Provide JSON {email, password} or form data {username, password}.",
        )

    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account",
        )

    access_token = create_access_token(
        subject=str(user.id),
        email=user.email,
        role=user.role,
    )

    client_ip = request.client.host if request.client else None
    try:
        create_audit_log(
            db=db,
            user=user,
            action="USER_LOGIN",
            resource_type="AUTH",
            resource_id=str(user.id),
            details={"email": user.email, "role": user.role},
            ip_address=client_ip,
        )
        db.commit()
    except Exception:
        db.rollback()

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def read_current_user(
    current_user: User = Depends(get_current_active_user),
):
    """Get profile of current authenticated user."""
    return UserResponse.model_validate(current_user)
