from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Iterable


ZERO = Decimal("0")
TWO_DP = Decimal("0.01")
AREA_UNIT_PATTERN = re.compile(r"=\s*([\d.]+)\s*材")


def quantize_money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(TWO_DP, rounding=ROUND_HALF_UP)


def _parse_area_unit_from_description(item: object) -> Decimal | None:
    description = getattr(item, "description", None)
    if not description:
        return None

    match = AREA_UNIT_PATTERN.search(str(description))
    if not match:
        return None

    area_unit = Decimal(match.group(1))
    return area_unit if area_unit > ZERO else Decimal("1")


def _uses_area_pricing(item: object) -> bool:
    if getattr(item, "unit", None) == "材":
        return True

    rfq_item = getattr(item, "rfq_item", None)
    if rfq_item is not None and getattr(rfq_item, "item_type", None) == "output":
        return True

    return False


def _resolve_area_multiplier(item: object) -> Decimal:
    if not _uses_area_pricing(item):
        return Decimal("1")

    direct_area_unit = getattr(item, "area_unit", None)
    if direct_area_unit is not None:
        area_unit = Decimal(direct_area_unit)
        return area_unit if area_unit > ZERO else Decimal("1")

    description_area_unit = _parse_area_unit_from_description(item)
    if description_area_unit is not None:
        return description_area_unit

    rfq_item = getattr(item, "rfq_item", None)
    if rfq_item is not None:
        rfq_area_unit = getattr(rfq_item, "area_unit", None)
        if rfq_area_unit is not None:
            area_unit = Decimal(rfq_area_unit)
            return area_unit if area_unit > ZERO else Decimal("1")

    return Decimal("1")


def calculate_total_cost(items: Iterable[object]) -> Decimal:
    total = ZERO
    for item in items:
        snapshot_cost = getattr(item, "snapshot_cost", None)
        quantity = getattr(item, "quantity", ZERO)
        if snapshot_cost is None:
            continue
        area_multiplier = _resolve_area_multiplier(item)
        total += Decimal(snapshot_cost) * Decimal(quantity) * area_multiplier
    return quantize_money(total)


def calculate_gross_profit_amount(total_revenue_excl_tax: Decimal, total_cost: Decimal) -> Decimal:
    return quantize_money(Decimal(total_revenue_excl_tax) - Decimal(total_cost))


def calculate_gross_profit_rate(total_revenue_excl_tax: Decimal, gross_profit_amount: Decimal) -> Decimal:
    revenue = Decimal(total_revenue_excl_tax)
    if revenue == ZERO:
        return Decimal("0.00")
    rate = (Decimal(gross_profit_amount) / revenue) * Decimal("100")
    return quantize_money(rate)


def identify_missing_cost_item_ids(items: Iterable[object]) -> list[str]:
    missing_ids: list[str] = []
    for item in items:
        if getattr(item, "snapshot_cost", None) is None:
            item_id = getattr(item, "id", None)
            if item_id:
                missing_ids.append(str(item_id))
    return missing_ids


def calculate_quote_revenue_excl_tax(quote: object) -> Decimal:
    subtotal = Decimal(getattr(quote, "subtotal", ZERO) or ZERO)
    promotion_discount_amount = Decimal(getattr(quote, "promotion_discount_amount", ZERO) or ZERO)
    return quantize_money(max(ZERO, subtotal - promotion_discount_amount))


def recalculate_quote_cost_fields(quote: object) -> None:
    items = list(getattr(quote, "items", []) or [])
    revenue_excl_tax = calculate_quote_revenue_excl_tax(quote)
    total_cost = calculate_total_cost(items)
    gross_profit_amount = calculate_gross_profit_amount(revenue_excl_tax, total_cost)
    gross_profit_rate = calculate_gross_profit_rate(revenue_excl_tax, gross_profit_amount)
    missing_item_ids = identify_missing_cost_item_ids(items)

    setattr(quote, "total_cost", total_cost)
    setattr(quote, "gross_profit_amount", gross_profit_amount)
    setattr(quote, "gross_profit_rate", gross_profit_rate)
    setattr(quote, "cost_status", "missing" if missing_item_ids else "ok")
