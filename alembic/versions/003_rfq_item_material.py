"""Add RFQ Item material fields for Catalog snapshot

Revision ID: 003_rfq_item_material
Revises: 002_catalog_mvp
Create Date: 2026-01-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_rfq_item_material'
down_revision: Union[str, None] = '002_catalog_mvp'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns (all nullable first)
    op.add_column('rfq_items', sa.Column('source_item_no', sa.String(), nullable=True))
    op.add_column('rfq_items', sa.Column('type', sa.String(), nullable=True))
    op.add_column('rfq_items', sa.Column('length_cm', sa.Numeric(10, 2), nullable=True))
    op.add_column('rfq_items', sa.Column('width_cm', sa.Numeric(10, 2), nullable=True))
    op.add_column('rfq_items', sa.Column('area_unit', sa.Numeric(10, 2), nullable=True))
    
    # Set default type to 'product' for existing items
    op.execute("UPDATE rfq_items SET type = 'product' WHERE type IS NULL")
    
    # Make type NOT NULL
    op.alter_column('rfq_items', 'type', nullable=False)


def downgrade() -> None:
    # Revert type to nullable
    op.alter_column('rfq_items', 'type', nullable=True)
    
    # Drop new columns
    op.drop_column('rfq_items', 'area_unit')
    op.drop_column('rfq_items', 'width_cm')
    op.drop_column('rfq_items', 'length_cm')
    op.drop_column('rfq_items', 'type')
    op.drop_column('rfq_items', 'source_item_no')
