"""add index to profit_bundle_item

Revision ID: 210ed136af61
Revises: c2475c31a873
Create Date: 2024-03-28 13:41:54.503782

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '210ed136af61'
down_revision: Union[str, None] = 'c2475c31a873'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(op.f('ix_profit_bundles_items_profit_bundle_id'), 'profit_bundles_items', ['profit_bundle_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_profit_bundles_items_profit_bundle_id'), table_name='profit_bundles_items')
