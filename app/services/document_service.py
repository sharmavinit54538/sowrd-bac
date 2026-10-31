import re
from sqlalchemy.orm import Session
from app.models.document import Document

DOC_PREFIXES = {
    "QUOTATION": "Q-",
    "PROFORMA_INVOICE": "POS-",
    "TAX_INVOICE": "SI-",
    "DELIVERY_CHALLAN": "DC-",
    "PACKING_SLIP": "PS-",
}


def generate_next_doc_number(db: Session, doc_type: str) -> str:
    """
    Generates sequential prefix document numbers.
    E.g. Q-0405 -> Q-0406, POS-0159 -> POS-0160, SI-0111 -> SI-0112.
    """
    prefix = DOC_PREFIXES.get(doc_type.upper(), "DOC-")
    
    # Query all document numbers starting with this prefix
    docs = (
        db.query(Document.doc_number)
        .filter(Document.doc_number.like(f"{prefix}%"))
        .all()
    )

    max_num = 0
    # Regular expression to extract trailing digits
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")

    for (doc_num,) in docs:
        match = pattern.match(doc_num)
        if match:
            try:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
            except ValueError:
                continue

    if max_num == 0:
        # Default starting sequence numbers if empty
        defaults = {
            "QUOTATION": 100,
            "PROFORMA_INVOICE": 100,
            "TAX_INVOICE": 100,
            "DELIVERY_CHALLAN": 100,
            "PACKING_SLIP": 100,
        }
        next_num = defaults.get(doc_type.upper(), 1)
    else:
        next_num = max_num + 1

    return f"{prefix}{next_num:04d}"

