"""Add cross-platform ID columns to tracks table.

Revision ID: 004
Revises: 003
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tracks",
        sa.Column("shazam_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "tracks",
        sa.Column("tiktok_sound_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "tracks",
        sa.Column("billboard_id", sa.String(200), nullable=True),
    )
    op.add_column(
        "tracks",
        sa.Column("chartmetric_id", sa.Integer(), nullable=True),
    )

    # Make apple_music_id unique + indexed (was not before)
    op.create_index("ix_tracks_apple_music_id", "tracks", ["apple_music_id"], unique=True)
    op.create_index("ix_tracks_shazam_id", "tracks", ["shazam_id"], unique=True)
    op.create_index("ix_tracks_tiktok_sound_id", "tracks", ["tiktok_sound_id"], unique=True)
    op.create_index("ix_tracks_billboard_id", "tracks", ["billboard_id"], unique=True)
    op.create_index("ix_tracks_chartmetric_id", "tracks", ["chartmetric_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_tracks_chartmetric_id", table_name="tracks")
    op.drop_index("ix_tracks_billboard_id", table_name="tracks")
    op.drop_index("ix_tracks_tiktok_sound_id", table_name="tracks")
    op.drop_index("ix_tracks_shazam_id", table_name="tracks")
    op.drop_index("ix_tracks_apple_music_id", table_name="tracks")

    op.drop_column("tracks", "chartmetric_id")
    op.drop_column("tracks", "billboard_id")
    op.drop_column("tracks", "tiktok_sound_id")
    op.drop_column("tracks", "shazam_id")
