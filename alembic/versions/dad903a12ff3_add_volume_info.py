"""Add volume info

Revision ID: dad903a12ff3
Revises: b28ba98c76d2
Create Date: 2024-02-07 22:21:08.567661

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "dad903a12ff3"
down_revision: Union[str, None] = "b28ba98c76d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profit_bundles", sa.Column("base_exchange_trading_volume", sa.Float(), nullable=True))
    op.add_column("profit_bundles", sa.Column("pair_exchange_trading_volume", sa.Float(), nullable=True))
    op.add_column("profit_bundles_items", sa.Column("to_use_base_ccy", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("profit_bundles_items", "to_use_base_ccy")
    op.drop_column("profit_bundles", "pair_exchange_trading_volume")
    op.drop_column("profit_bundles", "base_exchange_trading_volume")
