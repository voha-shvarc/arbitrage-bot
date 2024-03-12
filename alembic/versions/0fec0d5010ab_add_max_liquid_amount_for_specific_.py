"""Add max liquid amount for specific exchange

Revision ID: 0fec0d5010ab
Revises: 7774d5fe6eb5
Create Date: 2024-03-12 23:43:25.056793

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0fec0d5010ab"
down_revision: Union[str, None] = "7774d5fe6eb5"

branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("exchanges", sa.Column("max_liquid_amount", sa.Integer(), server_default="800", nullable=True))


def downgrade() -> None:
    op.drop_column("exchanges", "max_liquid_amount")
