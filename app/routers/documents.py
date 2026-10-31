from datetime import date
from decimal import Decimal
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_roles
from app.models.company import CompanyProfile
from app.models.customer import Customer
from app.models.document import Document, DocumentItem
from app.models.inventory_log import InventoryLog
from app.models.product import Product
from app.models.user import User
from app.schemas.document import (
    ChallanCreateRequest,
    DocumentCreate,
    DocumentItemCreate,
    DocumentResponse,
    DocumentStatusUpdate,
    DocumentUpdate,
    PackingSlipCreateRequest,
)
from app.services.audit_service import create_audit_log
from app.services.document_service import generate_next_doc_number
from app.services.gst_service import compute_document_financials

router = APIRouter(prefix="/documents", tags=["Documents & Order Fulfilment"])


def _lock_products_by_ids(db: Session, product_ids: List[uuid.UUID]) -> dict:
    """Acquires SELECT ... FOR UPDATE row locks on products."""
    if not product_ids:
        return {}
    query = db.query(Product).filter(Product.id.in_(product_ids))
    if db.bind and db.bind.dialect.name == "postgresql":
        query = query.with_for_update()
    products = query.all()
    return {p.id: p for p in products}


@router.get("", response_model=List[DocumentResponse])
def get_documents(
    doc_type: Optional[str] = Query(None, description="QUOTATION | PROFORMA_INVOICE | TAX_INVOICE | DELIVERY_CHALLAN | PACKING_SLIP"),
    status: Optional[str] = Query(None, description="DRAFT | SENT | APPROVED | STOCK_RESERVED | FULFILLED | CANCELLED"),
    customer_id: Optional[uuid.UUID] = None,
    search: Optional[str] = Query(None, description="Search by document number or customer name"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List documents with comprehensive filtering (Authorized for all authenticated roles)."""
    query = db.query(Document)
    if doc_type:
        query = query.filter(Document.doc_type == doc_type.upper())
    if status:
        query = query.filter(Document.status == status.upper())
    if customer_id:
        query = query.filter(Document.customer_id == customer_id)
    if search:
        s = f"%{search.strip()}%"
        query = query.join(Customer).filter(
            or_(
                Document.doc_number.ilike(s),
                Customer.company_name.ilike(s),
            )
        )

    documents = query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
    return [DocumentResponse.model_validate(d) for d in documents]


@router.get("/{id}", response_model=DocumentResponse)
def get_document_by_id(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retrieve full document details with item lines and customer information."""
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentResponse.model_validate(doc)


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document(
    doc_in: DocumentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Create a new ERP Document (Quotation, Direct Delivery Challan, or Direct Tax Invoice).
    Role Constraints:
    - SELLER: Can only create 'QUOTATION'.
    - INVENTORY_MANAGER: Cannot create direct general documents (must use fulfillment endpoints).
    - ADMIN: Can create any document type.
    """
    doc_type = doc_in.doc_type.upper()
    if current_user.role == "SELLER" and doc_type != "QUOTATION":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sellers are only permitted to create Quotations.",
        )
    if current_user.role == "INVENTORY_MANAGER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inventory Managers cannot create general documents directly. Use inventory and challan endpoints.",
        )

    customer = db.query(Customer).filter(Customer.id == doc_in.customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    company = db.query(CompanyProfile).filter(CompanyProfile.id == 1).first()
    company_state_code = company.state_code if company else "08"

    # Compute financial figures and GST breakdown
    raw_items = [item.model_dump() for item in doc_in.items]
    financials = compute_document_financials(
        items_data=raw_items,
        customer_state_code=customer.state_code,
        company_state_code=company_state_code,
    )

    doc_number = doc_in.doc_number
    if not doc_number:
        doc_number = generate_next_doc_number(db, doc_type)

    existing_doc = db.query(Document).filter(Document.doc_number == doc_number).first()
    if existing_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document number '{doc_number}' already exists.",
        )

    doc = Document(
        doc_type=doc_type,
        doc_number=doc_number,
        doc_date=doc_in.doc_date,
        status=doc_in.status.upper(),
        parent_doc_id=doc_in.parent_doc_id,
        parent_doc_number=doc_in.parent_doc_number,
        customer_id=customer.id,
        buyer_order_ref=doc_in.buyer_order_ref,
        buyer_order_date=doc_in.buyer_order_date,
        mode_of_dispatch=doc_in.mode_of_dispatch,
        mode_of_payment=doc_in.mode_of_payment,
        place_of_supply=doc_in.place_of_supply or customer.state_name,
        sub_total=financials["sub_total"],
        cgst_rate=financials["cgst_rate"],
        cgst_amount=financials["cgst_amount"],
        sgst_rate=financials["sgst_rate"],
        sgst_amount=financials["sgst_amount"],
        igst_rate=financials["igst_rate"],
        igst_amount=financials["igst_amount"],
        rounding_off=financials["rounding_off"],
        grand_total=financials["grand_total"],
        amount_in_words=financials["amount_in_words"],
        terms=doc_in.terms,
        remarks=doc_in.remarks,
        parts_value=doc_in.parts_value,
        service_charges_value=doc_in.service_charges_value,
        job_work_total_value=doc_in.job_work_total_value,
        transporter_name=doc_in.transporter_name,
        vehicle_no=doc_in.vehicle_no,
        dispatch_date=doc_in.dispatch_date,
        pkg_number=doc_in.pkg_number,
        gross_weight=doc_in.gross_weight,
        payment_note=doc_in.payment_note,
        created_by=current_user.name,
        created_by_role=current_user.role,
        stock_reserved=False,
        stock_deducted=False,
    )
    db.add(doc)
    db.flush()

    for idx, item_data in enumerate(financials["items"], start=1):
        item = DocumentItem(
            document_id=doc.id,
            sr=item_data.get("sr") or idx,
            product_id=item_data.get("product_id"),
            item_name=item_data["item_name"],
            technical_specs=item_data.get("technical_specs"),
            hsn_code=item_data.get("hsn_code", "84779000"),
            qty=item_data["qty"],
            unit=item_data.get("unit", "Nos"),
            rate=item_data["rate"],
            taxable_value=item_data["taxable_value"],
            net_weight=item_data.get("net_weight"),
        )
        db.add(item)

    client_ip = request.client.host if request.client else None
    create_audit_log(
        db=db,
        user=current_user,
        action="CREATE_DOCUMENT",
        resource_type="DOCUMENT",
        resource_id=str(doc.id),
        details={"doc_number": doc.doc_number, "doc_type": doc.doc_type, "grand_total": float(doc.grand_total)},
        ip_address=client_ip,
    )

    db.commit()
    db.refresh(doc)
    return DocumentResponse.model_validate(doc)


@router.patch("/{id}/status", response_model=DocumentResponse)
def update_document_status(
    id: uuid.UUID,
    status_in: DocumentStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Transition document lifecycle status.
    - SELLER can only transition Quotations from DRAFT to SENT.
    - INVENTORY_MANAGER cannot update document approvals.
    - ADMIN can approve, fulfill, or cancel documents.
    - If status transitioned to CANCELLED and stock was reserved, automatically unreserves inventory.
    """
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    target_status = status_in.status.upper()
    valid_statuses = ["DRAFT", "SENT", "APPROVED", "STOCK_RESERVED", "FULFILLED", "CANCELLED"]
    if target_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{status_in.status}'. Allowed: {valid_statuses}",
        )

    if current_user.role == "SELLER":
        if doc.doc_type != "QUOTATION" or target_status != "SENT":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sellers may only mark DRAFT Quotations as SENT.",
            )
    elif current_user.role == "INVENTORY_MANAGER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inventory Managers do not have permissions to alter document status directly.",
        )

    old_status = doc.status
    doc.status = target_status

    # If document is cancelled and stock was reserved, release the reserved stock
    if target_status == "CANCELLED" and doc.stock_reserved:
        product_ids = [item.product_id for item in doc.items if item.product_id]
        products_map = _lock_products_by_ids(db, product_ids)

        for item in doc.items:
            if item.product_id and item.product_id in products_map:
                prod = products_map[item.product_id]
                prod.reserved_stock = max(0, prod.reserved_stock - item.qty)
                inv_log = InventoryLog(
                    product_id=prod.id,
                    action="UNRESERVED",
                    quantity=item.qty,
                    reference_doc_id=doc.id,
                    reference_doc_number=doc.doc_number,
                    notes=f"Released reservation due to cancellation of {doc.doc_number}",
                    created_by=current_user.name,
                )
                db.add(inv_log)
        doc.stock_reserved = False

    client_ip = request.client.host if request.client else None
    create_audit_log(
        db=db,
        user=current_user,
        action="UPDATE_DOCUMENT_STATUS",
        resource_type="DOCUMENT",
        resource_id=str(doc.id),
        details={"doc_number": doc.doc_number, "old_status": old_status, "new_status": target_status},
        ip_address=client_ip,
    )

    db.commit()
    db.refresh(doc)
    return DocumentResponse.model_validate(doc)


