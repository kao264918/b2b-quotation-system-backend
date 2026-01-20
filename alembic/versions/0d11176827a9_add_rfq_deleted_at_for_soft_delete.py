"""add rfq deleted_at for soft delete

Revision ID: 0d11176827a9
Revises: f140e669adf2
Create Date: 2026-01-20 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0d11176827a9'
down_revision: Union[str, None] = 'f140e669adf2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('rfqs', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('rfqs', 'deleted_at')
