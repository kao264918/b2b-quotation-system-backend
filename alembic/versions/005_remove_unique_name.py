"""remove unique constraint on name

Revision ID: 005_remove_unique_name
Revises: 004_units
Create Date: 2026-01-13 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_remove_unique_name'
down_revision: Union[str, None] = '004_units'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop unique constraint on name
    op.drop_constraint('uq_catalog_item_name', 'catalog_items', type_='unique')
    
    # Create non-unique index for performance (since we look up by name)
    op.create_index(op.f('ix_catalog_items_name'), 'catalog_items', ['name'], unique=False)


def downgrade() -> None:
    # Drop index
    op.drop_index(op.f('ix_catalog_items_name'), table_name='catalog_items')
    
    # Restore unique constraint
    op.create_unique_constraint('uq_catalog_item_name', 'catalog_items', ['name'])
