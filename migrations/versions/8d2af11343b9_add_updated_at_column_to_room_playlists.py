"""add_updated_at_column_to_room_playlists

Revision ID: 8d2af11343b9
Revises: 7576ca1e056d
Create Date: 2025-08-24 00:11:05.064099

"""
from __future__ import annotations

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "8d2af11343b9"
down_revision: str | Sequence[str] | None = "7576ca1e056d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
