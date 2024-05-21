"""show how many times bundle already occured

Revision ID: 55df6ec30f00
Revises: 0850430ead2f
Create Date: 2024-05-21 09:33:29.083246

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "55df6ec30f00"
down_revision: Union[str, None] = "0850430ead2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profit_bundles", sa.Column("times_occurred", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("profit_bundles", "times_occurred")
