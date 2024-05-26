"""show recent trading volume

Revision ID: 21eb4fafdc13
Revises: 55df6ec30f00
Create Date: 2024-05-26 20:52:50.173014

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "21eb4fafdc13"
down_revision: Union[str, None] = "55df6ec30f00"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profit_bundles", sa.Column("pair_exchange_recent_trading_volume", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("profit_bundles", "pair_exchange_recent_trading_volume")
