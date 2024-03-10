"""Add active buy/sell on exchanges

Revision ID: 7774d5fe6eb5
Revises: 49b95fa743de
Create Date: 2024-03-10 19:18:51.258213

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7774d5fe6eb5"
down_revision: Union[str, None] = "49b95fa743de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("exchanges", sa.Column("active_buy", sa.Boolean(), server_default="true", nullable=True))
    op.add_column("exchanges", sa.Column("active_sell", sa.Boolean(), server_default="true", nullable=True))


def downgrade() -> None:
    op.drop_column("exchanges", "active_sell")
    op.drop_column("exchanges", "active_buy")
