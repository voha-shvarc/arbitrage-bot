"""Add dates for bundle items, add defaults for withdraw_fee

Revision ID: 3de7bc179f14
Revises: 22fd044c4183
Create Date: 2024-01-18 00:25:39.954481

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3de7bc179f14"
down_revision: Union[str, None] = "22fd044c4183"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profit_bundles", sa.Column("synced", sa.Boolean(), server_default="False", nullable=True))
    op.create_index(op.f("ix_profit_bundles_synced"), "profit_bundles", ["synced"], unique=False)

    op.add_column("profit_bundles_items", sa.Column("created_at", sa.DateTime(), nullable=False))
    op.add_column("profit_bundles_items", sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index(op.f("ix_profit_bundles_items_created_at"), "profit_bundles_items", ["created_at"], unique=False)

    op.alter_column("coin_network_exchange", "withdraw_fee", server_default="0")


def downgrade() -> None:
    op.drop_index(op.f("ix_profit_bundles_items_created_at"), table_name="profit_bundles_items")

    op.drop_column("profit_bundles_items", "updated_at")
    op.drop_column("profit_bundles_items", "created_at")

    op.drop_index(op.f("ix_profit_bundles_synced"), table_name="profit_bundles")
    op.drop_column("profit_bundles", "synced")
