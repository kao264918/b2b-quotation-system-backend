from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


ZERO = Decimal("0")
TWO_DP = Decimal("0.01")


def quantize_money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(TWO_DP, rounding=ROUND_HALF_UP)


def calculate_total_cost(items: Iterable[object]) -> Decimal:
    total = ZERO
    for item in items:
        snapshot_cost = getattr(item, "snapshot_cost", None)
        quantity = getattr(item, "quantity", ZERO)
        if snapshot_cost is None:
            continue
        total += Decimal(snapshot_cost) * Decimal(quantity)
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


def recalculate_quote_cost_fields(quote: object) -> None:
    items = list(getattr(quote, "items", []) or [])
    total_cost = calculate_total_cost(items)
    gross_profit_amount = calculate_gross_profit_amount(getattr(quote, "subtotal", ZERO), total_cost)
    gross_profit_rate = calculate_gross_profit_rate(getattr(quote, "subtotal", ZERO), gross_profit_amount)
    missing_item_ids = identify_missing_cost_item_ids(items)

    setattr(quote, "total_cost", total_cost)
    setattr(quote, "gross_profit_amount", gross_profit_amount)
    setattr(quote, "gross_profit_rate", gross_profit_rate)
    setattr(quote, "cost_status", "missing" if missing_item_ids else "ok")
