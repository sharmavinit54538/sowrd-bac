from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.company import router as company_router
from app.routers.customers import router as customers_router
from app.routers.products import router as products_router
from app.routers.inventory import router as inventory_router
from app.routers.documents import router as documents_router
from app.routers.dashboard import router as dashboard_router
from app.routers.audit import router as audit_router

__all__ = [
    "auth_router",
    "users_router",
    "company_router",
    "customers_router",
    "products_router",
    "inventory_router",
    "documents_router",
    "dashboard_router",
    "audit_router",
]