@router.post("/{id}/convert-to-pi", response_model=DocumentResponse)
def convert_to_proforma_invoice(
    id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    """
    Clone an APPROVED Quotation into a Proforma Invoice (POS-XXXX). (ADMIN only).
    """
    quotation = db.query(Document).filter(Document.id == id).first()
    if not quotation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")

    if quotation.doc_type != "QUOTATION":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only QUOTATION can be converted to PI. Current doc_type is '{quotation.doc_type}'.",
        )

    if quotation.status not in ["APPROVED", "SENT"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Quotation must be in 'APPROVED' or 'SENT' status to convert to PI. Current status: '{quotation.status}'.",
        )

    new_doc_number = generate_next_doc_number(db, "PROFORMA_INVOICE")

    pi = Document(
        doc_type="PROFORMA_INVOICE",
        doc_number=new_doc_number,
        doc_date=date.today(),
        status="APPROVED",
        parent_doc_id=quotation.id,
        parent_doc_number=quotation.doc_number,
        customer_id=quotation.customer_id,
        buyer_order_ref=quotation.buyer_order_ref,
        buyer_order_date=quotation.buyer_order_date,
        mode_of_dispatch=quotation.mode_of_dispatch,
        mode_of_payment=quotation.mode_of_payment,
        place_of_supply=quotation.place_of_supply,
        sub_total=quotation.sub_total,
        cgst_rate=quotation.cgst_rate,
        cgst_amount=quotation.cgst_amount,
        sgst_rate=quotation.sgst_rate,
        sgst_amount=quotation.sgst_amount,
        igst_rate=quotation.igst_rate,
        igst_amount=quotation.igst_amount,
        rounding_off=quotation.rounding_off,
        grand_total=quotation.grand_total,
        amount_in_words=quotation.amount_in_words,
        terms=quotation.terms,
        remarks=f"Converted from Quotation {quotation.doc_number}",
        created_by=current_user.name,
        created_by_role=current_user.role,
        stock_reserved=False,
        stock_deducted=False,
    )
    db.add(pi)
    db.flush()

    for item in quotation.items:
        new_item = DocumentItem(
            document_id=pi.id,
            sr=item.sr,
            product_id=item.product_id,
            item_name=item.item_name,
            technical_specs=item.technical_specs,
            hsn_code=item.hsn_code,
            qty=item.qty,
            unit=item.unit,
            rate=item.rate,
            taxable_value=item.taxable_value,
            net_weight=item.net_weight,
        )
        db.add(new_item)

    client_ip = request.client.host if request.client else None
    create_audit_log(
        db=db,
        user=current_user,
        action="CONVERT_TO_PROFORMA_INVOICE",
        resource_type="DOCUMENT",
        resource_id=str(pi.id),
        details={"source_quotation": quotation.doc_number, "pi_number": pi.doc_number},
        ip_address=client_ip,
    )

    db.commit()
    db.refresh(pi)
    return DocumentResponse.model_validate(pi)


