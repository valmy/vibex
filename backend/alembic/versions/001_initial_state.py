"""Initial state - existing tables

Revision ID: 001
Revises: 
Create Date: 2025-10-30 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create schema if not exists
    op.execute("CREATE SCHEMA IF NOT EXISTS trading")

    # This migration acknowledges existing tables that were created via init-db.sql
    # No changes are needed as they are already in the database
    pass


def downgrade() -> None:
    # Do not drop existing tables as they have data
    pass