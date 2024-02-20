"""Split network fee and spot fee

Revision ID: 2554501cdea3
Revises: 0cf7fb966f25
Create Date: 2024-02-20 09:55:38.012889

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2554501cdea3'
down_revision: Union[str, None] = '0cf7fb966f25'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('profit_bundles_items', sa.Column('spot_fee', sa.Float(), server_default='0', nullable=True))
    op.add_column('profit_bundles_items', sa.Column('network_fee', sa.Float(), server_default='0', nullable=True))


def downgrade() -> None:
    op.drop_column('profit_bundles_items', 'network_fee')
    op.drop_column('profit_bundles_items', 'spot_fee')
