"""add_customer_currency_fields

Revision ID: 20260122_currency
Revises: 96c4ff4f672d
Create Date: 2026-01-22 16:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260122_currency'
down_revision: Union[str, None] = '96c4ff4f672d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add missing columns that were commented out in 96c4ff4f672d
    op.add_column('customers', sa.Column('default_currency', sa.String(), nullable=True, server_default='TWD'))
    op.add_column('customers', sa.Column('default_payment_terms', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('customers', 'default_payment_terms')
    op.drop_column('customers', 'default_currency')
