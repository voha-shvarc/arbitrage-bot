"""Add buy price snapshot

Revision ID: 9185ce6d2387
Revises: ae33a965192c
Create Date: 2024-02-25 12:45:09.563690

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9185ce6d2387'
down_revision: Union[str, None] = 'ae33a965192c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('profit_bundles', sa.Column('buy_price_snapshot', sa.ARRAY(sa.String(length=50)), nullable=True))


def downgrade() -> None:
    op.drop_column('profit_bundles', 'buy_price_snapshot')
