import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Dict, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend directory is in python search path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Configure Test Database URL (SQLite in-memory with StaticPool for fast isolated tests)
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
connect_args = {}
if "sqlite" in TEST_DATABASE_URL:
    connect_args["check_same_thread"] = False

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args=connect_args,
    poolclass=StaticPool if "sqlite" in TEST_DATABASE_URL else None,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Rebind app.core.database engine and SessionLocal
import app.core.database as db_module
db_module.engine = test_engine
db_module.SessionLocal = TestingSessionLocal

from app.core.database import Base, get_db
from app.core.security import create_access_token, get_password_hash
from app.models.audit_log import AuditLog
from app.models.company import CompanyProfile
from app.models.customer import Customer
from app.models.document import Document, DocumentItem
from app.models.inventory_log import InventoryLog
from app.models.product import Product
from app.models.user import User
from app.main import app


def _seed_baseline(db: Session) -> Dict[str, any]:
    """Seed foundational test baseline: Company profile, 3 RBAC users, 2 customers, 2 products."""
    # 1. Company Profile (Jaipur, Rajasthan "08")
    company = CompanyProfile(
        id=1,
        name="SWORD INNOVATIONS",
        tagline="Precision Tooling & Pelletizer Rotors",
        address="Plot No. G-12, RIICO Industrial Area, Mansarovar",
        city="Jaipur",
        state_name="Rajasthan",
        state_code="08",
        gstin="08AGIPN6872D1Z4",
        pan="AGIPN6872D",
        iec="AGIPN6872D",
        phones=["+91 98290 12345"],
        email="sales@swordinn.biz",
        founder="Er. Rajesh Sharma",
        founder_mobile="+91 98290 12345",
        jurisdiction="Jaipur",
    )
    db.add(company)

    # 2. 3 Users with bcrypt password 'password123'
    pwd_hash = get_password_hash("password123")
    admin_user = User(
        name="Admin User",
        email="admin@swordinn.biz",
        password_hash=pwd_hash,
        role="ADMIN",
        phone="+91 98290 11111",
        is_active=True,
    )
    inv_user = User(
        name="Inventory Manager",
        email="inventory@swordinn.biz",
        password_hash=pwd_hash,
        role="INVENTORY_MANAGER",
        phone="+91 98290 22222",
        is_active=True,
    )
    seller_user = User(
        name="Sales Executive",
        email="sales@swordinn.biz",
        password_hash=pwd_hash,
        role="SELLER",
        phone="+91 98290 33333",
        is_active=True,
    )
    db.add_all([admin_user, inv_user, seller_user])
    db.flush()

    # 3. 2 Test Customers (Intra-state Rajasthan '08' vs Inter-state Maharashtra '27')
    cust_intra = Customer(
        company_name="Rajasthan Precision Works",
        billing_address="E-12, RIICO Mansarovar, Jaipur, Rajasthan",
        shipping_address="E-12, RIICO Mansarovar, Jaipur, Rajasthan",
        state_name="Rajasthan",
        state_code="08",
        gstin="08AACCD9433H1ZK",
        contact_person="Ravi Sharma",
        phone="+91 98290 99999",
        email="procurement@rajasthanprecision.com",
    )
    cust_inter = Customer(
        company_name="Maharashtra Polymer Ltd",
        billing_address="Plot 55, MIDC Pawane, Navi Mumbai, Maharashtra",
        shipping_address="Plot 55, MIDC Pawane, Navi Mumbai, Maharashtra",
        state_name="Maharashtra",
        state_code="27",
        gstin="27AAFCD7590Q1ZS",
        contact_person="Amit Patwardhan",
        phone="+91 98205 88888",
        email="purchases@mahapoly.com",
    )
    db.add_all([cust_intra, cust_inter])
    db.flush()

    # 4. 2 Test Master Products
    p1 = Product(
        sku="TEST-ROTOR-01",
        item_name="PUSG-200-30T-SL Rotor Assembly",
        technical_specs="30-Teeth Stellite-tipped rotor",
        category="Pelletizer Rotors",
        hsn_code="84779000",
        unit="Nos",
        rate=Decimal("50000.00"),
        total_stock=20,
        reserved_stock=0,
        min_stock_level=5,
    )
    p2 = Product(
        sku="TEST-BLADE-02",
        item_name="PUSG-200-4E-CE Bed Knife Ceramic",
        technical_specs="Solid ceramic bed knife",
        category="Bed Knives",
        hsn_code="84779000",
        unit="Nos",
        rate=Decimal("100000.00"),
        total_stock=10,
        reserved_stock=0,
        min_stock_level=2,
    )
    db.add_all([p1, p2])
    db.commit()

    return {
        "admin_user": admin_user,
        "inv_user": inv_user,
        "seller_user": seller_user,
        "cust_intra": cust_intra,
        "cust_inter": cust_inter,
        "p1": p1,
        "p2": p2,
    }


@pytest.fixture(autouse=True)
def setup_test_database():
    """Create fresh schema and baseline records before each test."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    with TestingSessionLocal() as db:
        _seed_baseline(db)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provides a transactional database session for manual state assertions in tests."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient bound directly to FastAPI app with get_db dependency override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_headers(db_session: Session) -> Dict[str, str]:
    """Bearer token headers for authenticated ADMIN."""
    admin = db_session.query(User).filter(User.email == "admin@swordinn.biz").first()
    token = create_access_token(subject=str(admin.id), role=admin.role, email=admin.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def inventory_headers(db_session: Session) -> Dict[str, str]:
    """Bearer token headers for authenticated INVENTORY_MANAGER."""
    inv = db_session.query(User).filter(User.email == "inventory@swordinn.biz").first()
    token = create_access_token(subject=str(inv.id), role=inv.role, email=inv.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seller_headers(db_session: Session) -> Dict[str, str]:
    """Bearer token headers for authenticated SELLER."""
    seller = db_session.query(User).filter(User.email == "sales@swordinn.biz").first()
    token = create_access_token(subject=str(seller.id), role=seller.role, email=seller.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def unauthorized_headers() -> Dict[str, str]:
    """Malformed or invalid token header."""
    return {"Authorization": "Bearer invalid.expired.token.jwt"}
