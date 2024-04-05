"""add index

Revision ID: 1faa52019508
Revises: 0143e0949fab
Create Date: 2024-04-04 18:34:40.264518

"""

from typing import Sequence
from typing import Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "1faa52019508"
down_revision: Union[str, None] = "0143e0949fab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(op.f("ix_exchanges_name"), "exchanges", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_exchanges_name"), table_name="exchanges")
