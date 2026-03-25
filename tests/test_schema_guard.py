from sqlalchemy import create_engine, text

from app.services.schema_guard import check_required_schema


def test_schema_guard_detects_missing_promotions_table():
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE quotes (id TEXT PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE invoices (id TEXT PRIMARY KEY)"))

    result = check_required_schema(engine)

    assert result.ok is False
    assert result.detail == "missing table: promotions"


def test_schema_guard_detects_missing_quote_columns():
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE promotions (
                    id TEXT PRIMARY KEY,
                    promotion_code TEXT,
                    promotion_name TEXT,
                    discount_value NUMERIC,
                    minimum_order_amount NUMERIC,
                    scope TEXT,
                    scope_category TEXT,
                    start_at TEXT,
                    end_at TEXT,
                    is_active BOOLEAN
                )
                """
            )
        )
        conn.execute(text("CREATE TABLE quotes (id TEXT PRIMARY KEY, promotion_id TEXT)"))
        conn.execute(
            text(
                """
                CREATE TABLE invoices (
                    id TEXT PRIMARY KEY,
                    promotion_discount_amount NUMERIC,
                    promotion_code_snapshot TEXT,
                    promotion_name_snapshot TEXT,
                    promotion_type_snapshot TEXT,
                    promotion_value_snapshot NUMERIC,
                    promotion_scope_snapshot TEXT,
                    promotion_scope_category_snapshot TEXT
                )
                """
            )
        )

    result = check_required_schema(engine)

    assert result.ok is False
    assert result.detail.startswith("missing columns on quotes:")
