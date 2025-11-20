"""add_balance_usd_to_account

Revision ID: 8228259bbdbf
Revises: 2779b8a86eec
Create Date: 2025-11-20 10:00:49.511699
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "8228259bbdbf"
down_revision = "2779b8a86eec"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add balance_usd column with default 0.0 to existing accounts table
    op.add_column(
        "accounts",
        sa.Column("balance_usd", sa.Float(), nullable=False, server_default="0.0"),
        schema="trading",
    )
    # Remove the server default after column creation
    op.alter_column("accounts", "balance_usd", server_default=None, schema="trading")


def downgrade() -> None:
    op.drop_column("accounts", "balance_usd", schema="trading")
