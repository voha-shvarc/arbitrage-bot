"""add network plain name

Revision ID: a55b0db4954a
Revises: 0fec0d5010ab
Create Date: 2024-03-15 12:29:51.328044

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a55b0db4954a"
down_revision: Union[str, None] = "0fec0d5010ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("coin_network_exchange", sa.Column("plain_network_name", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("coin_network_exchange", "plain_network_name")
