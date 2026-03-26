"""
RFQ Calculation Service

Backend-authoritative calculations for:
- Area unit (material dimension calculation)
- Line item subtotals
- Order totals with tax
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional
import math


# Tax rate mapping
TAX_RATES = {
    "taxable_5": Decimal("0.05"),
    "taxable_10": Decimal("0.10"),
    "non_taxable": Decimal("0"),
    "tax_exempt": Decimal("0"),
}


def requires_area_pricing(item_type: Optional[str], unit: Optional[str]) -> bool:
    """
    Determine whether an item should use area-based pricing.

    Business rule must stay aligned with frontend:
    - output type always requires area pricing
    - any item with unit "材" also requires area pricing
    """
    return item_type == "output" or unit == "材"


def calculate_area_unit(length_cm: Optional[Decimal], width_cm: Optional[Decimal]) -> Decimal:
    """
    Calculate area unit for output type items.
    Formula: ceil((length * width) / 900)
    
    Args:
        length_cm: Length in centimeters
        width_cm: Width in centimeters
    
    Returns:
        Decimal: Area unit (minimum 1)
    """
    if not length_cm or not width_cm or length_cm <= 0 or width_cm <= 0:
        return Decimal("1")
    
    area = length_cm * width_cm
    area_unit = math.ceil(float(area) / 900)
    return Decimal(str(max(1, area_unit)))


def calculate_line_subtotal(
    unit_price: Decimal,
    quantity: Decimal,
    area_unit: Decimal = Decimal("1")
) -> Decimal:
    """
    Calculate line item subtotal.
    Formula: unit_price * quantity * area_unit
    
    Args:
        unit_price: Unit price
        quantity: Quantity
        area_unit: Area unit (for output type items)
    
    Returns:
        Decimal: Line subtotal
    """
    return (unit_price * quantity * area_unit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_item_totals(
    items: List[Dict[str, Any]],
    tax_setting: str = "non_taxable"
) -> Dict[str, Decimal]:
    """
    Calculate order totals from items.
    
    Args:
        items: List of item dicts with 'unit_price', 'quantity', 'area_unit', 'item_type'
        tax_setting: Tax setting enum value
    
    Returns:
        Dict with subtotal, tax_amount, total_amount
    """
    subtotal = Decimal("0")
    
    for item in items:
        unit_price = Decimal(str(item.get("unit_price", 0)))
        quantity = Decimal(str(item.get("quantity", 0)))

        if requires_area_pricing(item.get("item_type"), item.get("unit")):
            length_cm = Decimal(str(item.get("length_cm", 0))) if item.get("length_cm") else None
            width_cm = Decimal(str(item.get("width_cm", 0))) if item.get("width_cm") else None
            area_unit = calculate_area_unit(length_cm, width_cm)
        else:
            area_unit = Decimal("1")
        
        line_subtotal = calculate_line_subtotal(unit_price, quantity, area_unit)
        subtotal += line_subtotal
    
    # Calculate tax
    tax_rate = TAX_RATES.get(tax_setting, Decimal("0"))
    tax_amount = (subtotal * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total_amount = subtotal + tax_amount
    
    return {
        "subtotal": subtotal,
        "tax_amount": tax_amount,
        "total_amount": total_amount,
    }


def recalculate_rfq_item(item_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recalculate derived fields for an RFQ item.
    
    Updates:
        - area_unit (if output type)
        - line_subtotal
    
    Args:
        item_data: Item data dict
    
    Returns:
        Updated item data dict
    """
    item_type = item_data.get("item_type", "product")
    unit_price = Decimal(str(item_data.get("unit_price", 0)))
    quantity = Decimal(str(item_data.get("quantity", 0)))
    
    if requires_area_pricing(item_type, item_data.get("unit")):
        length_cm = Decimal(str(item_data.get("length_cm", 0))) if item_data.get("length_cm") else None
        width_cm = Decimal(str(item_data.get("width_cm", 0))) if item_data.get("width_cm") else None
        area_unit = calculate_area_unit(length_cm, width_cm)
    else:
        area_unit = Decimal("1")
        # Clear dimension fields for non-output types
        item_data["length_cm"] = None
        item_data["width_cm"] = None
    
    item_data["area_unit"] = area_unit
    item_data["line_subtotal"] = calculate_line_subtotal(unit_price, quantity, area_unit)
    
    return item_data
