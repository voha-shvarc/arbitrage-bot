"""add api_enabled, ui_enabled options to pair exchange

Revision ID: 0850430ead2f
Revises: 5ab2805e74f9
Create Date: 2024-04-27 08:26:53.300445

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0850430ead2f"
down_revision: Union[str, None] = "5ab2805e74f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pair_exchanges", sa.Column("api_enabled", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("pair_exchanges", sa.Column("ui_enabled", sa.Boolean(), server_default="true", nullable=False))
    op.create_index(op.f("ix_pair_exchanges_ui_enabled"), "pair_exchanges", ["ui_enabled"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_pair_exchanges_ui_enabled"), table_name="pair_exchanges")
    op.drop_column("pair_exchanges", "ui_enabled")
    op.drop_column("pair_exchanges", "api_enabled")
