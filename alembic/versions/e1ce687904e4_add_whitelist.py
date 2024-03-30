"""add whitelist

Revision ID: e1ce687904e4
Revises: 7a3f81fd2c9a
Create Date: 2024-03-30 14:47:23.545616

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e1ce687904e4"
down_revision: Union[str, None] = "7a3f81fd2c9a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "whitelist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("withdraw_exchange_id", sa.Integer(), nullable=True),
        sa.Column("deposit_exchange_id", sa.Integer(), nullable=True),
        sa.Column("base_network_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["base_network_id"],
            ["networks.id"],
        ),
        sa.ForeignKeyConstraint(
            ["deposit_exchange_id"],
            ["exchanges.id"],
        ),
        sa.ForeignKeyConstraint(
            ["withdraw_exchange_id"],
            ["exchanges.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_whitelist_base_network_id"), "whitelist", ["base_network_id"], unique=False)
    op.create_index(op.f("ix_whitelist_deposit_exchange_id"), "whitelist", ["deposit_exchange_id"], unique=False)
    op.create_index(op.f("ix_whitelist_withdraw_exchange_id"), "whitelist", ["withdraw_exchange_id"], unique=False)
    op.add_column("profit_bundles", sa.Column("is_whitelisted", sa.Boolean(), server_default="False", nullable=True))


def downgrade() -> None:
    op.drop_column("profit_bundles", "is_whitelisted")
    op.drop_index(op.f("ix_whitelist_withdraw_exchange_id"), table_name="whitelist")
    op.drop_index(op.f("ix_whitelist_deposit_exchange_id"), table_name="whitelist")
    op.drop_index(op.f("ix_whitelist_base_network_id"), table_name="whitelist")
    op.drop_table("whitelist")
