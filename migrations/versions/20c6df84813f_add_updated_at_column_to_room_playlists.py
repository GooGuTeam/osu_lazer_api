"""add_updated_at_column_to_room_playlists

Revision ID: 20c6df84813f
Revises: 57bacf936413
Create Date: 2025-08-24 00:08:14.704724

"""
from __future__ import annotations

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20c6df84813f"
down_revision: str | Sequence[str] | None = "57bacf936413"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
