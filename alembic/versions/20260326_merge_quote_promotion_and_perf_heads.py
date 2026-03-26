"""merge quote promotion and performance index heads

Revision ID: 20260326_merge_quote_promotion_and_perf_heads
Revises: b260313promo, 20260326_add_list_performance_indexes
Create Date: 2026-03-26 16:20:00.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260326_merge_quote_promotion_and_perf_heads"
down_revision: Union[str, Sequence[str], None] = (
    "b260313promo",
    "20260326_add_list_performance_indexes",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge revision only: no schema changes.
    pass


def downgrade() -> None:
    # Merge revision only: no schema changes.
    pass
