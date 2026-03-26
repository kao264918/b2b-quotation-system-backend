"""add list performance indexes

Revision ID: 260326_perf_idx
Revises: a1f8d7c9e2b3
Create Date: 2026-03-26 15:30:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "260326_perf_idx"
down_revision = "a1f8d7c9e2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS ix_rfqs_updated_at ON rfqs (updated_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rfqs_status ON rfqs (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rfqs_current_version_id ON rfqs (current_version_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rfqs_rfq_no ON rfqs (rfq_no)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rfqs_project_name ON rfqs (project_name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rfq_versions_rfq_id ON rfq_versions (rfq_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rfq_versions_version_number ON rfq_versions (version_number)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_catalog_items_created_at ON catalog_items (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_catalog_items_name ON catalog_items (name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_quotes_created_at ON quotes (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_quotes_status ON quotes (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customers_status ON customers (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customers_company_name ON customers (company_name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customers_tax_id ON customers (tax_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_customers_tax_id")
    op.execute("DROP INDEX IF EXISTS ix_customers_company_name")
    op.execute("DROP INDEX IF EXISTS ix_customers_status")
    op.execute("DROP INDEX IF EXISTS ix_quotes_status")
    op.execute("DROP INDEX IF EXISTS ix_quotes_created_at")
    op.execute("DROP INDEX IF EXISTS ix_catalog_items_name")
    op.execute("DROP INDEX IF EXISTS ix_catalog_items_created_at")
    op.execute("DROP INDEX IF EXISTS ix_rfq_versions_version_number")
    op.execute("DROP INDEX IF EXISTS ix_rfq_versions_rfq_id")
    op.execute("DROP INDEX IF EXISTS ix_rfqs_project_name")
    op.execute("DROP INDEX IF EXISTS ix_rfqs_rfq_no")
    op.execute("DROP INDEX IF EXISTS ix_rfqs_current_version_id")
    op.execute("DROP INDEX IF EXISTS ix_rfqs_status")
    op.execute("DROP INDEX IF EXISTS ix_rfqs_updated_at")
