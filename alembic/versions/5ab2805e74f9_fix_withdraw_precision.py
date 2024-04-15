"""fix withdraw precision

Revision ID: 5ab2805e74f9
Revises: 1faa52019508
Create Date: 2024-04-15 19:59:29.145444

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "5ab2805e74f9"
down_revision: Union[str, None] = "1faa52019508"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "coin_network_exchange",
        "withdraw_precision",
        existing_type=sa.DOUBLE_PRECISION(precision=53),
        type_=sa.Integer(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "coin_network_exchange",
        "withdraw_precision",
        existing_type=sa.Integer(),
        type_=sa.DOUBLE_PRECISION(precision=53),
        existing_nullable=True,
    )
