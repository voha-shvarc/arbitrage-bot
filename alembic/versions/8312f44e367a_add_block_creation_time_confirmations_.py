"""Add block_creation_time, confirmations needed

Revision ID: 8312f44e367a
Revises: 5be367364c4d
Create Date: 2024-02-28 22:34:18.518859

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8312f44e367a'
down_revision: Union[str, None] = '5be367364c4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('coin_network_exchange', sa.Column('confirmations_needed', sa.Integer(), nullable=True))
    op.drop_column('coin_network_exchange', 'arrival_time')
    op.add_column('networks', sa.Column('block_creation_time', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('networks', 'block_creation_time')
    op.add_column('coin_network_exchange', sa.Column('arrival_time', sa.INTEGER(), autoincrement=False, nullable=True))
    op.drop_column('coin_network_exchange', 'confirmations_needed')
