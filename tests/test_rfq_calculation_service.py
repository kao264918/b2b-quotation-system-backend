from decimal import Decimal

from app.services.rfq_calculation import calculate_item_totals, recalculate_rfq_item, requires_area_pricing


def test_requires_area_pricing_for_output_or_tsai_unit():
    assert requires_area_pricing("output", "pcs") is True
    assert requires_area_pricing("product", "材") is True
    assert requires_area_pricing("service", "pcs") is False


def test_recalculate_rfq_item_applies_area_unit_for_tsai_unit():
    item = recalculate_rfq_item(
        {
            "item_type": "product",
            "unit": "材",
            "unit_price": Decimal("20"),
            "quantity": Decimal("2"),
            "length_cm": Decimal("100"),
            "width_cm": Decimal("200"),
        }
    )

    assert item["area_unit"] == Decimal("23")
    assert item["line_subtotal"] == Decimal("920.00")


def test_calculate_item_totals_applies_area_unit_for_tsai_unit():
    totals = calculate_item_totals(
        [
            {
                "item_type": "product",
                "unit": "材",
                "unit_price": Decimal("20"),
                "quantity": Decimal("2"),
                "length_cm": Decimal("100"),
                "width_cm": Decimal("200"),
            }
        ],
        "non_taxable",
    )

    assert totals["subtotal"] == Decimal("920.00")
    assert totals["tax_amount"] == Decimal("0.00")
    assert totals["total_amount"] == Decimal("920.00")


def test_calculate_item_totals_keeps_non_area_items_unchanged():
    totals = calculate_item_totals(
        [
            {
                "item_type": "product",
                "unit": "pcs",
                "unit_price": Decimal("20"),
                "quantity": Decimal("2"),
                "length_cm": Decimal("100"),
                "width_cm": Decimal("200"),
            }
        ],
        "non_taxable",
    )

    assert totals["subtotal"] == Decimal("40.00")
    assert totals["tax_amount"] == Decimal("0.00")
    assert totals["total_amount"] == Decimal("40.00")
