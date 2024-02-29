"""Add network speed just to bundle

Revision ID: 6551372c294a
Revises: 8312f44e367a
Create Date: 2024-02-29 20:53:16.297857

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6551372c294a'
down_revision: Union[str, None] = '8312f44e367a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('profit_bundles', sa.Column('network_speed', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('profit_bundles', 'network_speed')

