from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.product import Product
from app.services.gst_service import compute_document_financials, determine_gst_rates
from app.services.number_to_words import amount_to_indian_words


class TestGSTEngineAndCalculations:
    """Rigorous validation of Indian GST calculations, rounding rules, and Amount to Words engine."""

    def test_intra_state_gst_tax_breakdown(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """
        Intra-State Transaction:
        Company (08 - Rajasthan) selling to Customer (08 - Rajasthan)
        Line item: Qty 2 @ 50,000 = Taxable 100,000
        Expected:
        - CGST: 9.0% -> 9,000.00
        - SGST: 9.0% -> 9,000.00
        - IGST: 0.0% -> 0.00
        - Grand Total: 118,000.00
        - Words: INR One Lac Eighteen Thousand Only.
        """
        cust_intra = db_session.query(Customer).filter(Customer.state_code == "08").first()
        prod = db_session.query(Product).filter(Product.sku == "TEST-ROTOR-01").first()

        doc_payload = {
            "docType": "QUOTATION",
            "customerId": str(cust_intra.id),
            "items": [
                {
                    "productId": str(prod.id),
                    "itemName": prod.item_name,
                    "hsnCode": prod.hsn_code,
                    "qty": 2,
                    "rate": 50000.00,
                }
            ],
        }

        response = client.post("/api/documents", json=doc_payload, headers=admin_headers)
        assert response.status_code == 201
        data = response.json()

        assert float(data["subTotal"]) == 100000.00
        assert float(data["cgstRate"]) == 9.0
        assert float(data["cgstAmount"]) == 9000.00
        assert float(data["sgstRate"]) == 9.0
        assert float(data["sgstAmount"]) == 9000.00
        assert float(data["igstRate"]) == 0.0
        assert float(data["igstAmount"]) == 0.00
        assert float(data["roundingOff"]) == 0.00
        assert float(data["grandTotal"]) == 118000.00
        assert "INR One Lac Eighteen Thousand Only." in data["amountInWords"]

    def test_inter_state_gst_tax_breakdown(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """
        Inter-State Transaction:
        Company (08 - Rajasthan) selling to Customer (27 - Maharashtra)
        Line item: Qty 1 @ 100,000 = Taxable 100,000
        Expected:
        - CGST: 0.0% -> 0.00
        - SGST: 0.0% -> 0.00
        - IGST: 18.0% -> 18,000.00
        - Grand Total: 118,000.00
        - Words: INR One Lac Eighteen Thousand Only.
        """
        cust_inter = db_session.query(Customer).filter(Customer.state_code == "27").first()
        prod = db_session.query(Product).filter(Product.sku == "TEST-BLADE-02").first()

        doc_payload = {
            "docType": "QUOTATION",
            "customerId": str(cust_inter.id),
            "items": [
                {
                    "productId": str(prod.id),
                    "itemName": prod.item_name,
                    "hsnCode": prod.hsn_code,
                    "qty": 1,
                    "rate": 100000.00,
                }
            ],
        }

        response = client.post("/api/documents", json=doc_payload, headers=admin_headers)
        assert response.status_code == 201
        data = response.json()

        assert float(data["subTotal"]) == 100000.00
        assert float(data["cgstRate"]) == 0.0
        assert float(data["cgstAmount"]) == 0.00
        assert float(data["sgstRate"]) == 0.0
        assert float(data["sgstAmount"]) == 0.00
        assert float(data["igstRate"]) == 18.0
        assert float(data["igstAmount"]) == 18000.00
        assert float(data["roundingOff"]) == 0.00
        assert float(data["grandTotal"]) == 118000.00
        assert "INR One Lac Eighteen Thousand Only." in data["amountInWords"]

    def test_gst_rounding_off_precision(self):
        """Verify fractional paise line items round to nearest whole rupee and track roundingOff."""
        # 3 items @ 33.33 = 99.99
        # IGST 18% = 17.9982 -> rounded to 18.00
        # Total exact = 117.99
        # Rounded grand total = 118.00 -> roundingOff = +0.01
        items = [{"item_name": "Precision Shim", "qty": 3, "rate": Decimal("33.33")}]
        result = compute_document_financials(items, customer_state_code="27", company_state_code="08")

        assert result["sub_total"] == Decimal("99.99")
        assert result["igst_amount"] == Decimal("18.00")
        assert result["grand_total"] == Decimal("118.00")
        assert result["rounding_off"] == Decimal("0.01")
        assert "INR One Hundred Eighteen Only." in result["amount_in_words"]

    def test_number_to_indian_words_unit_cases(self):
        """Comprehensive verification of the Indian English currency words converter."""
        test_matrix = [
            (182900, "INR One Lac Eighty-Two Thousand Nine Hundred Only."),
            (290500, "INR Two Lac Ninety Thousand Five Hundred Only."),
            (51500.50, "INR Fifty-One Thousand Five Hundred and Fifty Paise Only."),
            (10000000, "INR One Crore Only."),
            (12500000, "INR One Crore Twenty-Five Lac Only."),
            (1005, "INR One Thousand Five Only."),
            (100, "INR One Hundred Only."),
            (50, "INR Fifty Only."),
            (0, "INR Zero Only."),
        ]

        for amount, expected_phrase in test_matrix:
            generated = amount_to_indian_words(amount)
            assert generated == expected_phrase, f"Failed for {amount}: got '{generated}', expected '{expected_phrase}'"
