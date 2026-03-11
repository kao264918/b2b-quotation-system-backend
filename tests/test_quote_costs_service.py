from decimal import Decimal

from app.services.quote_costs import (
    calculate_gross_profit_amount,
    calculate_gross_profit_rate,
    calculate_total_cost,
    identify_missing_cost_item_ids,
    recalculate_quote_cost_fields,
)


class _FakeItem:
    def __init__(
        self,
        item_id: str,
        quantity: str,
        snapshot_cost: str | None,
        *,
        area_unit: str | None = None,
        rfq_area_unit: str | None = None,
    ):
        self.id = item_id
        self.quantity = Decimal(quantity)
        self.snapshot_cost = Decimal(snapshot_cost) if snapshot_cost is not None else None
        self.area_unit = Decimal(area_unit) if area_unit is not None else None
        self.unit = "pcs"
        self.rfq_item = (
            type("_FakeRFQItem", (), {"area_unit": Decimal(rfq_area_unit), "item_type": "output"})()
            if rfq_area_unit is not None
            else None
        )


class _FakeQuote:
    def __init__(self, subtotal: str, items: list[_FakeItem]):
        self.subtotal = Decimal(subtotal)
        self.items = items
        self.total_cost = Decimal("0")
        self.gross_profit_amount = Decimal("0")
        self.gross_profit_rate = Decimal("0")
        self.cost_status = "ok"


def test_calculate_total_cost_ignores_missing_snapshot_cost() -> None:
    items = [
        _FakeItem("i1", "2", "20.50"),
        _FakeItem("i2", "3", None),
    ]
    assert calculate_total_cost(items) == Decimal("41.00")


def test_calculate_total_cost_multiplies_area_unit_from_quote_item() -> None:
    item = _FakeItem("i1", "2", "20.50", area_unit="3")
    item.unit = "材"
    items = [item]
    assert calculate_total_cost(items) == Decimal("123.00")


def test_calculate_total_cost_multiplies_area_unit_from_rfq_item() -> None:
    items = [_FakeItem("i1", "2", "20.50", rfq_area_unit="4")]
    assert calculate_total_cost(items) == Decimal("164.00")


def test_calculate_total_cost_prefers_area_unit_from_description_over_rfq_item() -> None:
    item = _FakeItem("i1", "2", "20.50", rfq_area_unit="4")
    item.unit = "材"
    item.description = "輸出說明\n40.00 x 60.00 cm = 3.00 材"
    assert calculate_total_cost([item]) == Decimal("123.00")


def test_calculate_total_cost_ignores_area_unit_for_non_material_unit() -> None:
    item = _FakeItem("i1", "2", "20.50", area_unit="3")
    item.description = "一般品項\n40.00 x 60.00 cm = 3.00 材"
    assert calculate_total_cost([item]) == Decimal("41.00")


def test_calculate_gross_profit_rate_round_half_up() -> None:
    amount = calculate_gross_profit_amount(Decimal("100"), Decimal("66.665"))
    rate = calculate_gross_profit_rate(Decimal("100"), amount)
    assert amount == Decimal("33.34")
    assert rate == Decimal("33.34")


def test_calculate_gross_profit_rate_zero_revenue() -> None:
    assert calculate_gross_profit_rate(Decimal("0"), Decimal("10")) == Decimal("0.00")


def test_identify_missing_cost_item_ids() -> None:
    items = [
        _FakeItem("a", "1", None),
        _FakeItem("b", "1", "1.00"),
    ]
    assert identify_missing_cost_item_ids(items) == ["a"]


def test_recalculate_quote_cost_fields_sets_missing_status() -> None:
    area_item = _FakeItem("a", "2", "30.00", area_unit="2")
    area_item.unit = "材"
    quote = _FakeQuote(
        subtotal="200.00",
        items=[area_item, _FakeItem("b", "1", None)],
    )
    recalculate_quote_cost_fields(quote)
    assert quote.total_cost == Decimal("120.00")
    assert quote.gross_profit_amount == Decimal("80.00")
    assert quote.gross_profit_rate == Decimal("40.00")
    assert quote.cost_status == "missing"
