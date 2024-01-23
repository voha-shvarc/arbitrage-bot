"""Add profit bundle status

Revision ID: ed1cdf5c44af
Revises: 3de7bc179f14
Create Date: 2024-01-20 11:41:04.540091

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ed1cdf5c44af"
down_revision: Union[str, None] = "3de7bc179f14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "profit_bundles", sa.Column("status", sa.String(length=20), server_default="In progress", nullable=True)
    )
    op.create_index(op.f("ix_profit_bundles_status"), "profit_bundles", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_profit_bundles_status"), table_name="profit_bundles")
    op.drop_column("profit_bundles", "status")
