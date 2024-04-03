"""add back way network fee

Revision ID: 35d8d232706d
Revises: 7f3942501ea1
Create Date: 2024-04-03 13:57:34.303140

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "35d8d232706d"
down_revision: Union[str, None] = "7f3942501ea1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profit_bundles", sa.Column("back_way_network_fee", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("profit_bundles", "back_way_network_fee")
