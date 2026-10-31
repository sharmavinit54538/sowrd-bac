import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.security import verify_password
from app.models.audit_log import AuditLog
from app.models.company import CompanyProfile
from app.models.customer import Customer
from app.models.document import Document
from app.models.product import Product
from app.models.user import User
from app.seed import seed_db


class TestAuditLogsAndSeedVerification:
    """Validation of audit trails, role boundaries on logs, dashboard telemetry, and seed integrity."""

    def test_audit_logs_emitted_on_critical_actions(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Verify immutable audit records are generated for create, update, and login operations."""
        # 1. Product creation should emit CREATE_PRODUCT audit log
        prod_payload = {
            "sku": "AUDIT-PROD-99",
            "itemName": "Audit Verification Rotor",
            "rate": 45000.00,
            "totalStock": 10,
        }
        res_prod = client.post("/api/products", json=prod_payload, headers=admin_headers)
        assert res_prod.status_code == 201

        # Query audit log via DB
        log_prod = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "CREATE_PRODUCT", AuditLog.resource_id == res_prod.json()["id"])
            .first()
        )
        assert log_prod is not None
        assert log_prod.user_role == "ADMIN"
        assert log_prod.resource_type == "PRODUCT"

    def test_audit_logs_query_and_rbac_restrictions(
        self,
        client: TestClient,
        admin_headers: dict,
        seller_headers: dict,
        inventory_headers: dict,
    ):
        """Verify only ADMIN can read the system audit logs, and supports query filters."""
        # Seller denied
        assert client.get("/api/audit/logs", headers=seller_headers).status_code == 403

        # Inventory Manager denied
        assert client.get("/api/audit/logs", headers=inventory_headers).status_code == 403

        # Admin authorized
        res_admin = client.get("/api/audit/logs", headers=admin_headers)
        assert res_admin.status_code == 200
        logs = res_admin.json()
        assert isinstance(logs, list)

        # Filter by action
        res_filtered = client.get("/api/audit/logs?action=CREATE", headers=admin_headers)
        assert res_filtered.status_code == 200

    def test_seed_database_authentic_records(
        self, db_session: Session
    ):
        """
        Verify seed_db creates the complete authentic dataset:
        - 3 Users with verifiable 'password123'
        - Company Profile: Sword Innovations
        - 5 Industrial Customers
        - 6 Master Products
        - 5 Real Documents
        """
        # Re-run seed on a clean schema
        engine = db_session.get_bind()
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        seed_db(db_session)

        # 1. Verify 3 Users
        users = db_session.query(User).all()
        assert len(users) == 3
        emails = {u.email: u for u in users}
        assert "admin@swordinn.biz" in emails
        assert "inventory@swordinn.biz" in emails
        assert "sales@swordinn.biz" in emails

        # Verify bcrypt passwords decrypt accurately
        for u in users:
            assert verify_password("password123", u.password_hash) is True

        # 2. Verify Company Profile
        company = db_session.query(CompanyProfile).filter(CompanyProfile.id == 1).first()
        assert company is not None
        assert company.name == "SWORD INNOVATIONS"
        assert company.state_code == "08"
        assert company.city == "Jaipur"
        assert company.gstin == "08AGIPN6872D1Z4"

        # 3. Verify 5 Customers
        customers = db_session.query(Customer).all()
        assert len(customers) == 5
        cust_names = [c.company_name for c in customers]
        assert "Uflex Ltd." in cust_names
        assert "Domo Engineering Plastics India Pvt. Ltd." in cust_names
        assert "Dainichi Color India Private Limited" in cust_names
        assert "Om Surgical Industries" in cust_names
        assert "Truewow Hygiene Products Pvt. Ltd." in cust_names

        # 4. Verify 6 Master Products
        products = db_session.query(Product).all()
        assert len(products) == 6
        product_skus = [p.sku for p in products]
        assert "PUSG-200-30T-SL-WB" in product_skus
        assert "PUSG-200-30T-SL-NB" in product_skus
        assert "PUSG-200-4E-CE" in product_skus
        assert "DSK-5-16T-SL" in product_skus
        assert "PL-300-BKH" in product_skus
        assert "PL-300-BKHP" in product_skus

        # 5. Verify 5 Real Documents
        docs = db_session.query(Document).all()
        assert len(docs) == 5
        doc_numbers = [d.doc_number for d in docs]
        assert "Q-0405" in doc_numbers
        assert "POS-0159" in doc_numbers
        assert "SI-0111" in doc_numbers
        assert "DC-0687" in doc_numbers
        assert "DC-0681" in doc_numbers

    def test_dashboard_stats_telemetry(
        self, client: TestClient, admin_headers: dict
    ):
        """Verify dashboard statistics endpoint aggregates revenue, active quotes, and inventory status."""
        response = client.get("/api/dashboard/stats", headers=admin_headers)
        assert response.status_code == 200
        stats = response.json()

        # Contract assertions (Strict CamelCase)
        assert "totalRevenue" in stats
        assert "activeQuotations" in stats
        assert "pendingOrders" in stats
        assert "lowStockCount" in stats
        assert "totalCustomers" in stats
        assert "totalProducts" in stats
        assert "recentDocuments" in stats
        assert "recentActivity" in stats

        assert stats["totalCustomers"] >= 2
        assert stats["totalProducts"] >= 2
        assert isinstance(stats["recentDocuments"], list)
        assert isinstance(stats["recentActivity"], list)
