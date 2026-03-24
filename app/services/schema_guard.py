from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import inspect
from sqlalchemy.engine import Engine


@dataclass
class SchemaCheckResult:
    ok: bool
    detail: str | None = None


PROMOTION_REQUIRED_TABLES = {
    "promotions": {
        "id",
        "promotion_code",
        "promotion_name",
        "discount_value",
        "minimum_order_amount",
        "scope",
        "scope_category",
        "start_at",
        "end_at",
        "is_active",
    },
    "quotes": {
        "promotion_id",
        "promotion_discount_amount",
        "promotion_code_snapshot",
        "promotion_name_snapshot",
        "promotion_type_snapshot",
        "promotion_value_snapshot",
        "promotion_scope_snapshot",
        "promotion_scope_category_snapshot",
    },
    "invoices": {
        "promotion_discount_amount",
        "promotion_code_snapshot",
        "promotion_name_snapshot",
        "promotion_type_snapshot",
        "promotion_value_snapshot",
        "promotion_scope_snapshot",
        "promotion_scope_category_snapshot",
    },
}


def check_required_schema(engine: Engine) -> SchemaCheckResult:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table_name, required_columns in PROMOTION_REQUIRED_TABLES.items():
        if table_name not in existing_tables:
            return SchemaCheckResult(
                ok=False,
                detail=f"missing table: {table_name}",
            )

        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        missing_columns = sorted(required_columns - existing_columns)
        if missing_columns:
            return SchemaCheckResult(
                ok=False,
                detail=f"missing columns on {table_name}: {', '.join(missing_columns)}",
            )

    return SchemaCheckResult(ok=True)
