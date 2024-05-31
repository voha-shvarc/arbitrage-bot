"""add info about additional coins to sell

Revision ID: b386c05a0de5
Revises: 6d3f7affda09
Create Date: 2024-05-31 16:46:38.803270

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b386c05a0de5"
down_revision: Union[str, None] = "6d3f7affda09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "profit_bundles_items", sa.Column("additional_base_ccy_to_sell", sa.Float(), server_default="0", nullable=True)
    )


def downgrade() -> None:
    op.drop_column("profit_bundles_items", "additional_base_ccy_to_sell")
