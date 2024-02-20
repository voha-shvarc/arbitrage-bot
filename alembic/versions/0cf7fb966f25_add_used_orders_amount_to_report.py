"""Add used orders amount to report

Revision ID: 0cf7fb966f25
Revises: 8922071c7f9d
Create Date: 2024-02-20 09:44:29.851410

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0cf7fb966f25'
down_revision: Union[str, None] = '8922071c7f9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('profit_bundles_items', sa.Column('used_buy_orders', sa.Integer(), server_default='0', nullable=True))
    op.add_column('profit_bundles_items', sa.Column('used_sell_orders', sa.Integer(), server_default='0', nullable=True))


def downgrade() -> None:
    op.drop_column('profit_bundles_items', 'used_sell_orders')
    op.drop_column('profit_bundles_items', 'used_buy_orders')
