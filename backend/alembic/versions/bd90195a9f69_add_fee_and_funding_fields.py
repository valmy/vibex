"""add_fee_and_funding_fields

Revision ID: bd90195a9f69
Revises: c38b24f60f6d
Create Date: 2025-11-19 16:45:55.658852

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bd90195a9f69"
down_revision: Union[str, Sequence[str], None] = "c38b24f60f6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add columns to accounts table
    op.add_column(
        "accounts",
        sa.Column("maker_fee_bps", sa.Float(), nullable=False, server_default="5.0"),
        schema="trading",
    )
    op.add_column(
        "accounts",
        sa.Column("taker_fee_bps", sa.Float(), nullable=False, server_default="20.0"),
        schema="trading",
    )

    # Add columns to strategy_performances table
    op.add_column(
        "strategy_performances",
        sa.Column("total_fees_paid", sa.Float(), nullable=False, server_default="0.0"),
        schema="trading",
    )
    op.add_column(
        "strategy_performances",
        sa.Column("total_funding_paid", sa.Float(), nullable=False, server_default="0.0"),
        schema="trading",
    )
    op.add_column(
        "strategy_performances",
        sa.Column("total_liquidations", sa.Integer(), nullable=False, server_default="0"),
        schema="trading",
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove columns from strategy_performances table
    op.drop_column("strategy_performances", "total_liquidations", schema="trading")
    op.drop_column("strategy_performances", "total_funding_paid", schema="trading")
    op.drop_column("strategy_performances", "total_fees_paid", schema="trading")

    # Remove columns from accounts table
    op.drop_column("accounts", "taker_fee_bps", schema="trading")
    op.drop_column("accounts", "maker_fee_bps", schema="trading")
