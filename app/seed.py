from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.company import CompanyProfile
from app.models.customer import Customer
from app.models.document import Document, DocumentItem
from app.models.inventory_log import InventoryLog
from app.models.product import Product
from app.models.user import User
from app.services.gst_service import compute_document_financials


def seed_db(db: Session) -> None:
    """
    Automatic seeding function hooked into FastAPI lifespan.
    Seeds company profile, 3 RBAC users, 5 industrial customers,
    6 master products, and 5 authentic manufacturing ERP documents.
    """
    admin_user = db.query(User).filter(User.email == "admin@swordinn.biz").first()
    if admin_user is not None:
        # Self-heal: ensure password hashes are correct
        dirty = False
        if not verify_password("password123", admin_user.password_hash):
            admin_user.password_hash = get_password_hash("password123")
            dirty = True
        
        inv_user = db.query(User).filter(User.email == "inventory@swordinn.biz").first()
        if inv_user and not verify_password("password123", inv_user.password_hash):
            inv_user.password_hash = get_password_hash("password123")
            dirty = True

        sales_user = db.query(User).filter(User.email == "sales@swordinn.biz").first()
        if sales_user and not verify_password("password123", sales_user.password_hash):
            sales_user.password_hash = get_password_hash("password123")
            dirty = True

        if dirty:
            db.commit()
            print("--- [SEED] Self-healed existing user password hashes to bcrypt ---")
        return

    print("--- [SEED] Seeding Sword Innovations ERP Initial Records ---")

    # 1. Company Profile
    company = db.query(CompanyProfile).filter(CompanyProfile.id == 1).first()
    if not company:
        company = CompanyProfile(
            id=1,
            name="SWORD INNOVATIONS",
            tagline="Excellence in Pelletizer Rotors, Bed Knives & Precision Tooling",
            address="Plot No. G-12, RIICO Industrial Area, Mansarovar",
            city="Jaipur",
            state_name="Rajasthan",
            state_code="08",
            gstin="08AGIPN6872D1Z4",
            pan="AGIPN6872D",
            iec="AGIPN6872D",
            phones=["+91 98290 12345", "+91 141 2789012"],
            email="sales@swordinn.biz",
            founder="Er. Rajesh Sharma",
            founder_mobile="+91 98290 12345",
            jurisdiction="Jaipur",
        )
        db.add(company)
        db.flush()

    # 2. Users (Password: password123)
    pwd_hash = get_password_hash("password123")

    admin_user = User(
        name="Rajesh Sharma (Admin)",
        email="admin@swordinn.biz",
        password_hash=pwd_hash,
        role="ADMIN",
        phone="+91 98290 11111",
        is_active=True,
    )
    inv_user = User(
        name="Mahesh Verma (Inventory Manager)",
        email="inventory@swordinn.biz",
        password_hash=pwd_hash,
        role="INVENTORY_MANAGER",
        phone="+91 98290 22222",
        is_active=True,
    )
    seller_user = User(
        name="Amit Singhal (Sales Executive)",
        email="sales@swordinn.biz",
        password_hash=pwd_hash,
        role="SELLER",
        phone="+91 98290 33333",
        is_active=True,
    )
    db.add_all([admin_user, inv_user, seller_user])
    db.flush()

    # 3. 5 Industrial Customers
    cust_uflex = Customer(
        company_name="Uflex Ltd.",
        billing_address="Plot No. 12-15, Belur Industrial Area, Dharwad, Karnataka 580011",
        shipping_address="Plot No. 12-15, Belur Industrial Area, Dharwad, Karnataka 580011",
        state_name="Karnataka",
        state_code="29",
        gstin="29AAACF0109J2ZV",
        contact_person="Mr. R. K. Verma (DGM Purchase)",
        phone="+91 98801 12233",
        email="purchases.dharwad@uflexltd.com",
    )
    cust_domo = Customer(
        company_name="Domo Engineering Plastics India Pvt. Ltd.",
        billing_address="Plot No. C-10, TTC Industrial Area, MIDC Pawane, Navi Mumbai, Maharashtra 400705",
        shipping_address="Plot No. C-10, TTC Industrial Area, MIDC Pawane, Navi Mumbai, Maharashtra 400705",
        state_name="Maharashtra",
        state_code="27",
        gstin="27AAFCD7590Q1ZS",
        contact_person="Mr. Amit Patwardhan (Plant Head)",
        phone="+91 98205 56677",
        email="procurement@domo.com",
    )
    cust_dainichi = Customer(
        company_name="Dainichi Color India Private Limited",
        billing_address="Plot No. SP-2, RIICO Industrial Area, Phase-I, Neemrana, Alwar, Rajasthan 301705",
        shipping_address="Plot No. SP-2, RIICO Industrial Area, Phase-I, Neemrana, Alwar, Rajasthan 301705",
        state_name="Rajasthan",
        state_code="08",
        gstin="08AACCD9433H1ZK",
        contact_person="Mr. H. Takahashi / Mr. Sharma",
        phone="+91 99102 23344",
        email="plant.neemrana@dainichicolor.in",
    )
    cust_om = Customer(
        company_name="Om Surgical Industries",
        billing_address="Plot No. 45, Sector 3, HSIIDC Industrial Estate, Rohtak, Haryana 124001",
        shipping_address="Plot No. 45, Sector 3, HSIIDC Industrial Estate, Rohtak, Haryana 124001",
        state_name="Haryana",
        state_code="06",
        gstin="06AAAFO8819R1ZK",
        contact_person="Dr. Sandeep Hooda",
        phone="+91 98123 34455",
        email="contact@omsurgical.com",
    )
    cust_truewow = Customer(
        company_name="Truewow Hygiene Products Pvt. Ltd.",
        billing_address="Industrial Area Site-1, P.O. Dahi Chowki, Unnao, Uttar Pradesh 209801",
        shipping_address="Industrial Area Site-1, P.O. Dahi Chowki, Unnao, Uttar Pradesh 209801",
        state_name="Uttar Pradesh",
        state_code="09",
        gstin="09AAJCT9415G1ZZ",
        contact_person="Mr. Gaurav Shukla",
        phone="+91 97931 12233",
        email="operations@truewowhygiene.com",
    )
    db.add_all([cust_uflex, cust_domo, cust_dainichi, cust_om, cust_truewow])
    db.flush()

    # 4. 6 Master Products
    p1 = Product(
        sku="PUSG-200-30T-SL-WB",
        item_name="PUSG-200-30T-SL Rotor (With Bearing and Housing)",
        technical_specs="30-Teeth Stellite-tipped pelletizer rotor with high-precision SKF bearings and heavy-duty housing assembly",
        category="Pelletizer Rotors",
        hsn_code="84779000",
        unit="Nos",
        rate=Decimal("290500.00"),
        total_stock=10,
        reserved_stock=0,
        min_stock_level=2,
    )
    p2 = Product(
        sku="PUSG-200-30T-SL-NB",
        item_name="PUSG-200-30T-SL Rotor (Without Bearing)",
        technical_specs="30-Teeth Stellite-tipped pelletizer rotor naked core for direct shaft mounting",
        category="Pelletizer Rotors",
        hsn_code="84779000",
        unit="Nos",
        rate=Decimal("260500.00"),
        total_stock=8,
        reserved_stock=0,
        min_stock_level=2,
    )
    p3 = Product(
        sku="PUSG-200-4E-CE",
        item_name="PUSG-200-4E-CE Bed Knife (Ceramic)",
        technical_specs="4-Edge solid ceramic tipped stationary bed knife for extreme abrasive resistance",
        category="Bed Knives",
        hsn_code="84779000",
        unit="Nos",
        rate=Decimal("40500.00"),
        total_stock=25,
        reserved_stock=0,
        min_stock_level=5,
    )
    p4 = Product(
        sku="DSK-5-16T-SL",
        item_name="DSK-5-16T-SL Rotor (Stellite)",
        technical_specs="16-Teeth precision dynamically balanced Stellite rotor for DSK-5 pelletizer",
        category="Pelletizer Rotors",
        hsn_code="84779000",
        unit="Nos",
        rate=Decimal("155000.00"),
        total_stock=12,
        reserved_stock=0,
        min_stock_level=3,
    )
    p5 = Product(
        sku="PL-300-BKH",
        item_name="PL-300 Bed Knife Holder",
        technical_specs="Forged alloy steel precision-machined bed knife holder body for PL-300 series",
        category="Tooling & Accessories",
        hsn_code="84779000",
        unit="Nos",
        rate=Decimal("42500.00"),
        total_stock=15,
        reserved_stock=0,
        min_stock_level=4,
    )
    p6 = Product(
        sku="PL-300-BKHP",
        item_name="PL-300 Bed Knife Holder Plate",
        technical_specs="Hardened and ground clamping plate for PL-300 bed knife assembly",
        category="Tooling & Accessories",
        hsn_code="84779000",
        unit="Nos",
        rate=Decimal("51500.00"),
        total_stock=14,
        reserved_stock=0,
        min_stock_level=4,
    )
    db.add_all([p1, p2, p3, p4, p5, p6])
    db.flush()

    # 5. 5 Real Documents

    # Doc 1: Quotation Q-0405 for Uflex Ltd.
    q1_items = [
        {
            "sr": 1,
            "product_id": p1.id,
            "item_name": p1.item_name,
            "technical_specs": p1.technical_specs,
            "hsn_code": p1.hsn_code,
            "qty": 1,
            "unit": p1.unit,
            "rate": p1.rate,
        }
    ]
    fin_q1 = compute_document_financials(q1_items, cust_uflex.state_code, company.state_code)
    q1 = Document(
        doc_type="QUOTATION",
        doc_number="Q-0405",
        doc_date=date(2026, 10, 15),
        status="SENT",
        customer_id=cust_uflex.id,
        buyer_order_ref="ENQ-UF-7782",
        buyer_order_date=date(2026, 10, 12),
        mode_of_dispatch="Road Transport",
        place_of_supply=cust_uflex.state_name,
        sub_total=fin_q1["sub_total"],
        cgst_rate=fin_q1["cgst_rate"],
        cgst_amount=fin_q1["cgst_amount"],
        sgst_rate=fin_q1["sgst_rate"],
        sgst_amount=fin_q1["sgst_amount"],
        igst_rate=fin_q1["igst_rate"],
        igst_amount=fin_q1["igst_amount"],
        rounding_off=fin_q1["rounding_off"],
        grand_total=fin_q1["grand_total"],
        amount_in_words=fin_q1["amount_in_words"],
        terms=[
            "100% advance along with confirmed Purchase Order.",
            "Delivery: 3-4 weeks from advance receipt.",
            "GST: 18% IGST extra as applicable.",
            "Warranty: 12 months against any manufacturing defects.",
        ],
        remarks="Special discounted rate offered for annual bulk replacement.",
        created_by=seller_user.name,
        created_by_role=seller_user.role,
        stock_reserved=False,
        stock_deducted=False,
    )
    db.add(q1)
    db.flush()
    db.add(
        DocumentItem(
            document_id=q1.id,
            sr=1,
            product_id=p1.id,
            item_name=p1.item_name,
            technical_specs=p1.technical_specs,
            hsn_code=p1.hsn_code,
            qty=1,
            unit=p1.unit,
            rate=p1.rate,
            taxable_value=fin_q1["items"][0]["taxable_value"],
        )
    )

    # Doc 2: Proforma Invoice POS-0159 for Domo Engineering
    pi2_items = [
        {
            "sr": 1,
            "product_id": p3.id,
            "item_name": p3.item_name,
            "technical_specs": p3.technical_specs,
            "hsn_code": p3.hsn_code,
            "qty": 2,
            "unit": p3.unit,
            "rate": p3.rate,
        }
    ]
    fin_pi2 = compute_document_financials(pi2_items, cust_domo.state_code, company.state_code)
    pi2 = Document(
        doc_type="PROFORMA_INVOICE",
        doc_number="POS-0159",
        doc_date=date(2026, 10, 20),
        status="APPROVED",
        customer_id=cust_domo.id,
        buyer_order_ref="PO/DOMO/2026/091",
        buyer_order_date=date(2026, 10, 18),
        mode_of_dispatch="By SafeXpress Courier",
        place_of_supply=cust_domo.state_name,
        sub_total=fin_pi2["sub_total"],
        cgst_rate=fin_pi2["cgst_rate"],
        cgst_amount=fin_pi2["cgst_amount"],
        sgst_rate=fin_pi2["sgst_rate"],
        sgst_amount=fin_pi2["sgst_amount"],
        igst_rate=fin_pi2["igst_rate"],
        igst_amount=fin_pi2["igst_amount"],
        rounding_off=fin_pi2["rounding_off"],
        grand_total=fin_pi2["grand_total"],
        amount_in_words=fin_pi2["amount_in_words"],
        terms=[
            "100% advance against Proforma Invoice before dispatch.",
            "Dispatch within 48 hours of payment credit.",
        ],
        remarks="Urgent dispatch requested for maintenance shutdown.",
        created_by=admin_user.name,
        created_by_role=admin_user.role,
        stock_reserved=False,
        stock_deducted=False,
    )
    db.add(pi2)
    db.flush()
    db.add(
        DocumentItem(
            document_id=pi2.id,
            sr=1,
            product_id=p3.id,
            item_name=p3.item_name,
            technical_specs=p3.technical_specs,
            hsn_code=p3.hsn_code,
            qty=2,
            unit=p3.unit,
            rate=p3.rate,
            taxable_value=fin_pi2["items"][0]["taxable_value"],
        )
    )

    # Doc 3: Tax Invoice SI-0111 for Dainichi Color India
    ti3_items = [
        {
            "sr": 1,
            "product_id": p4.id,
            "item_name": p4.item_name,
            "technical_specs": p4.technical_specs,
            "hsn_code": p4.hsn_code,
            "qty": 1,
            "unit": p4.unit,
            "rate": p4.rate,
        }
    ]
    fin_ti3 = compute_document_financials(ti3_items, cust_dainichi.state_code, company.state_code)
    ti3 = Document(
        doc_type="TAX_INVOICE",
        doc_number="SI-0111",
        doc_date=date(2026, 10, 25),
        status="FULFILLED",
        customer_id=cust_dainichi.id,
        buyer_order_ref="DC/PO/2026-27/441",
        buyer_order_date=date(2026, 10, 22),
        mode_of_dispatch="Direct Plant Vehicle",
        place_of_supply=cust_dainichi.state_name,
        sub_total=fin_ti3["sub_total"],
        cgst_rate=fin_ti3["cgst_rate"],
        cgst_amount=fin_ti3["cgst_amount"],
        sgst_rate=fin_ti3["sgst_rate"],
        sgst_amount=fin_ti3["sgst_amount"],
        igst_rate=fin_ti3["igst_rate"],
        igst_amount=fin_ti3["igst_amount"],
        rounding_off=fin_ti3["rounding_off"],
        grand_total=fin_ti3["grand_total"],
        amount_in_words=fin_ti3["amount_in_words"],
        terms=[
            "Payment received in full.",
            "Goods once sold will not be taken back.",
        ],
        payment_note="Payment received via RTGS UTR# PUNBR5202610250098 on 25-Oct-2026",
        remarks="Delivered directly to Neemrana manufacturing line.",
        created_by=admin_user.name,
        created_by_role=admin_user.role,
        stock_reserved=False,
        stock_deducted=True,
    )
    db.add(ti3)
    db.flush()
    db.add(
        DocumentItem(
            document_id=ti3.id,
            sr=1,
            product_id=p4.id,
            item_name=p4.item_name,
            technical_specs=p4.technical_specs,
            hsn_code=p4.hsn_code,
            qty=1,
            unit=p4.unit,
            rate=p4.rate,
            taxable_value=fin_ti3["items"][0]["taxable_value"],
        )
    )

    # Doc 4: Delivery Challan DC-0687 for Om Surgical Industries
    dc4_items = [
        {
            "sr": 1,
            "product_id": None,
            "item_name": "Regrinding of Napkin Die & Anvil Roller",
            "technical_specs": "High precision CNC cylindrical regrinding, hard-facing inspection, and dynamic runout testing under 3 microns",
            "hsn_code": "998898",
            "qty": 1,
            "unit": "Job",
            "rate": Decimal("18500.00"),
        }
    ]
    fin_dc4 = compute_document_financials(dc4_items, cust_om.state_code, company.state_code)
    dc4 = Document(
        doc_type="DELIVERY_CHALLAN",
        doc_number="DC-0687",
        doc_date=date(2026, 10, 27),
        status="FULFILLED",
        customer_id=cust_om.id,
        buyer_order_ref="OM/JW/ROHTAK/109",
        buyer_order_date=date(2026, 10, 24),
        mode_of_dispatch="Jaipur Golden Transport",
        transporter_name="Jaipur Golden Transport",
        vehicle_no="RJ14TG3554",
        dispatch_date=date(2026, 10, 27),
        place_of_supply=cust_om.state_name,
        sub_total=fin_dc4["sub_total"],
        cgst_rate=fin_dc4["cgst_rate"],
        cgst_amount=fin_dc4["cgst_amount"],
        sgst_rate=fin_dc4["sgst_rate"],
        sgst_amount=fin_dc4["sgst_amount"],
        igst_rate=fin_dc4["igst_rate"],
        igst_amount=fin_dc4["igst_amount"],
        rounding_off=fin_dc4["rounding_off"],
        grand_total=fin_dc4["grand_total"],
        amount_in_words=fin_dc4["amount_in_words"],
        job_work_total_value=Decimal("18500.00"),
        terms=[
            "Challan issued for delivery of job-worked tooling.",
            "Subject to Jaipur jurisdiction.",
        ],
        remarks="Vehicle RJ14TG3554 driver verified. Die delivered in heavy-duty crate.",
        created_by=inv_user.name,
        created_by_role=inv_user.role,
        stock_reserved=False,
        stock_deducted=False,
    )
    db.add(dc4)
    db.flush()
    db.add(
        DocumentItem(
            document_id=dc4.id,
            sr=1,
            product_id=None,
            item_name="Regrinding of Napkin Die & Anvil Roller",
            technical_specs="High precision CNC cylindrical regrinding, hard-facing inspection, and dynamic runout testing under 3 microns",
            hsn_code="998898",
            qty=1,
            unit="Job",
            rate=Decimal("18500.00"),
            taxable_value=fin_dc4["items"][0]["taxable_value"],
        )
    )

    # Doc 5: Packing Slip DC-0681 for Truewow Hygiene Products
    ps5_items = [
        {
            "sr": 1,
            "product_id": p5.id,
            "item_name": p5.item_name,
            "technical_specs": p5.technical_specs,
            "hsn_code": p5.hsn_code,
            "qty": 2,
            "unit": p5.unit,
            "rate": p5.rate,
            "net_weight": "40 Kg",
        }
    ]
    fin_ps5 = compute_document_financials(ps5_items, cust_truewow.state_code, company.state_code)
    ps5 = Document(
        doc_type="PACKING_SLIP",
        doc_number="DC-0681",
        doc_date=date(2026, 10, 28),
        status="FULFILLED",
        customer_id=cust_truewow.id,
        buyer_order_ref="TW/PUR/2026/889",
        buyer_order_date=date(2026, 10, 26),
        mode_of_dispatch="V-Trans India Ltd.",
        place_of_supply=cust_truewow.state_name,
        pkg_number="1 Wooden Crate",
        gross_weight="50 Kg",
        sub_total=fin_ps5["sub_total"],
        cgst_rate=fin_ps5["cgst_rate"],
        cgst_amount=fin_ps5["cgst_amount"],
        sgst_rate=fin_ps5["sgst_rate"],
        sgst_amount=fin_ps5["sgst_amount"],
        igst_rate=fin_ps5["igst_rate"],
        igst_amount=fin_ps5["igst_amount"],
        rounding_off=fin_ps5["rounding_off"],
        grand_total=fin_ps5["grand_total"],
        amount_in_words=fin_ps5["amount_in_words"],
        terms=[
            "Goods packed in seaworthy export-standard wooden box.",
            "Net weight 40 Kg, Gross weight 50 Kg.",
        ],
        remarks="Packed in seaworthy wooden casing with anti-corrosive VCI plastic wrapping.",
        created_by=inv_user.name,
        created_by_role=inv_user.role,
        stock_reserved=False,
        stock_deducted=False,
    )
    db.add(ps5)
    db.flush()
    db.add(
        DocumentItem(
            document_id=ps5.id,
            sr=1,
            product_id=p5.id,
            item_name=p5.item_name,
            technical_specs=p5.technical_specs,
            hsn_code=p5.hsn_code,
            qty=2,
            unit=p5.unit,
            rate=p5.rate,
            taxable_value=fin_ps5["items"][0]["taxable_value"],
            net_weight="40 Kg",
        )
    )

    db.commit()
    print("--- [SEED] Completed Seeding Successfully ---")
