"""Simple, deterministic flat-percentage tax calculation for sales lines."""


def calculate_tax(subtotal: float, tax_percent: float) -> float:
    if subtotal < 0:
        raise ValueError("subtotal cannot be negative")
    if tax_percent < 0:
        raise ValueError("tax_percent cannot be negative")
    return round(subtotal * tax_percent / 100, 2)


def calculate_totals(qty: float, unit_price: float, tax_percent: float) -> dict:
    if qty <= 0:
        raise ValueError("qty must be > 0")
    if unit_price < 0:
        raise ValueError("unit_price cannot be negative")
    subtotal = round(qty * unit_price, 2)
    tax = calculate_tax(subtotal, tax_percent)
    return {
        "subtotal": subtotal,
        "tax": tax,
        "total": round(subtotal + tax, 2),
    }
