"""Instrumental analysis cache + stem job types + entry-point lock.

Revision ID: 025
Revises: 024
Create Date: 2026-04-13

Adds the columns needed for the instrumental-analysis cache and the
vocal-entry-point alignment pipeline:

  instrumentals.vocal_entry_seconds FLOAT NULL
      Where verse 1 should begin in this instrumental, in seconds from
      t=0. Populated by the stem-extractor worker on first use via a
      librosa/agglomerative-segmentation + spectral-flatness heuristic,
      and overwriteable by the CEO via the Songs-page "Nudge vocal
      entry" control when the auto-detect is off.

  instrumentals.vocal_entry_source TEXT NULL
      'auto' (worker-detected) | 'manual' (CEO-edited). Lets us show
      a confidence badge in the UI and skip re-detection on manual
      values even if the cache is otherwise expired.

  instrumentals.analysis_json JSONB NULL
      Blob for everything else the worker measures on first touch:
      {detected_bpm, detected_key, detected_duration_seconds,
       spectral_flatness_peaks, section_boundaries, ...}.
      Kept as JSONB rather than per-field columns because the set of
      measured features will evolve.

  instrumentals.analyzed_at TIMESTAMPTZ NULL
      Cache marker. If NULL, the worker runs the full librosa analysis
      pass on first use and populates the three columns above. If NOT
      NULL, the worker reuses the cached values and skips librosa on
      the instrumental side entirely. Cuts per-job librosa time ~50%.

  song_stem_jobs.job_type TEXT NOT NULL DEFAULT 'full'
      'full'         — normal pipeline: download → tempo-lock → Demucs
                       → entry-point-lock → ffmpeg mix → ack
      'remix_only'   — skip Demucs and reuse the cached vocals_only
                       stem from song_stems. Used when the CEO nudges
                       the vocal entry point and we need to re-mix in
                       <10 s instead of re-running Demucs for 15 min.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- instrumentals: analysis cache + vocal entry -----------------
    op.add_column(
        "instrumentals",
        sa.Column("vocal_entry_seconds", sa.Float, nullable=True),
    )
    op.add_column(
        "instrumentals",
        sa.Column("vocal_entry_source", sa.Text, nullable=True),
    )
    op.add_column(
        "instrumentals",
        sa.Column(
            "analysis_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "instrumentals",
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_instrumentals_vocal_entry_source",
        "instrumentals",
        "vocal_entry_source IS NULL OR vocal_entry_source IN ('auto', 'manual')",
    )

    # --- song_stem_jobs: job type ------------------------------------
    op.add_column(
        "song_stem_jobs",
        sa.Column(
            "job_type",
            sa.Text,
            nullable=False,
            server_default=sa.text("'full'"),
        ),
    )
    op.create_check_constraint(
        "ck_song_stem_jobs_job_type",
        "song_stem_jobs",
        "job_type IN ('full', 'remix_only')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_song_stem_jobs_job_type", "song_stem_jobs", type_="check")
    op.drop_column("song_stem_jobs", "job_type")
    op.drop_constraint(
        "ck_instrumentals_vocal_entry_source", "instrumentals", type_="check"
    )
    op.drop_column("instrumentals", "analyzed_at")
    op.drop_column("instrumentals", "analysis_json")
    op.drop_column("instrumentals", "vocal_entry_source")
    op.drop_column("instrumentals", "vocal_entry_seconds")
