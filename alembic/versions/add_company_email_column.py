"""Add company_email column to customers

Revision ID: add_company_email
Revises: 6f653838b11e
Create Date: 2026-01-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_company_email'
down_revision: Union[str, None] = '6f653838b11e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('customers', sa.Column('company_email', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('customers', 'company_email')
