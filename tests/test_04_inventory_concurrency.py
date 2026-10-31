import concurrent.futures
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.inventory_log import InventoryLog
from app.models.product import Product


class TestInventoryConcurrencyAndAdjustments:
    """Rigorous validation of manual stock adjustments, row-level locking, and over-selling prevention."""

    def test_manual_stock_in_and_audit(
        self, client: TestClient, inventory_headers: dict, db_session: Session
    ):
        """Test STOCK_IN increases totalStock and records immutable inventory log."""
        prod = db_session.query(Product).filter(Product.sku == "TEST-ROTOR-01").first()
        initial_stock = prod.total_stock

        payload = {
            "productId": str(prod.id),
            "action": "STOCK_IN",
            "quantity": 10,
            "notes": "Goods received from heat treatment plant",
        }
        response = client.post("/api/inventory/adjust", json=payload, headers=inventory_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "STOCK_IN"
        assert data["quantity"] == 10

        # Verify database state
        db_session.refresh(prod)
        assert prod.total_stock == initial_stock + 10

        # Verify inventory log recorded
        log = (
            db_session.query(InventoryLog)
            .filter(InventoryLog.product_id == prod.id, InventoryLog.action == "STOCK_IN")
            .order_by(InventoryLog.created_at.desc())
            .first()
        )
        assert log is not None
        assert log.quantity == 10
        assert log.notes == "Goods received from heat treatment plant"

    def test_manual_stock_out_and_insufficient_stock_rejection(
        self, client: TestClient, inventory_headers: dict, db_session: Session
    ):
        """Test STOCK_OUT decrements stock and rejects deductions exceeding available stock."""
        prod = db_session.query(Product).filter(Product.sku == "TEST-BLADE-02").first()
        # Initial: total=10, reserved=0 -> available=10

        # 1. Valid deduction of 4
        payload_valid = {
            "productId": str(prod.id),
            "action": "STOCK_OUT",
            "quantity": 4,
            "notes": "Scrap or sample dispatch",
        }
        res_valid = client.post("/api/inventory/adjust", json=payload_valid, headers=inventory_headers)
        assert res_valid.status_code == 200

        db_session.refresh(prod)
        assert prod.total_stock == 6
        assert prod.available_stock == 6

        # 2. Invalid deduction of 10 (exceeds available 6)
        payload_invalid = {
            "productId": str(prod.id),
            "action": "STOCK_OUT",
            "quantity": 10,
            "notes": "Attempting over-deduction",
        }
        res_invalid = client.post("/api/inventory/adjust", json=payload_invalid, headers=inventory_headers)
        assert res_invalid.status_code == 400
        assert "Insufficient available stock" in res_invalid.json()["detail"]

    def test_inventory_adjustment_delta_and_reserved_boundary(
        self, client: TestClient, inventory_headers: dict, db_session: Session
    ):
        """Test ADJUSTMENT action updates stock while strictly protecting reserved stock."""
        prod = db_session.query(Product).filter(Product.sku == "TEST-ROTOR-01").first()
        prod.total_stock = 10
        prod.reserved_stock = 4  # 4 reserved units
        db_session.commit()

        # Deduction of 7 would make totalStock = 3 < reservedStock (4) -> Must reject!
        payload_violating = {
            "productId": str(prod.id),
            "action": "ADJUSTMENT",
            "quantity": -7,
            "notes": "Cycle count reduction",
        }
        res_fail = client.post("/api/inventory/adjust", json=payload_violating, headers=inventory_headers)
        assert res_fail.status_code == 400
        assert "fall below reserved stock" in res_fail.json()["detail"]

        # Valid adjustment of +5
        payload_valid = {
            "productId": str(prod.id),
            "action": "ADJUSTMENT",
            "quantity": 5,
            "notes": "Found physical items in warehouse bay C",
        }
        res_ok = client.post("/api/inventory/adjust", json=payload_valid, headers=inventory_headers)
        assert res_ok.status_code == 200
        db_session.refresh(prod)
        assert prod.total_stock == 15

    def test_concurrent_stock_reservations_prevent_overselling(
        self, client: TestClient, admin_headers: dict, inventory_headers: dict, db_session: Session
    ):
        """
        Concurrency Race Condition & Row-Level Locking Test:
        - Product has exactly 5 units available (total=5, reserved=0).
        - 10 distinct approved documents are created, each demanding 1 unit.
        - 10 threads concurrently fire POST /api/documents/{id}/reserve-stock.
        - Exactly 5 must succeed (HTTP 200).
        - Exactly 5 must fail (HTTP 400 - Insufficient stock).
        - Final DB state: total=5, reserved=5, available=0. Zero over-selling!
        """
        cust = db_session.query(Customer).first()

        # Create limited stock product
        limited_prod = Product(
            sku="CONCURRENCY-ROTOR-05",
            item_name="Limited Supply Rotor",
            hsn_code="84779000",
            unit="Nos",
            rate=Decimal("10000.00"),
            total_stock=5,
            reserved_stock=0,
            min_stock_level=1,
        )
        db_session.add(limited_prod)
        db_session.commit()
        db_session.refresh(limited_prod)

        # Pre-create 10 APPROVED documents targeting this product
        doc_ids = []
        for i in range(10):
            payload = {
                "docType": "QUOTATION",
                "customerId": str(cust.id),
                "items": [
                    {
                        "productId": str(limited_prod.id),
                        "itemName": limited_prod.item_name,
                        "qty": 1,
                        "rate": float(limited_prod.rate),
                    }
                ],
            }
            res = client.post("/api/documents", json=payload, headers=admin_headers)
            assert res.status_code == 201
            doc_id = res.json()["id"]

            # Transition to APPROVED
            res_approve = client.patch(
                f"/api/documents/{doc_id}/status",
                json={"status": "APPROVED"},
                headers=admin_headers,
            )
            assert res_approve.status_code == 200
            doc_ids.append(doc_id)

        # Launch 10 parallel threads to reserve stock
        def do_reserve(target_doc_id: str):
            # Each thread makes an independent HTTP request with inventory credentials
            return client.post(
                f"/api/documents/{target_doc_id}/reserve-stock",
                headers=inventory_headers,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(do_reserve, d_id) for d_id in doc_ids]
            responses = [f.result() for f in futures]

        status_codes = [r.status_code for r in responses]
        success_count = status_codes.count(200)
        failure_count = status_codes.count(400)

        assert success_count == 5, f"Expected 5 successful reservations, got {success_count}. Statuses: {status_codes}"
        assert failure_count == 5, f"Expected 5 rejected reservations, got {failure_count}. Statuses: {status_codes}"

        # Assert final database product state
        db_session.refresh(limited_prod)
        assert limited_prod.total_stock == 5
        assert limited_prod.reserved_stock == 5
        assert limited_prod.available_stock == 0

    def test_inventory_summary_and_logs_endpoints(
        self, client: TestClient, inventory_headers: dict
    ):
        """Verify inventory summary metrics and log retrieval endpoints."""
        # Summary
        res_sum = client.get("/api/inventory/summary", headers=inventory_headers)
        assert res_sum.status_code == 200
        summary = res_sum.json()
        assert "totalSkus" in summary
        assert "totalStockCount" in summary
        assert "totalReservedCount" in summary
        assert "lowStockCount" in summary
        assert summary["totalSkus"] >= 2

        # Logs
        res_logs = client.get("/api/inventory/logs", headers=inventory_headers)
        assert res_logs.status_code == 200
        assert isinstance(res_logs.json(), list)
