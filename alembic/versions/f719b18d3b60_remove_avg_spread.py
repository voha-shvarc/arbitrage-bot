"""remove avg_spread

Revision ID: f719b18d3b60
Revises: 703f365d489c
Create Date: 2024-03-31 12:18:26.266343

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f719b18d3b60"
down_revision: Union[str, None] = "703f365d489c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("profit_bundles_items", "user_based_avg_spread")
    op.drop_column("profit_bundles_items", "avg_spread")


def downgrade() -> None:
    op.add_column(
        "profit_bundles_items",
        sa.Column("avg_spread", sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    )
    op.add_column(
        "profit_bundles_items",
        sa.Column(
            "user_based_avg_spread",
            sa.DOUBLE_PRECISION(precision=53),
            server_default=sa.text("'0'::double precision"),
            autoincrement=False,
            nullable=True,
        ),
    )
