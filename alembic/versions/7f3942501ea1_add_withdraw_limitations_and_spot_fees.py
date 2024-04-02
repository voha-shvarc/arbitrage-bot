"""add withdraw limitations and spot fees

Revision ID: 7f3942501ea1
Revises: f719b18d3b60
Create Date: 2024-04-02 13:06:13.552035

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7f3942501ea1"
down_revision: Union[str, None] = "f719b18d3b60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("coin_network_exchange", sa.Column("withdraw_min", sa.Float(), nullable=True))
    op.add_column("coin_network_exchange", sa.Column("withdraw_max", sa.Float(), nullable=True))
    op.add_column("coin_network_exchange", sa.Column("deposit_min", sa.Float(), nullable=True))
    op.add_column("coin_network_exchange", sa.Column("withdraw_precision", sa.Float(), nullable=True))
    op.add_column("pair_exchanges", sa.Column("maker_fee", sa.Float(), server_default="0.001", nullable=True))
    op.add_column("pair_exchanges", sa.Column("taker_fee", sa.Float(), server_default="0.001", nullable=True))
    op.add_column("profit_bundles", sa.Column("bought_ccy_quantity", sa.Float(), server_default="0", nullable=True))
    op.add_column("profit_bundles", sa.Column("spot_buy_fee", sa.Float(), server_default="0.001", nullable=True))
    op.add_column("profit_bundles", sa.Column("spot_sell_fee", sa.Float(), server_default="0.001", nullable=True))


def downgrade() -> None:
    op.drop_column("profit_bundles", "spot_sell_fee")
    op.drop_column("profit_bundles", "spot_buy_fee")
    op.drop_column("profit_bundles", "bought_ccy_quantity")
    op.drop_column("pair_exchanges", "taker_fee")
    op.drop_column("pair_exchanges", "maker_fee")
    op.drop_column("coin_network_exchange", "withdraw_precision")
    op.drop_column("coin_network_exchange", "deposit_min")
    op.drop_column("coin_network_exchange", "withdraw_max")
    op.drop_column("coin_network_exchange", "withdraw_min")
