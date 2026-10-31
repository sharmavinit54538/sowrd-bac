from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Tuple

from app.core.config import settings
from app.services.number_to_words import amount_to_indian_words

TWO_PLACES = Decimal("0.01")


def calculate_line_item(qty: int, rate: Decimal) -> Decimal:
    """Calculate line item taxable value = qty * rate."""
    taxable = (Decimal(qty) * Decimal(rate)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return taxable


def determine_gst_rates(customer_state_code: str, company_state_code: str = None) -> Tuple[Decimal, Decimal, Decimal]:
    """
    Determine CGST, SGST, IGST rates.
    If intra-state (same state code): CGST = 9%, SGST = 9%, IGST = 0%.
    If inter-state (different state code): CGST = 0%, SGST = 0%, IGST = 18%.
    """
    comp_code = (company_state_code or settings.COMPANY_STATE_CODE).strip().zfill(2)
    cust_code = (customer_state_code or "").strip().zfill(2)

    if cust_code == comp_code:
        # Intra-state: Rajasthan -> Rajasthan
        return Decimal("9.00"), Decimal("9.00"), Decimal("0.00")
    else:
        # Inter-state
        return Decimal("0.00"), Decimal("0.00"), Decimal("18.00")


def compute_document_financials(
    items_data: List[Dict[str, Any]],
    customer_state_code: str,
    company_state_code: str = None,
) -> Dict[str, Any]:
    """
    Computes complete financial breakdown:
    - taxable values for each item
    - sub_total
    - CGST, SGST, IGST rates and amounts
    - rounding_off
    - grand_total
    - amount_in_words
    """
    sub_total = Decimal("0.00")
    computed_items = []

    for item in items_data:
        qty = int(item.get("qty", 1))
        rate = Decimal(str(item.get("rate", 0.00)))
        taxable_value = calculate_line_item(qty, rate)
        sub_total += taxable_value

        item_copy = dict(item)
        item_copy["taxable_value"] = taxable_value
        item_copy["rate"] = rate
        item_copy["qty"] = qty
        computed_items.append(item_copy)

    sub_total = sub_total.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    cgst_rate, sgst_rate, igst_rate = determine_gst_rates(customer_state_code, company_state_code)

    cgst_amount = Decimal("0.00")
    sgst_amount = Decimal("0.00")
    igst_amount = Decimal("0.00")

    if cgst_rate > 0:
        cgst_amount = (sub_total * (cgst_rate / Decimal("100.00"))).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    if sgst_rate > 0:
        sgst_amount = (sub_total * (sgst_rate / Decimal("100.00"))).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    if igst_rate > 0:
        igst_amount = (sub_total * (igst_rate / Decimal("100.00"))).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    exact_total = sub_total + cgst_amount + sgst_amount + igst_amount

    # Round to nearest whole rupee
    rounded_grand_total = exact_total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    rounding_off = (rounded_grand_total - exact_total).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    grand_total = rounded_grand_total.quantize(TWO_PLACES)

    amount_in_words = amount_to_indian_words(grand_total)

    return {
        "items": computed_items,
        "sub_total": sub_total,
        "cgst_rate": cgst_rate,
        "cgst_amount": cgst_amount,
        "sgst_rate": sgst_rate,
        "sgst_amount": sgst_amount,
        "igst_rate": igst_rate,
        "igst_amount": igst_amount,
        "rounding_off": rounding_off,
        "grand_total": grand_total,
        "amount_in_words": amount_in_words,
    }

