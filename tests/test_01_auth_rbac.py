import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.product import Product


class TestAuthAndRBACMatrix:
    """Rigorous authentication and role-based access control validation suite."""

    def test_login_success_admin_json(self, client: TestClient):
        """Verify successful JSON authentication for ADMIN returning camelCase JWT contract."""
        payload = {"email": "admin@swordinn.biz", "password": "password123"}
        response = client.post("/api/auth/login", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "accessToken" in data
        assert data["tokenType"] == "bearer"
        assert data["user"]["email"] == "admin@swordinn.biz"
        assert data["user"]["role"] == "ADMIN"
        assert "id" in data["user"]

    def test_login_success_inventory_manager(self, client: TestClient):
        """Verify successful login for INVENTORY_MANAGER."""
        payload = {"email": "inventory@swordinn.biz", "password": "password123"}
        response = client.post("/api/auth/login", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["role"] == "INVENTORY_MANAGER"

    def test_login_success_seller(self, client: TestClient):
        """Verify successful login for SELLER."""
        payload = {"email": "sales@swordinn.biz", "password": "password123"}
        response = client.post("/api/auth/login", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["role"] == "SELLER"

    def test_login_success_form_data(self, client: TestClient):
        """Verify Swagger UI OAuth2 form-data authentication flow."""
        form_data = {"username": "admin@swordinn.biz", "password": "password123"}
        response = client.post("/api/auth/login", data=form_data)
        assert response.status_code == 200
        assert "accessToken" in response.json()

    def test_login_invalid_password(self, client: TestClient):
        """Verify rejected login on incorrect password."""
        payload = {"email": "admin@swordinn.biz", "password": "wrong_password_999"}
        response = client.post("/api/auth/login", json=payload)
        assert response.status_code == 401
        assert "detail" in response.json()

    def test_login_non_existent_user(self, client: TestClient):
        """Verify rejected login on unknown user email."""
        payload = {"email": "ghost@swordinn.biz", "password": "password123"}
        response = client.post("/api/auth/login", json=payload)
        assert response.status_code == 401

    def test_login_empty_payload(self, client: TestClient):
        """Verify 400 Bad Request on empty or missing login credentials."""
        response = client.post("/api/auth/login", json={})
        assert response.status_code == 400

    def test_get_current_user_profile(
        self,
        client: TestClient,
        admin_headers: dict,
        inventory_headers: dict,
        seller_headers: dict,
        unauthorized_headers: dict,
    ):
        """Verify /api/auth/me returns proper user identities and rejects unauthorized tokens."""
        # 1. Admin
        res_admin = client.get("/api/auth/me", headers=admin_headers)
        assert res_admin.status_code == 200
        assert res_admin.json()["role"] == "ADMIN"

        # 2. Inventory Manager
        res_inv = client.get("/api/auth/me", headers=inventory_headers)
        assert res_inv.status_code == 200
        assert res_inv.json()["role"] == "INVENTORY_MANAGER"

        # 3. Seller
        res_seller = client.get("/api/auth/me", headers=seller_headers)
        assert res_seller.status_code == 200
        assert res_seller.json()["role"] == "SELLER"

        # 4. Bad Token
        res_bad = client.get("/api/auth/me", headers=unauthorized_headers)
        assert res_bad.status_code == 401

        # 5. Missing Token
        res_missing = client.get("/api/auth/me")
        assert res_missing.status_code == 401

    def test_rbac_product_creation(
        self,
        client: TestClient,
        admin_headers: dict,
        inventory_headers: dict,
        seller_headers: dict,
    ):
        """
        Verify Product Creation RBAC:
        - Admin -> 201 Created
        - Seller -> 403 Forbidden
        - Inventory Manager -> 403 Forbidden
        """
        product_payload = {
            "sku": "RBAC-PROD-01",
            "itemName": "RBAC Test Rotor",
            "category": "Rotors",
            "hsnCode": "84779000",
            "unit": "Nos",
            "rate": 75000.00,
            "totalStock": 15,
            "reservedStock": 0,
            "minStockLevel": 3,
        }

        # Seller cannot create products
        res_seller = client.post("/api/products", json=product_payload, headers=seller_headers)
        assert res_seller.status_code == 403

        # Inventory manager cannot create products
        res_inv = client.post("/api/products", json=product_payload, headers=inventory_headers)
        assert res_inv.status_code == 403

        # Admin creates product successfully
        res_admin = client.post("/api/products", json=product_payload, headers=admin_headers)
        assert res_admin.status_code == 201
        assert res_admin.json()["sku"] == "RBAC-PROD-01"

    def test_rbac_customer_creation(
        self,
        client: TestClient,
        admin_headers: dict,
        inventory_headers: dict,
        seller_headers: dict,
    ):
        """
        Verify Customer Creation RBAC:
        - Admin -> 201 Created
        - Seller -> 403 Forbidden
        - Inventory Manager -> 403 Forbidden
        """
        cust_payload = {
            "companyName": "RBAC Polymers Ltd",
            "billingAddress": "Sector 4, Gurgaon, Haryana",
            "shippingAddress": "Sector 4, Gurgaon, Haryana",
            "stateName": "Haryana",
            "stateCode": "06",
            "gstin": "06AAACR1234A1Z1",
            "contactPerson": "Mr. Anil",
            "phone": "+91 98111 22222",
            "email": "procurement@rbacpolymers.com",
        }

        # Seller forbidden
        assert client.post("/api/customers", json=cust_payload, headers=seller_headers).status_code == 403
        # Inventory Manager forbidden
        assert client.post("/api/customers", json=cust_payload, headers=inventory_headers).status_code == 403
        # Admin allowed
        res_admin = client.post("/api/customers", json=cust_payload, headers=admin_headers)
        assert res_admin.status_code == 201
        assert res_admin.json()["companyName"] == "RBAC Polymers Ltd"

    def test_rbac_inventory_adjustments(
        self,
        client: TestClient,
        admin_headers: dict,
        inventory_headers: dict,
        seller_headers: dict,
        db_session: Session,
    ):
        """
        Verify Inventory Adjustment RBAC:
        - Inventory Manager -> 200 OK
        - Admin -> 200 OK
        - Seller -> 403 Forbidden
        """
        prod = db_session.query(Product).first()
        payload = {
            "productId": str(prod.id),
            "action": "STOCK_IN",
            "quantity": 5,
            "notes": "Testing RBAC stock in",
        }

        # Seller forbidden
        res_seller = client.post("/api/inventory/adjust", json=payload, headers=seller_headers)
        assert res_seller.status_code == 403

        # Inventory Manager authorized
        res_inv = client.post("/api/inventory/adjust", json=payload, headers=inventory_headers)
        assert res_inv.status_code == 200

        # Admin authorized
        res_admin = client.post("/api/inventory/adjust", json=payload, headers=admin_headers)
        assert res_admin.status_code == 200

    def test_rbac_document_creation_rules(
        self,
        client: TestClient,
        admin_headers: dict,
        inventory_headers: dict,
        seller_headers: dict,
        db_session: Session,
    ):
        """
        Verify Document Creation RBAC constraints:
        - Seller can ONLY create QUOTATION.
        - Seller cannot create TAX_INVOICE or DELIVERY_CHALLAN directly.
        - Inventory Manager cannot create general documents directly.
        - Admin can create any document type.
        """
        cust = db_session.query(Customer).first()
        prod = db_session.query(Product).first()

        quote_payload = {
            "docType": "QUOTATION",
            "customerId": str(cust.id),
            "items": [
                {
                    "productId": str(prod.id),
                    "itemName": prod.item_name,
                    "hsnCode": prod.hsn_code,
                    "qty": 1,
                    "rate": float(prod.rate),
                }
            ],
        }

        # 1. Seller creates QUOTATION -> 201 Created
        res_seller_quote = client.post("/api/documents", json=quote_payload, headers=seller_headers)
        assert res_seller_quote.status_code == 201
        assert res_seller_quote.json()["docType"] == "QUOTATION"

        # 2. Seller attempts TAX_INVOICE -> 403 Forbidden
        tax_payload = dict(quote_payload)
        tax_payload["docType"] = "TAX_INVOICE"
        res_seller_tax = client.post("/api/documents", json=tax_payload, headers=seller_headers)
        assert res_seller_tax.status_code == 403

        # 3. Inventory Manager attempts direct document creation -> 403 Forbidden
        res_inv_quote = client.post("/api/documents", json=quote_payload, headers=inventory_headers)
        assert res_inv_quote.status_code == 403

        # 4. Admin creates direct TAX_INVOICE -> 201 Created
        res_admin_tax = client.post("/api/documents", json=tax_payload, headers=admin_headers)
        assert res_admin_tax.status_code == 201
        assert res_admin_tax.json()["docType"] == "TAX_INVOICE"
