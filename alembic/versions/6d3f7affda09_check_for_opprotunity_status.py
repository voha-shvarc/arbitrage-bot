"""check for opprotunity status

Revision ID: 6d3f7affda09
Revises: 21eb4fafdc13
Create Date: 2024-05-30 13:19:07.028616

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "6d3f7affda09"
down_revision: Union[str, None] = "21eb4fafdc13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "profit_bundles",
        sa.Column("opportunity_status", sa.String(length=20), server_default="Equal Opportunity", nullable=True),
    )


def downgrade() -> None:
    op.drop_column("profit_bundles", "opportunity_status")
