from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.routers import (
    audit_router,
    auth_router,
    company_router,
    customers_router,
    dashboard_router,
    documents_router,
    inventory_router,
    products_router,
    users_router,
)
from app.seed import seed_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager:
    - Creates database tables if not existing
    - Seeds initial ERP records for Sword Innovations on clean startup
    """
    # Create tables
    Base.metadata.create_all(bind=engine)

    # Automatically seed records if tables are fresh
    with SessionLocal() as db:
        seed_db(db)

    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description=(
        "Sword Innovations - Production-Grade B2B Manufacturing Inventory, "
        "Order Fulfilment & GST Billing ERP Backend API."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Configuration
origins = settings.CORS_ORIGINS
if isinstance(origins, str):
    origins = [origins]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers under /api
api_prefix = settings.API_V1_STR
app.include_router(auth_router, prefix=api_prefix)
app.include_router(users_router, prefix=api_prefix)
app.include_router(company_router, prefix=api_prefix)
app.include_router(customers_router, prefix=api_prefix)
app.include_router(products_router, prefix=api_prefix)
app.include_router(inventory_router, prefix=api_prefix)
app.include_router(documents_router, prefix=api_prefix)
app.include_router(dashboard_router, prefix=api_prefix)
app.include_router(audit_router, prefix=api_prefix)


@app.get("/", tags=["Health"])
def root():
    """Root health and status endpoint."""
    return {
        "status": "online",
        "service": "Sword Innovations ERP Backend",
        "version": "1.0.0",
        "docsUrl": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Microservice health check endpoint for container orchestrators."""
    return {"status": "healthy"}

