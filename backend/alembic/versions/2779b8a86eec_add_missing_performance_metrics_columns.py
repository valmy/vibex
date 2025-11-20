"""add_missing_performance_metrics_columns

Revision ID: 2779b8a86eec
Revises: bd90195a9f69
Create Date: 2025-11-20 09:35:26.829349

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2779b8a86eec"
down_revision: Union[str, Sequence[str], None] = "bd90195a9f69"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add missing columns to performance_metrics table
    op.add_column(
        "performance_metrics",
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        schema="trading",
    )
    op.add_column(
        "performance_metrics",
        sa.Column("max_drawdown_percent", sa.Float(), nullable=True),
        schema="trading",
    )
    op.add_column(
        "performance_metrics",
        sa.Column("sharpe_ratio", sa.Float(), nullable=True),
        schema="trading",
    )
    op.add_column(
        "performance_metrics",
        sa.Column("sortino_ratio", sa.Float(), nullable=True),
        schema="trading",
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove columns from performance_metrics table
    op.drop_column("performance_metrics", "sortino_ratio", schema="trading")
    op.drop_column("performance_metrics", "sharpe_ratio", schema="trading")
    op.drop_column("performance_metrics", "max_drawdown_percent", schema="trading")
    op.drop_column("performance_metrics", "max_drawdown", schema="trading")
