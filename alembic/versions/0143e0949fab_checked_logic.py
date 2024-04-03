"""checked logic

Revision ID: 0143e0949fab
Revises: 35d8d232706d
Create Date: 2024-04-03 16:12:17.889118

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0143e0949fab"
down_revision: Union[str, None] = "35d8d232706d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("coin_network_exchange", sa.Column("is_checked", sa.Boolean(), server_default="false", nullable=True))
    op.add_column("coin_network_exchange", sa.Column("checked_at", sa.Date(), nullable=True))
    op.create_index(op.f("ix_coin_network_exchange_checked_at"), "coin_network_exchange", ["checked_at"], unique=False)
    op.create_index(op.f("ix_coin_network_exchange_is_checked"), "coin_network_exchange", ["is_checked"], unique=False)
    op.add_column("profit_bundles", sa.Column("is_checked", sa.Boolean(), server_default="false", nullable=True))


def downgrade() -> None:
    op.drop_column("profit_bundles", "is_checked")
    op.drop_index(op.f("ix_coin_network_exchange_is_checked"), table_name="coin_network_exchange")
    op.drop_index(op.f("ix_coin_network_exchange_checked_at"), table_name="coin_network_exchange")
    op.drop_column("coin_network_exchange", "checked_at")
    op.drop_column("coin_network_exchange", "is_checked")
