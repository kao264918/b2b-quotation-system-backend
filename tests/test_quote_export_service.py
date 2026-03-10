from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from openpyxl import load_workbook

from app.services.quote_export import generate_quote_excel


def _build_quote(items=None):
    now = datetime(2026, 3, 10, tzinfo=timezone.utc)
    return SimpleNamespace(
        quote_number="QUO-2603-001",
        version=3,
        title="2026 Q2 展場整合報價",
        created_at=now,
        subtotal=Decimal("1000.00"),
        tax_total=Decimal("50.00"),
        total=Decimal("1050.00"),
        items=items or [],
        customer=SimpleNamespace(
            company_name="測試客戶股份有限公司",
            tax_id="12345678",
            contact_phone="0912345678",
            contact_name="王小明",
        ),
    )


def test_quote_excel_header_uses_customer_primary_contact_and_title():
    quote = _build_quote()

    excel_bytes = generate_quote_excel(quote)
    workbook = load_workbook(BytesIO(excel_bytes))
    worksheet = workbook.active

    assert worksheet["H2"].value == "2026 Q2 展場整合報價"
    assert worksheet["J10"].value == "2026 Q2 展場整合報價"
    assert worksheet["J6"].value == "測試客戶股份有限公司"
    assert worksheet["J7"].value == "12345678"
    assert worksheet["J8"].value == "0912345678"
    assert worksheet["J9"].value == "王小明"


def test_quote_excel_preserves_template_footer_notes_and_bank_info():
    quote = _build_quote()

    excel_bytes = generate_quote_excel(quote)
    workbook = load_workbook(BytesIO(excel_bytes))
    worksheet = workbook.active

    assert str(worksheet["D56"].value).strip() == "備  註"
    assert str(worksheet["F56"].value).strip() == "※此訂單簽訂後與正式合約具同等效力。"
    assert worksheet["B60"].value == "客 戶 回 簽"
    assert worksheet["F65"].value == "匯款銀行"


def test_quote_excel_still_clears_item_table_template_rows():
    quote = _build_quote()

    excel_bytes = generate_quote_excel(quote)
    workbook = load_workbook(BytesIO(excel_bytes))
    worksheet = workbook.active

    assert worksheet["G17"].value is None
    assert worksheet["F17"].value is None
    assert worksheet["J17"].value is None
    assert worksheet["G18"].value is None
