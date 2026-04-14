"""Retune chartmetric_endpoint_config targets for 90% saturation.

Revision ID: 031
Revises: 030
Create Date: 2026-04-14

Stage 3 Phase D: the initial Phase B/C1 seed rows used conservative
target_interval_hours (24-72h). That produced a per-day emission
ceiling below the fetcher's drain rate once entity counts dropped
below ~6,500 (entity, endpoint) pairs — starving the queue and
leaving the 90%-of-quota bucket underfilled.

New targets (this migration UPSERTs them onto existing rows):

  track_stat_spotify     2h     weight 1.0
  track_stat_tiktok      2h     weight 1.0
  track_stat_shazam      6h     weight 0.8
  artist_stat_spotify    6h     weight 1.0
  artist_stat_instagram  12h    weight 0.9
  artist_stat_tiktok     6h     weight 1.0
  artist_stat_youtube    12h    weight 1.0
  artist_stat_twitter    24h    weight 0.6
  artist_stat_shazam     12h    weight 0.8

Rationale (see chartmetric_ingest/endpoints.py docstring for long
form): at 2h on the two highest-volume track endpoints, every track
with a chartmetric_id generates 12 jobs/day per platform. With even
a modest catalog (~1,000 tracks) that's 24,000 jobs/day on spotify
+ tiktok alone — well over the 155,520/day drain threshold the
fetcher's 1.8 req/s token bucket imposes.

Operators who tuned any of these rows manually after Phase C1 will
have their edits clobbered by this upgrade. Acceptable — the
defaults are the only tunings in place at Phase C1 ship time, this
migration lands in the same session, and a runtime override via the
admin API is always available after the upgrade.
"""
from alembic import op


revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


NEW_TARGETS = [
    ("track_stat_spotify",    2.0,  1.0),
    ("track_stat_tiktok",     2.0,  1.0),
    ("track_stat_shazam",     6.0,  0.8),
    ("artist_stat_spotify",   6.0,  1.0),
    ("artist_stat_instagram", 12.0, 0.9),
    ("artist_stat_tiktok",    6.0,  1.0),
    ("artist_stat_youtube",   12.0, 1.0),
    ("artist_stat_twitter",   24.0, 0.6),
    ("artist_stat_shazam",    12.0, 0.8),
]


def upgrade() -> None:
    for key, interval, weight in NEW_TARGETS:
        op.execute(f"""
            INSERT INTO chartmetric_endpoint_config
                (endpoint_key, target_interval_hours, priority_weight, enabled, notes)
            VALUES
                ('{key}', {interval}, {weight}, true,
                 'Retuned by migration 031 for 90% saturation')
            ON CONFLICT (endpoint_key) DO UPDATE SET
                target_interval_hours = EXCLUDED.target_interval_hours,
                priority_weight = EXCLUDED.priority_weight,
                enabled = true,
                updated_at = now()
        """)


def downgrade() -> None:
    # Restore the Phase C1 defaults (24-72h).
    for key, interval, weight in [
        ("track_stat_spotify",    24.0, 1.0),
        ("track_stat_tiktok",     24.0, 1.0),
        ("track_stat_shazam",     24.0, 0.8),
        ("artist_stat_spotify",   48.0, 1.0),
        ("artist_stat_instagram", 48.0, 0.9),
        ("artist_stat_tiktok",    48.0, 1.0),
        ("artist_stat_youtube",   48.0, 1.0),
        ("artist_stat_twitter",   72.0, 0.6),
        ("artist_stat_shazam",    48.0, 0.8),
    ]:
        op.execute(f"""
            UPDATE chartmetric_endpoint_config
            SET target_interval_hours = {interval},
                priority_weight = {weight},
                updated_at = now()
            WHERE endpoint_key = '{key}'
        """)
