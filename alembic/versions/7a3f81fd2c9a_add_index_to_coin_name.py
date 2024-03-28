"""add index to coin name

Revision ID: 7a3f81fd2c9a
Revises: 210ed136af61
Create Date: 2024-03-28 14:04:27.856518

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a3f81fd2c9a'
down_revision: Union[str, None] = '210ed136af61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(op.f('ix_coins_name'), 'coins', ['name'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_coins_name'), table_name='coins')