@router.post("/{id}/reserve-stock", response_model=DocumentResponse)
def reserve_stock_for_document(
    id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "INVENTORY_MANAGER"])),
):
    """
    Row-level locking (SELECT ... FOR UPDATE) inventory reservation for an approved document.
    Validates available_stock >= required qty.
    Authorized for ADMIN and INVENTORY_MANAGER.
    """
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if doc.stock_reserved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stock has already been reserved for document '{doc.doc_number}'.",
        )

    if doc.status == "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reserve stock for a CANCELLED document.",
        )

    product_ids = [item.product_id for item in doc.items if item.product_id]
    if not product_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document contains no linked inventory products to reserve.",
        )

    # Acquire row locks on products
    products_map = _lock_products_by_ids(db, product_ids)

    # 1. Validation phase
    for item in doc.items:
        if item.product_id:
            product = products_map.get(item.product_id)
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product with ID '{item.product_id}' not found in inventory.",
                )
            if product.available_stock < item.qty:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Insufficient stock for product '{product.item_name}' (SKU: {product.sku}). "
                        f"Available: {product.available_stock}, Requested: {item.qty}"
                    ),
                )

    # 2. Reservation phase
    for item in doc.items:
        if item.product_id:
            product = products_map[item.product_id]
            product.reserved_stock += item.qty
            inv_log = InventoryLog(
                product_id=product.id,
                action="RESERVED",
                quantity=item.qty,
                reference_doc_id=doc.id,
                reference_doc_number=doc.doc_number,
                notes=f"Reserved {item.qty} units for {doc.doc_type} {doc.doc_number}",
                created_by=current_user.name,
            )
            db.add(inv_log)

    doc.stock_reserved = True
    doc.status = "STOCK_RESERVED"

    client_ip = request.client.host if request.client else None
    create_audit_log(
        db=db,
        user=current_user,
        action="RESERVE_STOCK",
        resource_type="DOCUMENT",
        resource_id=str(doc.id),
        details={"doc_number": doc.doc_number, "reserved_items_count": len(doc.items)},
        ip_address=client_ip,
    )

    db.commit()
    db.refresh(doc)
    return DocumentResponse.model_validate(doc)


