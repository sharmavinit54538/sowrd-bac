from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.inventory_log import InventoryLog
from app.models.product import Product


class TestDocumentWorkflowLifecycle:
    """Full 5-stage physical ERP document lifecycle from initial quotation to final packing slip."""

    def test_complete_five_stage_manufacturing_order_fulfilment(
        self,
        client: TestClient,
        admin_headers: dict,
        inventory_headers: dict,
        seller_headers: dict,
        db_session: Session,
    ):
        """
        Executes the entire end-to-end B2B ERP manufacturing order journey:
        Stage 1: SELLER drafts & sends Quotation (Q-XXXX).
        Stage 2: ADMIN approves Quotation and converts it to Proforma Invoice (POS-XXXX).
        Stage 3: INVENTORY_MANAGER verifies availability and reserves stock (STOCK_RESERVED).
        Stage 4: Payment received -> ADMIN converts to Tax Invoice (SI-XXXX) deducting stock (STOCK_OUT).
        Stage 5: INVENTORY_MANAGER generates Delivery Challan (DC-XXXX) and Packing Slip (PS-XXXX).
        """
        # Baseline resources
        cust = db_session.query(Customer).filter(Customer.state_code == "27").first()
        prod = db_session.query(Product).filter(Product.sku == "TEST-ROTOR-01").first()

        initial_total_stock = prod.total_stock  # 20
        initial_reserved_stock = prod.reserved_stock  # 0
        order_qty = 2

        # -------------------------------------------------------------
        # STAGE 1: Seller Drafts Quotation & Marks SENT
        # -------------------------------------------------------------
        quote_payload = {
            "docType": "QUOTATION",
            "customerId": str(cust.id),
            "buyerOrderRef": "ENQ-MAHA-4410",
            "items": [
                {
                    "productId": str(prod.id),
                    "itemName": prod.item_name,
                    "hsnCode": prod.hsn_code,
                    "qty": order_qty,
                    "rate": float(prod.rate),
                }
            ],
            "terms": ["100% advance against Proforma Invoice."],
            "remarks": "Standard 1-year manufacturing warranty included.",
        }

        res_q_create = client.post("/api/documents", json=quote_payload, headers=seller_headers)
        assert res_q_create.status_code == 201
        quote_data = res_q_create.json()
        quote_id = quote_data["id"]
        quote_num = quote_data["docNumber"]

        assert quote_num.startswith("Q-")
        assert quote_data["status"] == "DRAFT"
        assert float(quote_data["subTotal"]) == 100000.00
        assert float(quote_data["igstAmount"]) == 18000.00
        assert float(quote_data["grandTotal"]) == 118000.00

        # Seller transitions Quotation from DRAFT to SENT
        res_q_sent = client.patch(
            f"/api/documents/{quote_id}/status",
            json={"status": "SENT"},
            headers=seller_headers,
        )
        assert res_q_sent.status_code == 200
        assert res_q_sent.json()["status"] == "SENT"

        # -------------------------------------------------------------
        # STAGE 2: Admin Approves Quotation & Converts to Proforma Invoice
        # -------------------------------------------------------------
        # Admin approves quotation
        res_q_app = client.patch(
            f"/api/documents/{quote_id}/status",
            json={"status": "APPROVED"},
            headers=admin_headers,
        )
        assert res_q_app.status_code == 200
        assert res_q_app.json()["status"] == "APPROVED"

        # Admin converts Quotation to Proforma Invoice (POS-XXXX)
        res_pi = client.post(f"/api/documents/{quote_id}/convert-to-pi", headers=admin_headers)
        assert res_pi.status_code == 200
        pi_data = res_pi.json()
        pi_id = pi_data["id"]
        pi_num = pi_data["docNumber"]

        assert pi_num.startswith("POS-")
        assert pi_data["docType"] == "PROFORMA_INVOICE"
        assert pi_data["parentDocId"] == quote_id
        assert pi_data["parentDocNumber"] == quote_num
        assert pi_data["status"] == "APPROVED"

        # -------------------------------------------------------------
        # STAGE 3: Inventory Manager Reserves Stock for the PI
        # -------------------------------------------------------------
        res_reserve = client.post(f"/api/documents/{pi_id}/reserve-stock", headers=inventory_headers)
        assert res_reserve.status_code == 200
        pi_res_data = res_reserve.json()

        assert pi_res_data["stockReserved"] is True
        assert pi_res_data["status"] == "STOCK_RESERVED"

        # Verify DB product reservation
        db_session.refresh(prod)
        assert prod.total_stock == initial_total_stock
        assert prod.reserved_stock == initial_reserved_stock + order_qty
        assert prod.available_stock == initial_total_stock - (initial_reserved_stock + order_qty)

        # -------------------------------------------------------------
        # STAGE 4: Admin Converts to Tax Invoice (SI-XXXX) & Stock Deducts
        # -------------------------------------------------------------
        payment_note = "Received via NEFT UTR# SBIN9920261025 on 25-Oct-2026"
        res_invoice = client.post(
            f"/api/documents/{pi_id}/convert-to-tax-invoice?payment_note={payment_note}",
            headers=admin_headers,
        )
        assert res_invoice.status_code == 200
        inv_data = res_invoice.json()
        inv_id = inv_data["id"]
        inv_num = inv_data["docNumber"]

        assert inv_num.startswith("SI-")
        assert inv_data["docType"] == "TAX_INVOICE"
        assert inv_data["parentDocId"] == pi_id
        assert inv_data["stockDeducted"] is True
        assert inv_data["status"] == "FULFILLED"

        # Verify physical stock reduction in DB
        db_session.refresh(prod)
        assert prod.total_stock == initial_total_stock - order_qty
        assert prod.reserved_stock == initial_reserved_stock  # released from reservation

        # Verify STOCK_OUT inventory log
        stock_out_log = (
            db_session.query(InventoryLog)
            .filter(InventoryLog.product_id == prod.id, InventoryLog.action == "STOCK_OUT")
            .order_by(InventoryLog.created_at.desc())
            .first()
        )
        assert stock_out_log is not None
        assert stock_out_log.quantity == order_qty
        assert stock_out_log.reference_doc_number == inv_num

        # -------------------------------------------------------------
        # STAGE 5: Dispatch & Logistics (Delivery Challan & Packing Slip)
        # -------------------------------------------------------------
        # 5a. Create Delivery Challan
        challan_payload = {
            "transporterName": "Jaipur Golden Transport",
            "vehicleNo": "RJ14TG3554",
            "remarks": "Tooling dispatch via dedicated truck",
        }
        res_dc = client.post(
            f"/api/documents/{inv_id}/create-challan",
            json=challan_payload,
            headers=inventory_headers,
        )
        assert res_dc.status_code == 200
        dc_data = res_dc.json()
        assert dc_data["docType"] == "DELIVERY_CHALLAN"
        assert dc_data["docNumber"].startswith("DC-")
        assert dc_data["vehicleNo"] == "RJ14TG3554"
        assert dc_data["parentDocId"] == inv_id

        # 5b. Create Packing Slip
        slip_payload = {
            "pkgNumber": "1 Wooden Crate",
            "grossWeight": "50 Kg",
            "remarks": "Packed with VCI moisture barrier",
            "itemNetWeights": {"1": "40 Kg"},
        }
        res_ps = client.post(
            f"/api/documents/{inv_id}/create-packing-slip",
            json=slip_payload,
            headers=inventory_headers,
        )
        assert res_ps.status_code == 200
        ps_data = res_ps.json()
        assert ps_data["docType"] == "PACKING_SLIP"
        assert ps_data["grossWeight"] == "50 Kg"
        assert ps_data["parentDocId"] == inv_id

    def test_document_cancellation_unreserves_stock_cleanly(
        self, client: TestClient, admin_headers: dict, inventory_headers: dict, db_session: Session
    ):
        """
        Verify that cancelling a document with reserved stock automatically releases
        the reservation and logs an UNRESERVED action.
        """
        cust = db_session.query(Customer).first()
        prod = db_session.query(Product).first()
        initial_reserved = prod.reserved_stock

        # Create quote
        doc_payload = {
            "docType": "QUOTATION",
            "customerId": str(cust.id),
            "items": [
                {
                    "productId": str(prod.id),
                    "itemName": prod.item_name,
                    "qty": 3,
                    "rate": float(prod.rate),
                }
            ],
        }
        res = client.post("/api/documents", json=doc_payload, headers=admin_headers)
        doc_id = res.json()["id"]

        # Approve and reserve
        client.patch(f"/api/documents/{doc_id}/status", json={"status": "APPROVED"}, headers=admin_headers)
        res_reserve = client.post(f"/api/documents/{doc_id}/reserve-stock", headers=inventory_headers)
        assert res_reserve.status_code == 200

        db_session.refresh(prod)
        assert prod.reserved_stock == initial_reserved + 3

        # Cancel document
        res_cancel = client.patch(f"/api/documents/{doc_id}/status", json={"status": "CANCELLED"}, headers=admin_headers)
        assert res_cancel.status_code == 200
        assert res_cancel.json()["status"] == "CANCELLED"
        assert res_cancel.json()["stockReserved"] is False

        # Verify stock unreserved in DB
        db_session.refresh(prod)
        assert prod.reserved_stock == initial_reserved

        # Verify UNRESERVED log entry
        unres_log = (
            db_session.query(InventoryLog)
            .filter(InventoryLog.product_id == prod.id, InventoryLog.action == "UNRESERVED")
            .order_by(InventoryLog.created_at.desc())
            .first()
        )
        assert unres_log is not None
        assert unres_log.quantity == 3
