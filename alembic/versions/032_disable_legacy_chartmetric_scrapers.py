"""Disable remaining legacy Chartmetric APScheduler scrapers.

Revision ID: 032
Revises: 031
Create Date: 2026-04-14

Stage 3 Phase D saturation handoff: the chartmetric_ingest fetcher
now runs live at 1.8 req/s = 90% of the Chartmetric 2 req/s quota.
Any legacy scraper that still hits Chartmetric through APScheduler
would contend with the fetcher for the shared token bucket —
pushing the combined request rate over 2 req/s and triggering 429s.

The fetcher is the canonical API consumer from this point on.
Legacy scrapers that have not yet been migrated to the planner/
handler pattern are disabled at the config level until their
migration lands. Their code stays in the tree so nothing imports
break; nothing wakes up to run them.

Scrapers disabled by this migration:
    chartmetric                     (core charts)
    chartmetric_deep_us             (endpoint matrix)
    chartmetric_historical_replay   (Stage 2A backfill)
    chartmetric_artist_tracks       (per-artist catalog crawl)
    chartmetric_playlist_crawler
    chartmetric_us_cities
    chartmetric_artists             (artist discovery)
    chartmetric_velocity_pulse
    chartmetric_audio_features

Already disabled by earlier migrations (for reference):
    chartmetric_track_history  (028)
    chartmetric_artist_stats   (030)

The chart_sweep planner replaces the same work the deep_us and
chart-facing legacy scrapers were producing. The historical replay
scraper's window-rotation backfill work is queued for a Phase C
migration and can be re-enabled selectively via admin API once the
new pipeline has demonstrated saturation at 90%.
"""
from alembic import op


revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


LEGACY_SCRAPERS = [
    "chartmetric",
    "chartmetric_deep_us",
    "chartmetric_historical_replay",
    "chartmetric_artist_tracks",
    "chartmetric_playlist_crawler",
    "chartmetric_us_cities",
    "chartmetric_artists",
    "chartmetric_velocity_pulse",
    "chartmetric_audio_features",
]


def upgrade() -> None:
    for scraper_id in LEGACY_SCRAPERS:
        op.execute(f"""
            UPDATE scraper_configs
            SET enabled = false
            WHERE id = '{scraper_id}'
              AND enabled = true
        """)


def downgrade() -> None:
    for scraper_id in LEGACY_SCRAPERS:
        op.execute(f"""
            UPDATE scraper_configs
            SET enabled = true
            WHERE id = '{scraper_id}'
        """)