@router.post("/{id}/convert-to-tax-invoice", response_model=DocumentResponse)
def convert_to_tax_invoice(
    id: uuid.UUID,
    payment_note: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    """
    Convert an order (PI or Quotation) to a Tax Invoice (SI-XXXX).
    Deducts total_stock -= qty (and adjusts reserved_stock if previously reserved).
    Logs STOCK_OUT in inventory_logs. Status becomes FULFILLED. (ADMIN only).
    """
    source_doc = db.query(Document).filter(Document.id == id).first()
    if not source_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source document not found")

    if source_doc.stock_deducted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stock for document '{source_doc.doc_number}' has already been deducted and fulfilled.",
        )

    product_ids = [item.product_id for item in source_doc.items if item.product_id]
    products_map = _lock_products_by_ids(db, product_ids)

    # If stock was NOT previously reserved, check if enough total available stock is present
    if not source_doc.stock_reserved:
        for item in source_doc.items:
            if item.product_id:
                prod = products_map.get(item.product_id)
                if prod and prod.available_stock < item.qty:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Insufficient stock to fulfill '{prod.item_name}' (SKU: {prod.sku}). "
                            f"Available: {prod.available_stock}, Required: {item.qty}"
                        ),
                    )

    new_invoice_number = generate_next_doc_number(db, "TAX_INVOICE")

    tax_inv = Document(
        doc_type="TAX_INVOICE",
        doc_number=new_invoice_number,
        doc_date=date.today(),
        status="FULFILLED",
        parent_doc_id=source_doc.id,
        parent_doc_number=source_doc.doc_number,
        customer_id=source_doc.customer_id,
        buyer_order_ref=source_doc.buyer_order_ref,
        buyer_order_date=source_doc.buyer_order_date,
        mode_of_dispatch=source_doc.mode_of_dispatch,
        mode_of_payment=source_doc.mode_of_payment,
        place_of_supply=source_doc.place_of_supply,
        sub_total=source_doc.sub_total,
        cgst_rate=source_doc.cgst_rate,
        cgst_amount=source_doc.cgst_amount,
        sgst_rate=source_doc.sgst_rate,
        sgst_amount=source_doc.sgst_amount,
        igst_rate=source_doc.igst_rate,
        igst_amount=source_doc.igst_amount,
        rounding_off=source_doc.rounding_off,
        grand_total=source_doc.grand_total,
        amount_in_words=source_doc.amount_in_words,
        terms=source_doc.terms,
        remarks=f"Generated from {source_doc.doc_number}",
        payment_note=payment_note or source_doc.payment_note,
        created_by=current_user.name,
        created_by_role=current_user.role,
        stock_reserved=False,
        stock_deducted=True,
    )
    db.add(tax_inv)
    db.flush()

    for item in source_doc.items:
        new_item = DocumentItem(
            document_id=tax_inv.id,
            sr=item.sr,
            product_id=item.product_id,
            item_name=item.item_name,
            technical_specs=item.technical_specs,
            hsn_code=item.hsn_code,
            qty=item.qty,
            unit=item.unit,
            rate=item.rate,
            taxable_value=item.taxable_value,
            net_weight=item.net_weight,
        )
        db.add(new_item)

        # Inventory deduction
        if item.product_id and item.product_id in products_map:
            prod = products_map[item.product_id]
            prod.total_stock -= item.qty
            if source_doc.stock_reserved:
                prod.reserved_stock = max(0, prod.reserved_stock - item.qty)

            inv_log = InventoryLog(
                product_id=prod.id,
                action="STOCK_OUT",
                quantity=item.qty,
                reference_doc_id=tax_inv.id,
                reference_doc_number=tax_inv.doc_number,
                notes=f"Stock deducted for Tax Invoice {tax_inv.doc_number} (Ref: {source_doc.doc_number})",
                created_by=current_user.name,
            )
            db.add(inv_log)

    source_doc.status = "FULFILLED"
    source_doc.stock_deducted = True

    client_ip = request.client.host if request and request.client else None
    create_audit_log(
        db=db,
        user=current_user,
        action="CONVERT_TO_TAX_INVOICE",
        resource_type="DOCUMENT",
        resource_id=str(tax_inv.id),
        details={"source_doc": source_doc.doc_number, "tax_invoice": tax_inv.doc_number},
        ip_address=client_ip,
    )

    db.commit()
    db.refresh(tax_inv)
    return DocumentResponse.model_validate(tax_inv)


