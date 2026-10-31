from decimal import Decimal, ROUND_HALF_UP
from typing import Union

_UNITS = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen"
]

_TENS = [
    "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"
]


def _two_digits_to_words(n: int) -> str:
    """Convert a number between 0 and 99 into Indian English words."""
    if n == 0:
        return ""
    if n < 20:
        return _UNITS[n]
    tens_part = _TENS[n // 10]
    unit_part = _UNITS[n % 10]
    if unit_part:
        return f"{tens_part}-{unit_part}"
    return tens_part


def _three_digits_to_words(n: int) -> str:
    """Convert a number between 0 and 999 into words."""
    parts = []
    hundreds = n // 100
    remainder = n % 100
    if hundreds > 0:
        parts.append(f"{_UNITS[hundreds]} Hundred")
    if remainder > 0:
        parts.append(_two_digits_to_words(remainder))
    return " ".join(parts)


def amount_to_indian_words(amount: Union[Decimal, float, int]) -> str:
    """
    Convert a monetary amount into formal Indian English Currency Words.
    E.g. 182900.00 -> 'INR One Lac Eighty-Two Thousand Nine Hundred Only.'
    """
    if amount is None:
        return ""

    dec_amount = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    is_negative = dec_amount < 0
    dec_amount = abs(dec_amount)

    rupees = int(dec_amount)
    paise = int((dec_amount - Decimal(rupees)) * 100)

    if rupees == 0 and paise == 0:
        return "INR Zero Only."

    parts = []

    # Indian Numbering Hierarchy:
    # Crores (10,000,000)
    crores = rupees // 10000000
    rem = rupees % 10000000

    # Lacs (100,000)
    lacs = rem // 100000
    rem = rem % 100000

    # Thousands (1,000)
    thousands = rem // 1000
    rem = rem % 1000

    # Hundreds and below (100)
    hundreds_and_below = rem

    if crores > 0:
        if crores >= 100:
            crores_str = _three_digits_to_words(crores)
        else:
            crores_str = _two_digits_to_words(crores)
        parts.append(f"{crores_str} Crore")

    if lacs > 0:
        parts.append(f"{_two_digits_to_words(lacs)} Lac")

    if thousands > 0:
        parts.append(f"{_two_digits_to_words(thousands)} Thousand")

    if hundreds_and_below > 0:
        parts.append(_three_digits_to_words(hundreds_and_below))

    rupees_str = " ".join(parts).strip() if parts else ""

    result = "INR " if not is_negative else "INR Minus "
    
    if rupees_str:
        result += rupees_str

    if paise > 0:
        paise_str = _two_digits_to_words(paise)
        if rupees_str:
            result += f" and {paise_str} Paise"
        else:
            result += f"{paise_str} Paise"

    result += " Only."
    return result

