"""add promotions and quote invoice promotion snapshot

Revision ID: b260313promo
Revises: a1f8d7c9e2b3
Create Date: 2026-03-13 14:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b260313promo"
down_revision: Union[str, None] = "a1f8d7c9e2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in [column["name"] for column in inspector.get_columns(table_name)]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "promotions" not in inspector.get_table_names():
        op.create_table(
            "promotions",
            sa.Column("id", sa.String(), primary_key=True, nullable=False),
            sa.Column("promotion_code", sa.String(), nullable=False),
            sa.Column("promotion_name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("internal_memo", sa.Text(), nullable=True),
            sa.Column("type", sa.String(length=20), nullable=False),
            sa.Column("discount_value", sa.Numeric(12, 2), nullable=False),
            sa.Column("minimum_order_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
            sa.Column("scope", sa.String(length=20), nullable=False, server_default="all_products"),
            sa.Column("scope_category", sa.String(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("promotion_code", name="uq_promotions_promotion_code"),
        )
        op.create_index("ix_promotions_is_active", "promotions", ["is_active"])
        op.create_index("ix_promotions_window", "promotions", ["start_at", "end_at"])
        op.create_index("ix_promotions_scope", "promotions", ["scope"])
        op.create_index("ix_promotions_scope_category", "promotions", ["scope_category"])

    quotes_columns = {
        "promotion_id": sa.Column("promotion_id", sa.String(), sa.ForeignKey("promotions.id"), nullable=True),
        "promotion_discount_amount": sa.Column("promotion_discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        "promotion_code_snapshot": sa.Column("promotion_code_snapshot", sa.String(), nullable=True),
        "promotion_name_snapshot": sa.Column("promotion_name_snapshot", sa.String(), nullable=True),
        "promotion_type_snapshot": sa.Column("promotion_type_snapshot", sa.String(length=20), nullable=True),
        "promotion_value_snapshot": sa.Column("promotion_value_snapshot", sa.Numeric(12, 2), nullable=True),
        "promotion_scope_snapshot": sa.Column("promotion_scope_snapshot", sa.String(length=20), nullable=True),
        "promotion_scope_category_snapshot": sa.Column("promotion_scope_category_snapshot", sa.String(), nullable=True),
    }
    for name, column in quotes_columns.items():
        if not _has_column(inspector, "quotes", name):
            op.add_column("quotes", column)

    invoice_columns = {
        "promotion_discount_amount": sa.Column("promotion_discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        "promotion_code_snapshot": sa.Column("promotion_code_snapshot", sa.String(), nullable=True),
        "promotion_name_snapshot": sa.Column("promotion_name_snapshot", sa.String(), nullable=True),
        "promotion_type_snapshot": sa.Column("promotion_type_snapshot", sa.String(length=20), nullable=True),
        "promotion_value_snapshot": sa.Column("promotion_value_snapshot", sa.Numeric(12, 2), nullable=True),
        "promotion_scope_snapshot": sa.Column("promotion_scope_snapshot", sa.String(length=20), nullable=True),
        "promotion_scope_category_snapshot": sa.Column("promotion_scope_category_snapshot", sa.String(), nullable=True),
    }
    for name, column in invoice_columns.items():
        if not _has_column(inspector, "invoices", name):
            op.add_column("invoices", column)


def downgrade() -> None:
    for column_name in [
        "promotion_scope_category_snapshot",
        "promotion_scope_snapshot",
        "promotion_value_snapshot",
        "promotion_type_snapshot",
        "promotion_name_snapshot",
        "promotion_code_snapshot",
        "promotion_discount_amount",
    ]:
        op.drop_column("invoices", column_name)

    for column_name in [
        "promotion_scope_category_snapshot",
        "promotion_scope_snapshot",
        "promotion_value_snapshot",
        "promotion_type_snapshot",
        "promotion_name_snapshot",
        "promotion_code_snapshot",
        "promotion_discount_amount",
        "promotion_id",
    ]:
        op.drop_column("quotes", column_name)

    op.drop_index("ix_promotions_scope_category", table_name="promotions")
    op.drop_index("ix_promotions_scope", table_name="promotions")
    op.drop_index("ix_promotions_window", table_name="promotions")
    op.drop_index("ix_promotions_is_active", table_name="promotions")
    op.drop_table("promotions")
