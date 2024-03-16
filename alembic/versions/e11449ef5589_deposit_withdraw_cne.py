"""Deposit/withdraw cne

Revision ID: e11449ef5589
Revises: a55b0db4954a
Create Date: 2024-03-16 03:15:32.201404

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e11449ef5589"
down_revision: Union[str, None] = "a55b0db4954a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profit_bundles", sa.Column("withdraw_coin_network_exchange_id", sa.Integer(), nullable=True))
    op.add_column("profit_bundles", sa.Column("deposit_coin_network_exchange_id", sa.Integer(), nullable=True))
    op.drop_index("ix_profit_bundles_coin_network_exchange_id", table_name="profit_bundles")
    op.create_index(
        op.f("ix_profit_bundles_deposit_coin_network_exchange_id"),
        "profit_bundles",
        ["deposit_coin_network_exchange_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_profit_bundles_withdraw_coin_network_exchange_id"),
        "profit_bundles",
        ["withdraw_coin_network_exchange_id"],
        unique=False,
    )
    op.drop_constraint("profit_bundles_coin_network_exchange_id_fkey", "profit_bundles", type_="foreignkey")
    op.create_foreign_key(
        None, "profit_bundles", "coin_network_exchange", ["withdraw_coin_network_exchange_id"], ["id"]
    )
    op.create_foreign_key(None, "profit_bundles", "coin_network_exchange", ["deposit_coin_network_exchange_id"], ["id"])
    op.drop_column("profit_bundles", "coin_network_exchange_id")


def downgrade() -> None:
    op.add_column(
        "profit_bundles", sa.Column("coin_network_exchange_id", sa.INTEGER(), autoincrement=False, nullable=True)
    )
    op.drop_constraint(None, "profit_bundles", type_="foreignkey")
    op.drop_constraint(None, "profit_bundles", type_="foreignkey")
    op.create_foreign_key(
        "profit_bundles_coin_network_exchange_id_fkey",
        "profit_bundles",
        "coin_network_exchange",
        ["coin_network_exchange_id"],
        ["id"],
    )
    op.drop_index(op.f("ix_profit_bundles_withdraw_coin_network_exchange_id"), table_name="profit_bundles")
    op.drop_index(op.f("ix_profit_bundles_deposit_coin_network_exchange_id"), table_name="profit_bundles")
    op.create_index(
        "ix_profit_bundles_coin_network_exchange_id", "profit_bundles", ["coin_network_exchange_id"], unique=False
    )
    op.drop_column("profit_bundles", "deposit_coin_network_exchange_id")
    op.drop_column("profit_bundles", "withdraw_coin_network_exchange_id")
