"""add units table

Revision ID: 004_units
Revises: 003_rfq_item_material
Create Date: 2026-01-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_units'
down_revision: Union[str, None] = '003_rfq_item_material'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'units',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('label')
    )
    
    # Seed default units
    import uuid
    units_table = sa.table(
        'units',
        sa.column('id', sa.String),
        sa.column('label', sa.String),
        sa.column('status', sa.String),
    )
    op.bulk_insert(units_table, [
        {'id': str(uuid.uuid4()), 'label': 'pcs', 'status': 'active'},
        {'id': str(uuid.uuid4()), 'label': '材', 'status': 'active'},
        {'id': str(uuid.uuid4()), 'label': 'kg', 'status': 'active'},
        {'id': str(uuid.uuid4()), 'label': 'set', 'status': 'active'},
        {'id': str(uuid.uuid4()), 'label': 'day', 'status': 'active'},
    ])


def downgrade() -> None:
    op.drop_table('units')
