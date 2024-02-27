"""Add extra_info to coin network exchange

Revision ID: 5be367364c4d
Revises: 9185ce6d2387
Create Date: 2024-02-27 09:30:32.967222

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5be367364c4d'
down_revision: Union[str, None] = '9185ce6d2387'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('coin_network_exchange', sa.Column('extra_info', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False))


def downgrade() -> None:
    op.drop_column('coin_network_exchange', 'extra_info')
