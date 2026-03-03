"""add_quote_cost_snapshot_and_kpi_fields

Revision ID: 9f31f3ec9f10
Revises: 0720cdfc3bae
Create Date: 2026-03-03 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f31f3ec9f10'
down_revision: Union[str, None] = '0720cdfc3bae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('quote_items', sa.Column('snapshot_cost', sa.Numeric(12, 2), nullable=True))

    op.add_column('quotes', sa.Column('cost_status', sa.String(length=20), nullable=False, server_default='ok'))
    op.add_column('quotes', sa.Column('total_cost', sa.Numeric(12, 2), nullable=False, server_default='0'))
    op.add_column('quotes', sa.Column('gross_profit_amount', sa.Numeric(12, 2), nullable=False, server_default='0'))
    op.add_column('quotes', sa.Column('gross_profit_rate', sa.Numeric(7, 2), nullable=False, server_default='0'))
    op.add_column('quotes', sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True))

    op.execute(
        """
        UPDATE quotes
        SET cost_status = CASE
            WHEN EXISTS (
                SELECT 1
                FROM quote_items qi
                WHERE qi.quote_id = quotes.id
                  AND qi.snapshot_cost IS NULL
            ) THEN 'missing'
            ELSE 'ok'
        END
        """
    )

    op.create_index('ix_quotes_status_confirmed_at', 'quotes', ['status', 'confirmed_at'], unique=False)
    op.create_index('ix_quotes_cost_status', 'quotes', ['cost_status'], unique=False)
    op.create_index('ix_quote_items_quote_id_snapshot_cost', 'quote_items', ['quote_id', 'snapshot_cost'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_quote_items_quote_id_snapshot_cost', table_name='quote_items')
    op.drop_index('ix_quotes_cost_status', table_name='quotes')
    op.drop_index('ix_quotes_status_confirmed_at', table_name='quotes')

    op.drop_column('quotes', 'confirmed_at')
    op.drop_column('quotes', 'gross_profit_rate')
    op.drop_column('quotes', 'gross_profit_amount')
    op.drop_column('quotes', 'total_cost')
    op.drop_column('quotes', 'cost_status')

    op.drop_column('quote_items', 'snapshot_cost')