@router.post("/{id}/create-challan", response_model=DocumentResponse)
def create_delivery_challan(
    id: uuid.UUID,
    payload: ChallanCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "INVENTORY_MANAGER"])),
):
    """
    Creates a Delivery Challan (DC-XXXX) capturing dispatch, vehicle, and job work / parts details.
    Authorized for ADMIN and INVENTORY_MANAGER.
    """
    parent_doc = db.query(Document).filter(Document.id == id).first()
    if not parent_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent document not found")

    dc_number = generate_next_doc_number(db, "DELIVERY_CHALLAN")

    # If custom items provided, use them; otherwise copy from parent
    items_to_use = []
    if payload.items:
        items_to_use = [item.model_dump() for item in payload.items]
    else:
        for item in parent_doc.items:
            items_to_use.append({
                "sr": item.sr,
                "product_id": item.product_id,
                "item_name": item.item_name,
                "technical_specs": item.technical_specs,
                "hsn_code": item.hsn_code,
                "qty": item.qty,
                "unit": item.unit,
                "rate": item.rate,
                "net_weight": item.net_weight,
            })

    company = db.query(CompanyProfile).filter(CompanyProfile.id == 1).first()
    company_state_code = company.state_code if company else "08"
    customer = parent_doc.customer

    financials = compute_document_financials(
        items_data=items_to_use,
        customer_state_code=customer.state_code,
        company_state_code=company_state_code,
    )

    challan = Document(
        doc_type="DELIVERY_CHALLAN",
        doc_number=dc_number,
        doc_date=date.today(),
        status="FULFILLED",
        parent_doc_id=parent_doc.id,
        parent_doc_number=parent_doc.doc_number,
        customer_id=parent_doc.customer_id,
        buyer_order_ref=parent_doc.buyer_order_ref,
        buyer_order_date=parent_doc.buyer_order_date,
        mode_of_dispatch=parent_doc.mode_of_dispatch,
        mode_of_payment=parent_doc.mode_of_payment,
        place_of_supply=parent_doc.place_of_supply,
        sub_total=financials["sub_total"],
        cgst_rate=financials["cgst_rate"],
        cgst_amount=financials["cgst_amount"],
        sgst_rate=financials["sgst_rate"],
        sgst_amount=financials["sgst_amount"],
        igst_rate=financials["igst_rate"],
        igst_amount=financials["igst_amount"],
        rounding_off=financials["rounding_off"],
        grand_total=financials["grand_total"],
        amount_in_words=financials["amount_in_words"],
        terms=parent_doc.terms,
        remarks=payload.remarks or f"Delivery Challan against {parent_doc.doc_number}",
        parts_value=payload.parts_value or Decimal("0.00"),
        job_work_total_value=payload.job_work_total_value or Decimal("0.00"),
        transporter_name=payload.transporter_name,
        vehicle_no=payload.vehicle_no,
        dispatch_date=payload.dispatch_date or date.today(),
        created_by=current_user.name,
        created_by_role=current_user.role,
        stock_reserved=False,
        stock_deducted=False,
    )
    db.add(challan)
    db.flush()

    for idx, item_data in enumerate(financials["items"], start=1):
        item = DocumentItem(
            document_id=challan.id,
            sr=item_data.get("sr") or idx,
            product_id=item_data.get("product_id"),
            item_name=item_data["item_name"],
            technical_specs=item_data.get("technical_specs"),
            hsn_code=item_data.get("hsn_code", "84779000"),
            qty=item_data["qty"],
            unit=item_data.get("unit", "Nos"),
            rate=item_data["rate"],
            taxable_value=item_data["taxable_value"],
            net_weight=item_data.get("net_weight"),
        )
        db.add(item)

    client_ip = request.client.host if request.client else None
    create_audit_log(
        db=db,
        user=current_user,
        action="CREATE_DELIVERY_CHALLAN",
        resource_type="DOCUMENT",
        resource_id=str(challan.id),
        details={"challan_number": challan.doc_number, "vehicle_no": challan.vehicle_no},
        ip_address=client_ip,
    )

    db.commit()
    db.refresh(challan)
    return DocumentResponse.model_validate(challan)


