"""add coins precision

Revision ID: c2475c31a873
Revises: e11449ef5589
Create Date: 2024-03-17 18:02:24.326618

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c2475c31a873"
down_revision: Union[str, None] = "e11449ef5589"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pair_exchanges", sa.Column("base_coin_precision", sa.Integer(), nullable=True))
    op.add_column("pair_exchanges", sa.Column("quote_coin_precision", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("pair_exchanges", "quote_coin_precision")
    op.drop_column("pair_exchanges", "base_coin_precision")
