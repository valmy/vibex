"""add_multi_asset_decision_support

Revision ID: c38b24f60f6d
Revises: 1a7275c79921
Create Date: 2025-11-13 15:11:25.887637

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c38b24f60f6d"
down_revision: Union[str, Sequence[str], None] = "1a7275c79921"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to support multi-asset decisions."""
    # Add new multi-asset decision fields
    op.add_column(
        "decisions", sa.Column("asset_decisions", sa.JSON(), nullable=True), schema="trading"
    )
    op.add_column(
        "decisions", sa.Column("portfolio_rationale", sa.Text(), nullable=True), schema="trading"
    )
    op.add_column(
        "decisions", sa.Column("total_allocation_usd", sa.Float(), nullable=True), schema="trading"
    )
    op.add_column(
        "decisions",
        sa.Column("portfolio_risk_level", sa.String(length=10), nullable=True),
        schema="trading",
    )

    # Make legacy single-asset fields nullable for backward compatibility
    op.alter_column(
        "decisions", "symbol", existing_type=sa.String(length=20), nullable=True, schema="trading"
    )
    op.alter_column(
        "decisions", "action", existing_type=sa.String(length=20), nullable=True, schema="trading"
    )
    op.alter_column(
        "decisions", "allocation_usd", existing_type=sa.Float(), nullable=True, schema="trading"
    )
    op.alter_column(
        "decisions", "exit_plan", existing_type=sa.Text(), nullable=True, schema="trading"
    )
    op.alter_column(
        "decisions", "rationale", existing_type=sa.Text(), nullable=True, schema="trading"
    )
    op.alter_column(
        "decisions", "confidence", existing_type=sa.Float(), nullable=True, schema="trading"
    )
    op.alter_column(
        "decisions",
        "risk_level",
        existing_type=sa.String(length=10),
        nullable=True,
        schema="trading",
    )


def downgrade() -> None:
    """Downgrade schema to remove multi-asset decision support."""
    # Remove multi-asset decision fields
    op.drop_column("decisions", "portfolio_risk_level", schema="trading")
    op.drop_column("decisions", "total_allocation_usd", schema="trading")
    op.drop_column("decisions", "portfolio_rationale", schema="trading")
    op.drop_column("decisions", "asset_decisions", schema="trading")

    # Restore legacy fields to non-nullable (note: this may fail if there are NULL values)
    op.alter_column(
        "decisions", "symbol", existing_type=sa.String(length=20), nullable=False, schema="trading"
    )
    op.alter_column(
        "decisions", "action", existing_type=sa.String(length=20), nullable=False, schema="trading"
    )
    op.alter_column(
        "decisions", "allocation_usd", existing_type=sa.Float(), nullable=False, schema="trading"
    )
    op.alter_column(
        "decisions", "exit_plan", existing_type=sa.Text(), nullable=False, schema="trading"
    )
    op.alter_column(
        "decisions", "rationale", existing_type=sa.Text(), nullable=False, schema="trading"
    )
    op.alter_column(
        "decisions", "confidence", existing_type=sa.Float(), nullable=False, schema="trading"
    )
    op.alter_column(
        "decisions",
        "risk_level",
        existing_type=sa.String(length=10),
        nullable=False,
        schema="trading",
    )