@router.post("/{id}/create-packing-slip", response_model=DocumentResponse)
def create_packing_slip(
    id: uuid.UUID,
    payload: PackingSlipCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN", "INVENTORY_MANAGER"])),
):
    """
    Generates a Packing Slip capturing package count, gross weight, and itemized net weights.
    Authorized for ADMIN and INVENTORY_MANAGER.
    """
    parent_doc = db.query(Document).filter(Document.id == id).first()
    if not parent_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent document not found")

    ps_number = generate_next_doc_number(db, "PACKING_SLIP")

    packing_slip = Document(
        doc_type="PACKING_SLIP",
        doc_number=ps_number,
        doc_date=date.today(),
        status="FULFILLED",
        parent_doc_id=parent_doc.id,
        parent_doc_number=parent_doc.doc_number,
        customer_id=parent_doc.customer_id,
        buyer_order_ref=parent_doc.buyer_order_ref,
        buyer_order_date=parent_doc.buyer_order_date,
        mode_of_dispatch=parent_doc.mode_of_dispatch,
        place_of_supply=parent_doc.place_of_supply,
        sub_total=parent_doc.sub_total,
        cgst_rate=parent_doc.cgst_rate,
        cgst_amount=parent_doc.cgst_amount,
        sgst_rate=parent_doc.sgst_rate,
        sgst_amount=parent_doc.sgst_amount,
        igst_rate=parent_doc.igst_rate,
        igst_amount=parent_doc.igst_amount,
        rounding_off=parent_doc.rounding_off,
        grand_total=parent_doc.grand_total,
        amount_in_words=parent_doc.amount_in_words,
        terms=parent_doc.terms,
        remarks=payload.remarks or f"Packing Slip against {parent_doc.doc_number}",
        pkg_number=payload.pkg_number or "1 Wooden Crate",
        gross_weight=payload.gross_weight,
        created_by=current_user.name,
        created_by_role=current_user.role,
        stock_reserved=False,
        stock_deducted=False,
    )
    db.add(packing_slip)
    db.flush()

    # Clone items with net weights
    for item in parent_doc.items:
        net_wt = None
        if payload.item_net_weights:
            net_wt = payload.item_net_weights.get(str(item.sr)) or payload.item_net_weights.get(str(item.id))
        if not net_wt:
            net_wt = item.net_weight

        ps_item = DocumentItem(
            document_id=packing_slip.id,
            sr=item.sr,
            product_id=item.product_id,
            item_name=item.item_name,
            technical_specs=item.technical_specs,
            hsn_code=item.hsn_code,
            qty=item.qty,
            unit=item.unit,
            rate=item.rate,
            taxable_value=item.taxable_value,
            net_weight=net_wt,
        )
        db.add(ps_item)

    client_ip = request.client.host if request.client else None
    create_audit_log(
        db=db,
        user=current_user,
        action="CREATE_PACKING_SLIP",
        resource_type="DOCUMENT",
        resource_id=str(packing_slip.id),
        details={"ps_number": packing_slip.doc_number, "gross_weight": packing_slip.gross_weight},
        ip_address=client_ip,
    )

    db.commit()
    db.refresh(packing_slip)
    return DocumentResponse.model_validate(packing_slip)


