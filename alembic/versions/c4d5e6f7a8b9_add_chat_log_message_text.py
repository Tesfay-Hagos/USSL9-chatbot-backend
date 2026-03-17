"""add_chat_log_message_text

Revision ID: c4d5e6f7a8b9
Revises: 7fa335ee9f32
Create Date: 2026-03-11 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = '7fa335ee9f32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add message_text and response_text columns to chat_logs."""
    op.add_column('chat_logs', sa.Column('message_text', sa.Text(), nullable=True))
    op.add_column('chat_logs', sa.Column('response_text', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove message_text and response_text columns from chat_logs."""
    op.drop_column('chat_logs', 'response_text')
    op.drop_column('chat_logs', 'message_text')
