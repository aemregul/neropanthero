"""rename creative_plugins to presets

Revision ID: f1a2b3c4d5e6
Revises: e7d6586949da
Create Date: 2026-03-12 18:55:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e7d6586949da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tabloyu yeniden adlandır
    op.rename_table('creative_plugins', 'presets')


def downgrade() -> None:
    op.rename_table('presets', 'creative_plugins')
