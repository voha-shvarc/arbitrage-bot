"""Add exhausted option

Revision ID: 632c6ec985cf
Revises: dad903a12ff3
Create Date: 2024-02-14 08:40:48.432831

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '632c6ec985cf'
down_revision: Union[str, None] = 'dad903a12ff3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('profit_bundles_items', sa.Column('is_exhausted', sa.Boolean(), server_default='false', nullable=True))


def downgrade() -> None:
    op.drop_column('profit_bundles_items', 'is_exhausted')
