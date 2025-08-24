"""add_updated_at_column_to_room_playlists

Revision ID: 7576ca1e056d
Revises: 20c6df84813f
Create Date: 2025-08-24 00:08:42.419252

"""

from __future__ import annotations

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "7576ca1e056d"
down_revision: str | Sequence[str] | None = "20c6df84813f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
