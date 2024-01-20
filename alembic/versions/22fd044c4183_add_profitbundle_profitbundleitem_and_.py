"""Add ProfitBundle, ProfitBundleItem and indexes

Revision ID: 22fd044c4183
Revises: 731e0dd7832a
Create Date: 2024-01-17 15:46:20.654169

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '22fd044c4183'
down_revision: Union[str, None] = '731e0dd7832a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('profit_bundles',
sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pair_id', sa.Integer(), nullable=True),
        sa.Column('coin_network_exchange_id', sa.Integer(), nullable=True),
        sa.Column('base_exchange_id', sa.Integer(), nullable=True),
        sa.Column('pair_exchange_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['base_exchange_id'], ['exchanges.id'], ),
        sa.ForeignKeyConstraint(['coin_network_exchange_id'], ['coin_network_exchange.id'], ),
        sa.ForeignKeyConstraint(['pair_exchange_id'], ['exchanges.id'], ),
        sa.ForeignKeyConstraint(['pair_id'], ['pairs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index(op.f('ix_profit_bundles_base_exchange_id'), 'profit_bundles', ['base_exchange_id'], unique=False)
    op.create_index(op.f('ix_profit_bundles_coin_network_exchange_id'), 'profit_bundles', ['coin_network_exchange_id'], unique=False)
    op.create_index(op.f('ix_profit_bundles_created_at'), 'profit_bundles', ['created_at'], unique=False)
    op.create_index(op.f('ix_profit_bundles_pair_exchange_id'), 'profit_bundles', ['pair_exchange_id'], unique=False)
    op.create_index(op.f('ix_profit_bundles_pair_id'), 'profit_bundles', ['pair_id'], unique=False)

    op.create_table('profit_bundles_items',
sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profit_bundle_id', sa.Integer(), nullable=True),
        sa.Column('to_use_usdt', sa.Float(), nullable=True),
        sa.Column('avg_spread', sa.Float(), nullable=True),
        sa.Column('base_profit', sa.Float(), nullable=True),
        sa.Column('total_fee', sa.Float(), nullable=True),
        sa.Column('profit', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['profit_bundle_id'], ['profit_bundles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_coin_network_exchange_can_deposit'), 'coin_network_exchange', ['can_deposit'], unique=False)
    op.create_index(op.f('ix_coin_network_exchange_can_withdraw'), 'coin_network_exchange', ['can_withdraw'], unique=False)
    op.create_index(op.f('ix_coin_network_exchange_coin_id'), 'coin_network_exchange', ['coin_id'], unique=False)
    op.create_index(op.f('ix_coin_network_exchange_exchange_id'), 'coin_network_exchange', ['exchange_id'], unique=False)
    op.create_index(op.f('ix_coin_network_exchange_network_id'), 'coin_network_exchange', ['network_id'], unique=False)

    op.create_index(op.f('ix_pair_exchanges_exchange_id'), 'pair_exchanges', ['exchange_id'], unique=False)
    op.create_index(op.f('ix_pair_exchanges_pair_id'), 'pair_exchanges', ['pair_id'], unique=False)

    op.create_index(op.f('ix_pairs_base_coin_id'), 'pairs', ['base_coin_id'], unique=False)
    op.create_index(op.f('ix_pairs_quote_coin_id'), 'pairs', ['quote_coin_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_pairs_quote_coin_id'), table_name='pairs')
    op.drop_index(op.f('ix_pairs_base_coin_id'), table_name='pairs')

    op.drop_index(op.f('ix_pair_exchanges_pair_id'), table_name='pair_exchanges')
    op.drop_index(op.f('ix_pair_exchanges_exchange_id'), table_name='pair_exchanges')

    op.drop_index(op.f('ix_coin_network_exchange_network_id'), table_name='coin_network_exchange')
    op.drop_index(op.f('ix_coin_network_exchange_exchange_id'), table_name='coin_network_exchange')
    op.drop_index(op.f('ix_coin_network_exchange_coin_id'), table_name='coin_network_exchange')
    op.drop_index(op.f('ix_coin_network_exchange_can_withdraw'), table_name='coin_network_exchange')
    op.drop_index(op.f('ix_coin_network_exchange_can_deposit'), table_name='coin_network_exchange')

    op.drop_table('profit_bundles_items')

    op.drop_index(op.f('ix_profit_bundles_pair_id'), table_name='profit_bundles')
    op.drop_index(op.f('ix_profit_bundles_pair_exchange_id'), table_name='profit_bundles')
    op.drop_index(op.f('ix_profit_bundles_created_at'), table_name='profit_bundles')
    op.drop_index(op.f('ix_profit_bundles_coin_network_exchange_id'), table_name='profit_bundles')
    op.drop_index(op.f('ix_profit_bundles_base_exchange_id'), table_name='profit_bundles')
    op.drop_table('profit_bundles')
