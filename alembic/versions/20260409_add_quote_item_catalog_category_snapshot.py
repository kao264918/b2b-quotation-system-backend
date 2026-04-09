"""add quote item catalog category snapshot

Revision ID: 20260409_quote_item_cat
Revises: 260326_merge_heads
Create Date: 2026-04-09 19:30:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260409_quote_item_cat"
down_revision = "260326_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE quote_items ADD COLUMN IF NOT EXISTS catalog_category_snapshot VARCHAR"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE quote_items DROP COLUMN IF EXISTS catalog_category_snapshot"
    )
