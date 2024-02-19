"""Add prices to report

Revision ID: 8922071c7f9d
Revises: 632c6ec985cf
Create Date: 2024-02-19 15:55:35.084670

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8922071c7f9d'
down_revision: Union[str, None] = '632c6ec985cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('profit_bundles_items', sa.Column('base_exchange_max_price', sa.Float(), server_default='0', nullable=True))
    op.add_column('profit_bundles_items', sa.Column('base_exchange_min_price', sa.Float(), server_default='0', nullable=True))
    op.add_column('profit_bundles_items', sa.Column('pair_exchange_max_price', sa.Float(), server_default='0', nullable=True))
    op.add_column('profit_bundles_items', sa.Column('pair_exchange_min_price', sa.Float(), server_default='0', nullable=True))


def downgrade() -> None:
    op.drop_column('profit_bundles_items', 'pair_exchange_min_price')
    op.drop_column('profit_bundles_items', 'pair_exchange_max_price')
    op.drop_column('profit_bundles_items', 'base_exchange_min_price')
    op.drop_column('profit_bundles_items', 'base_exchange_max_price')
