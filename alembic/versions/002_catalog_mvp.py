"""Add catalog MVP fields and audit log

Revision ID: 002_catalog_mvp
Revises: 6f653838b11e
Create Date: 2026-01-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '002_catalog_mvp'
down_revision: Union[str, None] = 'add_company_email'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None





def upgrade() -> None:
    # ===== Part 1: Create audit_logs table =====
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('actor', sa.String(), nullable=True),
        sa.Column('changes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_logs_entity', 'audit_logs', ['entity_type', 'entity_id'])
    op.create_index('ix_audit_logs_timestamp', 'audit_logs', ['timestamp'])

    # ===== Part 2: Add new columns to catalog_items =====
    # Add optional columns first
    op.add_column('catalog_items', sa.Column('item_no', sa.String(), nullable=True))
    op.add_column('catalog_items', sa.Column('type', sa.String(), nullable=True))
    op.add_column('catalog_items', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('catalog_items', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    
    # ===== Part 3: Migrate existing data =====
    # Set default type to 'product' for existing items
    op.execute("UPDATE catalog_items SET type = 'product' WHERE type IS NULL")
    
    # Generate item_no for existing items
    # Use ROW_NUMBER to assign sequential numbers
    op.execute("""
        WITH numbered_products AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at) as rn
            FROM catalog_items
            WHERE type = 'product' AND item_no IS NULL
        )
        UPDATE catalog_items
        SET item_no = 'P-' || LPAD(numbered_products.rn::text, 4, '0')
        FROM numbered_products
        WHERE catalog_items.id = numbered_products.id
    """)
    
    # Set default values for reference_cost and default_price if NULL
    op.execute("UPDATE catalog_items SET reference_cost = 0.00 WHERE reference_cost IS NULL")
    op.execute("UPDATE catalog_items SET default_price = 0.00 WHERE default_price IS NULL")
    
    # ===== Part 4: Make columns NOT NULL and add constraints =====
    op.alter_column('catalog_items', 'item_no', nullable=False)
    op.alter_column('catalog_items', 'type', nullable=False)
    op.alter_column('catalog_items', 'reference_cost', nullable=False)
    op.alter_column('catalog_items', 'default_price', nullable=False)
    
    # Change description from String to Text
    op.alter_column('catalog_items', 'description',
                    type_=sa.Text(),
                    existing_type=sa.String(),
                    existing_nullable=True)
    
    # Add unique constraints
    op.create_unique_constraint('uq_catalog_item_name', 'catalog_items', ['name'])
    op.create_unique_constraint('uq_catalog_item_item_no', 'catalog_items', ['item_no'])
    
    # Add indexes
    op.create_index('ix_catalog_items_status', 'catalog_items', ['status'])
    op.create_index('ix_catalog_items_type', 'catalog_items', ['type'])
    op.create_index('ix_catalog_items_deleted_at', 'catalog_items', ['deleted_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_catalog_items_deleted_at', 'catalog_items')
    op.drop_index('ix_catalog_items_type', 'catalog_items')
    op.drop_index('ix_catalog_items_status', 'catalog_items')
    
    # Drop unique constraints
    op.drop_constraint('uq_catalog_item_item_no', 'catalog_items', type_='unique')
    op.drop_constraint('uq_catalog_item_name', 'catalog_items', type_='unique')
    
    # Revert description to String
    op.alter_column('catalog_items', 'description',
                    type_=sa.String(),
                    existing_type=sa.Text(),
                    existing_nullable=True)
    
    # Revert NOT NULL constraints
    op.alter_column('catalog_items', 'default_price', nullable=True)
    op.alter_column('catalog_items', 'reference_cost', nullable=True)
    op.alter_column('catalog_items', 'type', nullable=True)
    op.alter_column('catalog_items', 'item_no', nullable=True)
    
    # Drop new columns
    op.drop_column('catalog_items', 'deleted_at')
    op.drop_column('catalog_items', 'notes')
    op.drop_column('catalog_items', 'type')
    op.drop_column('catalog_items', 'item_no')
    
    # Drop audit_logs table
    op.drop_index('ix_audit_logs_timestamp', 'audit_logs')
    op.drop_index('ix_audit_logs_entity', 'audit_logs')
    op.drop_table('audit_logs')
