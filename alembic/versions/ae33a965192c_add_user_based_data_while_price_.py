"""Add user based data while price analyzing

Revision ID: ae33a965192c
Revises: 2554501cdea3
Create Date: 2024-02-22 09:37:44.425105

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ae33a965192c'
down_revision: Union[str, None] = '2554501cdea3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('profit_bundles_items', sa.Column('user_based_to_use_usdt', sa.Float(), server_default='0', nullable=True))
    op.add_column('profit_bundles_items', sa.Column('user_based_to_use_base_ccy', sa.Float(), server_default='0', nullable=True))
    op.add_column('profit_bundles_items', sa.Column('user_based_avg_spread', sa.Float(), server_default='0', nullable=True))
    op.add_column('profit_bundles_items', sa.Column('user_based_base_profit', sa.Float(), server_default='0', nullable=True))
    op.add_column('profit_bundles_items', sa.Column('user_based_total_fee', sa.Float(), server_default='0', nullable=True))
    op.add_column('profit_bundles_items', sa.Column('user_based_spot_fee', sa.Float(), server_default='0', nullable=True))
    op.add_column('profit_bundles_items', sa.Column('user_based_network_fee', sa.Float(), server_default='0', nullable=True))
    op.add_column('profit_bundles_items', sa.Column('user_based_profit', sa.Float(), server_default='0', nullable=True))
    op.add_column('profit_bundles_items', sa.Column('user_based_base_exchange_max_price', sa.Float(), server_default='0', nullable=True))
    op.add_column('profit_bundles_items', sa.Column('user_based_base_exchange_min_price', sa.Float(), server_default='0', nullable=True))
    op.add_column('profit_bundles_items', sa.Column('user_based_pair_exchange_max_price', sa.Float(), server_default='0', nullable=True))
    op.add_column('profit_bundles_items', sa.Column('user_based_pair_exchange_min_price', sa.Float(), server_default='0', nullable=True))
    op.add_column('profit_bundles_items', sa.Column('user_based_used_buy_orders', sa.Integer(), server_default='0', nullable=True))
    op.add_column('profit_bundles_items', sa.Column('user_based_used_sell_orders', sa.Integer(), server_default='0', nullable=True))


def downgrade() -> None:
    op.drop_column('profit_bundles_items', 'user_based_used_sell_orders')
    op.drop_column('profit_bundles_items', 'user_based_used_buy_orders')
    op.drop_column('profit_bundles_items', 'user_based_pair_exchange_min_price')
    op.drop_column('profit_bundles_items', 'user_based_pair_exchange_max_price')
    op.drop_column('profit_bundles_items', 'user_based_base_exchange_min_price')
    op.drop_column('profit_bundles_items', 'user_based_base_exchange_max_price')
    op.drop_column('profit_bundles_items', 'user_based_profit')
    op.drop_column('profit_bundles_items', 'user_based_network_fee')
    op.drop_column('profit_bundles_items', 'user_based_spot_fee')
    op.drop_column('profit_bundles_items', 'user_based_total_fee')
    op.drop_column('profit_bundles_items', 'user_based_base_profit')
    op.drop_column('profit_bundles_items', 'user_based_avg_spread')
    op.drop_column('profit_bundles_items', 'user_based_to_use_base_ccy')
    op.drop_column('profit_bundles_items', 'user_based_to_use_usdt')
