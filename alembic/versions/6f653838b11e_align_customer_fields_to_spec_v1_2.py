"""Align customer fields to spec v1.2

Revision ID: 6f653838b11e
Revises: 001_initial
Create Date: 2026-01-09 16:00:57.075167

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f653838b11e'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop customer_contacts table (MVP: no multiple contacts)
    op.drop_table('customer_contacts')
    
    # Add optional columns first
    op.add_column('customers', sa.Column('industry', sa.String(), nullable=True))
    op.add_column('customers', sa.Column('website', sa.String(), nullable=True))
    op.add_column('customers', sa.Column('address_line2', sa.String(), nullable=True))
    op.add_column('customers', sa.Column('postal_code', sa.String(), nullable=True))
    op.add_column('customers', sa.Column('contact_phone', sa.String(), nullable=True))
    op.add_column('customers', sa.Column('contact_title', sa.String(), nullable=True))
    op.add_column('customers', sa.Column('billing_email', sa.String(), nullable=True))
    op.add_column('customers', sa.Column('notes', sa.Text(), nullable=True))
    
    # Add required columns with temporary nullable=True
    op.add_column('customers', sa.Column('address_line1', sa.String(), nullable=True))
    op.add_column('customers', sa.Column('city', sa.String(), nullable=True))
    op.add_column('customers', sa.Column('country', sa.String(), nullable=True))
    op.add_column('customers', sa.Column('contact_name', sa.String(), nullable=True))
    op.add_column('customers', sa.Column('contact_email', sa.String(), nullable=True))
    
    # Migrate existing data: copy from old columns to new required columns
    op.execute("""
        UPDATE customers SET 
            address_line1 = COALESCE(address, 'N/A'),
            city = 'N/A',
            country = 'Taiwan',
            contact_name = COALESCE(name, 'N/A'),
            contact_email = COALESCE(email, 'unknown@example.com')
        WHERE address_line1 IS NULL
    """)
    
    # Now make required columns NOT NULL
    op.alter_column('customers', 'address_line1', nullable=False)
    op.alter_column('customers', 'city', nullable=False)
    op.alter_column('customers', 'country', nullable=False)
    op.alter_column('customers', 'contact_name', nullable=False)
    op.alter_column('customers', 'contact_email', nullable=False)
    
    # Drop old columns
    op.drop_column('customers', 'phone')
    op.drop_column('customers', 'address')
    op.drop_column('customers', 'name')
    op.drop_column('customers', 'default_payment_terms')
    op.drop_column('customers', 'email')


def downgrade() -> None:
    # Restore old columns
    op.add_column('customers', sa.Column('email', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('customers', sa.Column('default_payment_terms', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('customers', sa.Column('name', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('customers', sa.Column('address', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.add_column('customers', sa.Column('phone', sa.VARCHAR(), autoincrement=False, nullable=True))
    
    # Migrate data back
    op.execute("""
        UPDATE customers SET 
            name = contact_name,
            email = contact_email,
            address = address_line1
    """)
    
    # Make name NOT NULL
    op.alter_column('customers', 'name', nullable=False)
    
    # Drop new columns
    op.drop_column('customers', 'notes')
    op.drop_column('customers', 'billing_email')
    op.drop_column('customers', 'contact_title')
    op.drop_column('customers', 'contact_phone')
    op.drop_column('customers', 'contact_email')
    op.drop_column('customers', 'contact_name')
    op.drop_column('customers', 'country')
    op.drop_column('customers', 'postal_code')
    op.drop_column('customers', 'city')
    op.drop_column('customers', 'address_line2')
    op.drop_column('customers', 'address_line1')
    op.drop_column('customers', 'website')
    op.drop_column('customers', 'industry')
    
    # Restore customer_contacts table
    op.create_table('customer_contacts',
        sa.Column('id', sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column('customer_id', sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column('name', sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column('title', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('email', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('phone', sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column('is_primary', sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], name=op.f('customer_contacts_customer_id_fkey')),
        sa.PrimaryKeyConstraint('id', name=op.f('customer_contacts_pkey'))
    )