@router.put("/{id}", response_model=DocumentResponse)
def update_document(
    id: uuid.UUID,
    doc_in: DocumentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Update document details and recalculate taxes.
    - ADMIN: Full access to edit.
    - SELLER: Allowed only if document is a QUOTATION with status DRAFT.
    - INVENTORY_MANAGER: Forbidden.
    """
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if current_user.role == "SELLER":
        if doc.doc_type != "QUOTATION" or doc.status != "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sellers can only modify DRAFT Quotations.",
            )
    elif current_user.role == "INVENTORY_MANAGER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inventory Managers do not have permissions to modify documents.",
        )

    customer_id = doc_in.customer_id or doc.customer_id
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    company = db.query(CompanyProfile).filter(CompanyProfile.id == 1).first()
    company_state_code = company.state_code if company else "08"

    # If items provided, recompute financials and replace items
    if doc_in.items is not None:
        raw_items = [item.model_dump() for item in doc_in.items]
        financials = compute_document_financials(
            items_data=raw_items,
            customer_state_code=customer.state_code,
            company_state_code=company_state_code,
        )

        doc.sub_total = financials["sub_total"]
        doc.cgst_rate = financials["cgst_rate"]
        doc.cgst_amount = financials["cgst_amount"]
        doc.sgst_rate = financials["sgst_rate"]
        doc.sgst_amount = financials["sgst_amount"]
        doc.igst_rate = financials["igst_rate"]
        doc.igst_amount = financials["igst_amount"]
        doc.rounding_off = financials["rounding_off"]
        doc.grand_total = financials["grand_total"]
        doc.amount_in_words = financials["amount_in_words"]

        # Delete existing items and add new ones
        db.query(DocumentItem).filter(DocumentItem.document_id == doc.id).delete()
        for idx, item_data in enumerate(financials["items"], start=1):
            item = DocumentItem(
                document_id=doc.id,
                sr=item_data.get("sr") or idx,
                product_id=item_data.get("product_id"),
                item_name=item_data["item_name"],
                technical_specs=item_data.get("technical_specs"),
                hsn_code=item_data.get("hsn_code", "84779000"),
                qty=item_data["qty"],
                unit=item_data.get("unit", "Nos"),
                rate=item_data["rate"],
                taxable_value=item_data["taxable_value"],
                net_weight=item_data.get("net_weight"),
            )
            db.add(item)

    update_data = doc_in.model_dump(exclude_unset=True, exclude={"items"})
    for field, value in update_data.items():
        setattr(doc, field, value)

    client_ip = request.client.host if request.client else None
    create_audit_log(
        db=db,
        user=current_user,
        action="UPDATE_DOCUMENT",
        resource_type="DOCUMENT",
        resource_id=str(doc.id),
        details={"doc_number": doc.doc_number},
        ip_address=client_ip,
    )

    db.commit()
    db.refresh(doc)
    return DocumentResponse.model_validate(doc)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["ADMIN"])),
):
    """Delete a document (ADMIN only; only allowed if status is DRAFT or CANCELLED)."""
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if doc.status not in ["DRAFT", "CANCELLED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only DRAFT or CANCELLED documents can be deleted. Current status: '{doc.status}'.",
        )

    client_ip = request.client.host if request.client else None
    create_audit_log(
        db=db,
        user=current_user,
        action="DELETE_DOCUMENT",
        resource_type="DOCUMENT",
        resource_id=str(doc.id),
        details={"doc_number": doc.doc_number, "doc_type": doc.doc_type},
        ip_address=client_ip,
    )

    db.delete(doc)
    db.commit()
    return None

