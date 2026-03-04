"""add dashboard trend index

Revision ID: a1f8d7c9e2b3
Revises: 9f31f3ec9f10
Create Date: 2026-03-04 22:05:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1f8d7c9e2b3"
down_revision: Union[str, None] = "9f31f3ec9f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_quotes_status_confirmed_at")
    op.execute("DROP INDEX IF EXISTS idx_quote_confirmed_at")
    op.execute("CREATE INDEX idx_quote_confirmed_at ON quotes (status, confirmed_at DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_quote_confirmed_at")
    op.execute("CREATE INDEX ix_quotes_status_confirmed_at ON quotes (status, confirmed_at)")
