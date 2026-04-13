"""Song stem extraction pipeline tables

Revision ID: 024
Revises: 023
Create Date: 2026-04-13

Two tables powering the vocal-stem-mix pipeline (Option A2 — stem
extractor microservice on Railway via Demucs):

  song_stem_jobs — the work queue. One row per song that needs its
    Suno output split into stems and mixed back onto the original
    instrumental. Claim pattern: SELECT FOR UPDATE SKIP LOCKED so
    parallel stem-extractor workers don't claim the same job.

  song_stems — the output artifacts. Multiple rows per song, one
    per stem_type:
      suno_original  — the full Suno add-vocals output (pristine)
      vocals_only    — Demucs-separated vocal stem
      final_mixed    — ffmpeg mix of vocals_only over the original
                       user-uploaded instrumental (THIS is the
                       track the UI plays by default)
      drums / bass / other — Demucs extras, stored for future remix
                              or stem-submission flows

Storage: inline BYTEA. Same pattern as instrumental_blobs + music_
generation_audio. Stems are typically 1-3 MB each, Postgres handles
them fine at our scale.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "song_stem_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "song_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("songs_master.song_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "music_generation_call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("music_generation_calls.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "source_instrumental_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("instrumentals.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_audio_url", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("worker_id", sa.Text, nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("params_json", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_song_stem_jobs_status",
        "song_stem_jobs",
        "status IN ('pending','in_progress','done','failed')",
    )
    op.create_index(
        "ix_song_stem_jobs_status",
        "song_stem_jobs",
        ["status"],
    )
    op.create_index(
        "ix_song_stem_jobs_song_id",
        "song_stem_jobs",
        ["song_id"],
    )

    op.create_table(
        "song_stems",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "song_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("songs_master.song_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("song_stem_jobs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("stem_type", sa.Text, nullable=False),
        sa.Column(
            "content_type",
            sa.String(50),
            nullable=False,
            server_default="audio/mpeg",
        ),
        sa.Column("audio_bytes", postgresql.BYTEA, nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column("loudness_lufs", sa.Float, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_song_stems_type",
        "song_stems",
        "stem_type IN ('suno_original','vocals_only','final_mixed','drums','bass','other')",
    )
    op.create_index(
        "ix_song_stems_song_id",
        "song_stems",
        ["song_id"],
    )
    op.create_unique_constraint(
        "uq_song_stems_song_stem_type",
        "song_stems",
        ["song_id", "stem_type"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_song_stems_song_stem_type", "song_stems", type_="unique")
    op.drop_index("ix_song_stems_song_id", table_name="song_stems")
    op.drop_constraint("ck_song_stems_type", "song_stems", type_="check")
    op.drop_table("song_stems")
    op.drop_index("ix_song_stem_jobs_song_id", table_name="song_stem_jobs")
    op.drop_index("ix_song_stem_jobs_status", table_name="song_stem_jobs")
    op.drop_constraint("ck_song_stem_jobs_status", "song_stem_jobs", type_="check")
    op.drop_table("song_stem_jobs")
