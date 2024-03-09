"""Add bundle chart change

Revision ID: 49b95fa743de
Revises: 6551372c294a
Create Date: 2024-03-09 07:28:17.653836

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "49b95fa743de"
down_revision: Union[str, None] = "6551372c294a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profit_bundles", sa.Column("base_exchange_chart_change", sa.Float(), nullable=True))
    op.add_column("profit_bundles", sa.Column("pair_exchange_chart_change", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("profit_bundles", "pair_exchange_chart_change")
    op.drop_column("profit_bundles", "base_exchange_chart_change")
