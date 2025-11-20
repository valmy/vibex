"""Add missing strategy columns order_preference and funding_rate_threshold

Revision ID: 4add75c79922
Revises: e44e20d265c6
Create Date: 2025-11-20 10:45:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4add75c79922"
down_revision: Union[str, Sequence[str], None] = "c38b24f60f6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing columns to strategies table."""
    # Add order_preference column
    op.add_column(
        "strategies",
        sa.Column("order_preference", sa.String(50), nullable=False, server_default="any"),
        schema="trading",
    )

    # Add funding_rate_threshold column
    op.add_column(
        "strategies",
        sa.Column("funding_rate_threshold", sa.Float, nullable=False, server_default="0.0"),
        schema="trading",
    )


def downgrade() -> None:
    """Remove the added columns from strategies table."""
    op.drop_column("strategies", "funding_rate_threshold", schema="trading")
    op.drop_column("strategies", "order_preference", schema="trading")
