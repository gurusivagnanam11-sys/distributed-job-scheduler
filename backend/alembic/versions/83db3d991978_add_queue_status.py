"""add queue status

Revision ID: 83db3d991978
Revises: bea964c6587f
Create Date: 2026-08-19 19:11:58.116323

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '83db3d991978'
down_revision: Union[str, Sequence[str], None] = 'bea964c6587f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create ENUM type first
    queue_status = sa.Enum('active', 'paused', name='queue_status')
    queue_status.create(op.get_bind(), checkfirst=True)
    
    # Add column with server_default to avoid breaking existing rows
    op.add_column('queues', sa.Column('status', queue_status, nullable=False, server_default='active'))
    op.create_index(op.f('ix_queues_status'), 'queues', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_queues_status'), table_name='queues')
    op.drop_column('queues', 'status')
    
    # Drop ENUM type
    queue_status = sa.Enum('active', 'paused', name='queue_status')
    queue_status.drop(op.get_bind(), checkfirst=True)
