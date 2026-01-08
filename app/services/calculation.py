from decimal import Decimal
from typing import Dict, Any

def calculate_line_item(
    quantity: Decimal,
    unit_price: Decimal,
    tax_rate: Decimal
) -> Dict[str, Decimal]:
    """
    Returns: { subtotal, tax_amount, total_amount }
    """
    subtotal = quantity * unit_price
    tax_amount = subtotal * tax_rate
    total_amount = subtotal + tax_amount
    
    # 這裡可以加入更多 rounding logic (e.g., round half up to 2 decimal places)
    # 目前僅做基礎運算
    
    return {
        "subtotal": subtotal,
        "tax_amount": tax_amount,
        "total_amount": total_amount
    }

def calculate_totals(items: list[Dict[str, Any]]) -> Dict[str, Decimal]:
    """
    Returns: { subtotal, tax_total, total }
    """
    subtotal = sum((item.get("subtotal") or 0) for item in items)
    tax_total = sum((item.get("tax_amount") or 0) for item in items)
    total = sum((item.get("total_amount") or 0) for item in items)
    
    return {
        "subtotal": subtotal,
        "tax_total": tax_total,
        "total": total
    }
