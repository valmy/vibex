"""Add User and Challenge tables

Revision ID: 002
Revises: 001
Create Date: 2025-10-30 00:00:00.000001

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('address', sa.String(length=42), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=False, default=False),
        sa.PrimaryKeyConstraint('id'),
        schema='trading'
    )
    
    # Create unique index for address
    op.create_index('idx_users_address_unique', 'users', ['address'], unique=True, schema='trading')
    
    # Add user_id column to accounts table
    op.add_column('accounts', 
        sa.Column('user_id', sa.String(), nullable=True), 
        schema='trading'
    )

    # Create challenges table
    op.create_table('challenges',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('address', sa.String(length=42), nullable=False),
        sa.Column('challenge', sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='trading'
    )
    
    # Create index for challenges
    op.create_index('idx_challenges_address', 'challenges', ['address'], schema='trading')
    op.create_index('idx_challenges_challenge_unique', 'challenges', ['challenge'], unique=True, schema='trading')


def downgrade() -> None:
    # Drop challenges table
    op.drop_table('challenges', schema='trading')
    
    # Remove user_id column from accounts table
    op.drop_column('accounts', 'user_id', schema='trading')
    
    # Drop users table
    op.drop_table('users', schema='trading')