"""add funding_rate to market_data
Revision ID: 1a7275c79921
Revises: e44e20d265c6
Create Date: 2025-11-06 10:51:04.640478
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1a7275c79921'
down_revision: Union[str, Sequence[str], None] = 'e44e20d265c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
def upgrade() -> None:
    """Upgrade schema."""
    # Check if the funding_rate column already exists to avoid errors
    conn = op.get_bind()
    result = conn.execute(
        sa.text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'trading'
            AND table_name = 'market_data'
            AND column_name = 'funding_rate'
        """)
    )
    exists = result.fetchone()
    if not exists:
        # Add funding_rate column to market_data table only if it doesn't exist
        op.add_column('market_data', sa.Column('funding_rate', sa.Float(), nullable=True), schema='trading')
def downgrade() -> None:
    """Downgrade schema."""
    # Remove funding_rate column from market_data table
    # Check if it exists first before dropping
    conn = op.get_bind()
    result = conn.execute(
        sa.text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'trading'
            AND table_name = 'market_data'
            AND column_name = 'funding_rate'
        """)
    )
    exists = result.fetchone()
    if exists:
        op.drop_column('market_data', 'funding_rate', schema='trading')
