"""add_is_public_to_store_registry

Revision ID: 7fa335ee9f32
Revises: a1b2c3d4e5f6
Create Date: 2026-03-02 15:15:22.111525

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7fa335ee9f32'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'store_registry',
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('store_registry', 'is_public')


