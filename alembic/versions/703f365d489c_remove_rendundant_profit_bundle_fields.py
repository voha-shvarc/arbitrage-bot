"""remove rendundant profit bundle fields

Revision ID: 703f365d489c
Revises: e1ce687904e4
Create Date: 2024-03-30 20:46:46.199993

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "703f365d489c"
down_revision: Union[str, None] = "e1ce687904e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("profit_bundles_items", "total_fee")
    op.drop_column("profit_bundles_items", "user_based_total_fee")
    op.drop_column("profit_bundles_items", "user_based_base_profit")
    op.drop_column("profit_bundles_items", "base_profit")


def downgrade() -> None:
    op.add_column(
        "profit_bundles_items",
        sa.Column("base_profit", sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    )
    op.add_column(
        "profit_bundles_items",
        sa.Column(
            "user_based_base_profit",
            sa.DOUBLE_PRECISION(precision=53),
            server_default=sa.text("'0'::double precision"),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "profit_bundles_items",
        sa.Column(
            "user_based_total_fee",
            sa.DOUBLE_PRECISION(precision=53),
            server_default=sa.text("'0'::double precision"),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "profit_bundles_items",
        sa.Column("total_fee", sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    )
