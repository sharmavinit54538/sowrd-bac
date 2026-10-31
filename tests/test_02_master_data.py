import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.product import Product


class TestMasterDataIntegrity:
    """Master Products, Industrial Customers, and Company Profile CRUD and data integrity suite."""

    # -------------------------------------------------------------
    # Products Suite
    # -------------------------------------------------------------
    def test_product_create_and_computed_available_stock(
        self, client: TestClient, admin_headers: dict
    ):
        """Create a master product and verify dynamic availableStock = totalStock - reservedStock."""
        payload = {
            "sku": "PUSG-300-40T-ROT",
            "itemName": "PUSG-300 Heavy Duty Rotor",
            "technicalSpecs": "40-Teeth carbide-tipped rotor for rigid compounding",
            "category": "Pelletizer Rotors",
            "hsnCode": "84779000",
            "unit": "Nos",
            "rate": 310000.00,
            "totalStock": 10,
            "reservedStock": 0,
            "minStockLevel": 2,
        }

        response = client.post("/api/products", json=payload, headers=admin_headers)
        assert response.status_code == 201
        data = response.json()

        # Contract assertions (Strict CamelCase)
        assert data["sku"] == "PUSG-300-40T-ROT"
        assert data["itemName"] == "PUSG-300 Heavy Duty Rotor"
        assert data["totalStock"] == 10
        assert data["reservedStock"] == 0
        assert data["availableStock"] == 10
        assert "id" in data
        assert "createdAt" in data

    def test_product_duplicate_sku_rejection(
        self, client: TestClient, admin_headers: dict
    ):
        """Verify rejected creation when SKU is duplicated."""
        payload = {
            "sku": "TEST-ROTOR-01",  # Existing SKU from baseline seed
            "itemName": "Duplicate SKU Rotor",
            "rate": 60000.00,
            "totalStock": 5,
        }
        response = client.post("/api/products", json=payload, headers=admin_headers)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_product_update_and_stock_recalculation(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Update product total stock and verify available stock updates reactively."""
        prod = db_session.query(Product).filter(Product.sku == "TEST-ROTOR-01").first()

        update_payload = {
            "rate": 55000.00,
            "totalStock": 25,
            "reservedStock": 5,
        }
        response = client.put(f"/api/products/{prod.id}", json=update_payload, headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert float(data["rate"]) == 55000.00
        assert data["totalStock"] == 25
        assert data["reservedStock"] == 5
        assert data["availableStock"] == 20  # 25 - 5 = 20

    def test_product_low_stock_alert_endpoint(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Verify /api/products/low-stock filters only items with availableStock <= minStockLevel."""
        # Baseline: TEST-BLADE-02 has total 10, min 2 -> available 10 (not low)
        # Update TEST-BLADE-02 to total 2, reserved 1 -> available 1 <= min 2 (low stock!)
        prod = db_session.query(Product).filter(Product.sku == "TEST-BLADE-02").first()
        prod.total_stock = 2
        prod.reserved_stock = 1
        db_session.commit()

        response = client.get("/api/products/low-stock", headers=admin_headers)
        assert response.status_code == 200
        low_items = response.json()
        skus = [p["sku"] for p in low_items]
        assert "TEST-BLADE-02" in skus
        assert "TEST-ROTOR-01" not in skus

    def test_product_delete(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Delete a product and assert 204 No Content followed by 404 on retrieval."""
        prod = db_session.query(Product).filter(Product.sku == "TEST-BLADE-02").first()
        prod_id = str(prod.id)

        res_del = client.delete(f"/api/products/{prod_id}", headers=admin_headers)
        assert res_del.status_code == 204

        res_get = client.get(f"/api/products/{prod_id}", headers=admin_headers)
        assert res_get.status_code == 404

    # -------------------------------------------------------------
    # Customers Suite
    # -------------------------------------------------------------
    def test_customer_create_and_camel_case_contract(
        self, client: TestClient, admin_headers: dict
    ):
        """Create an industrial customer and verify proper 2-digit stateCode and camelCase fields."""
        payload = {
            "companyName": "Kabra Extrusiontechnik Ltd",
            "billingAddress": "Kabra Industrial Park, Daman",
            "shippingAddress": "Kabra Industrial Park, Daman",
            "stateName": "Daman & Diu",
            "stateCode": "25",
            "gstin": "25AABCK1234D1Z8",
            "contactPerson": "Mr. Rajesh Mehta",
            "phone": "+91 98250 11223",
            "email": "purchases@kabra.net",
        }

        response = client.post("/api/customers", json=payload, headers=admin_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["companyName"] == "Kabra Extrusiontechnik Ltd"
        assert data["stateCode"] == "25"
        assert data["gstin"] == "25AABCK1234D1Z8"
        assert "id" in data
        assert "createdAt" in data

    def test_customer_search_and_filtering(
        self, client: TestClient, admin_headers: dict
    ):
        """Verify customer listing search by name and stateCode filter."""
        # 1. Search by name query
        res_search = client.get("/api/customers?search=Rajasthan", headers=admin_headers)
        assert res_search.status_code == 200
        results = res_search.json()
        assert len(results) >= 1
        assert "Rajasthan" in results[0]["companyName"]

        # 2. Filter by state_code
        res_state = client.get("/api/customers?state_code=27", headers=admin_headers)
        assert res_state.status_code == 200
        for cust in res_state.json():
            assert cust["stateCode"] == "27"

    def test_customer_update_and_delete(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Update customer phone/contact and subsequently delete the customer."""
        cust = db_session.query(Customer).filter(Customer.company_name == "Maharashtra Polymer Ltd").first()
        cust_id = str(cust.id)

        update_payload = {
            "contactPerson": "Vikram Shinde",
            "phone": "+91 98205 99999",
        }
        res_upd = client.put(f"/api/customers/{cust_id}", json=update_payload, headers=admin_headers)
        assert res_upd.status_code == 200
        assert res_upd.json()["contactPerson"] == "Vikram Shinde"

        res_del = client.delete(f"/api/customers/{cust_id}", headers=admin_headers)
        assert res_del.status_code == 204

        res_get = client.get(f"/api/customers/{cust_id}", headers=admin_headers)
        assert res_get.status_code == 404

    # -------------------------------------------------------------
    # Company Profile Suite
    # -------------------------------------------------------------
    def test_company_profile_read_and_admin_update(
        self, client: TestClient, admin_headers: dict, seller_headers: dict
    ):
        """Verify reading company profile and enforcing Admin-only update permissions."""
        # 1. Read company profile (accessible to all roles)
        res_get = client.get("/api/company", headers=seller_headers)
        assert res_get.status_code == 200
        data = res_get.json()
        assert data["name"] == "SWORD INNOVATIONS"
        assert data["stateCode"] == "08"
        assert data["city"] == "Jaipur"

        # 2. Seller attempt update -> 403 Forbidden
        update_payload = {"tagline": "World Leaders in Precision Tooling"}
        res_seller_upd = client.put("/api/company", json=update_payload, headers=seller_headers)
        assert res_seller_upd.status_code == 403

        # 3. Admin update -> 200 OK
        res_admin_upd = client.put("/api/company", json=update_payload, headers=admin_headers)
        assert res_admin_upd.status_code == 200
        assert res_admin_upd.json()["tagline"] == "World Leaders in Precision Tooling"
