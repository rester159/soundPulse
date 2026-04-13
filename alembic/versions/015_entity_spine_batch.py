"""Batch: remaining §17 entity tables (T-101..T-112)

Revision ID: 015
Revises: 014
Create Date: 2026-04-12

13 tables covering the rest of the §17 canonical entity model:
reference_artists, artist_visual_assets, artist_voice_state, releases,
release_track_record, audio_assets, song_qa_reports, song_submissions,
royalty_registrations, marketing_campaigns, social_accounts,
social_posts, revenue_events.

Also adds the deferred FKs on songs_master that were left as bare UUIDs
in migration 014 (release_id, qa_report_id, primary_artwork_asset_id).

Dependency order: reference_artists → artist_visual_assets →
artist_voice_state → releases → audio_assets → song_qa_reports →
release_track_record → song_submissions → royalty_registrations →
marketing_campaigns → social_accounts → social_posts → revenue_events.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # reference_artists (§19 research) ----------------------------------
    op.create_table(
        "reference_artists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("chartmetric_id", sa.BigInteger, nullable=True),
        sa.Column("spotify_id", sa.String(40), nullable=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("primary_genre", sa.String(100)),
        sa.Column("adjacent_genres", postgresql.ARRAY(sa.Text)),
        sa.Column("factual", postgresql.JSONB),          # age, nationality, languages, etc
        sa.Column("visual_signals", postgresql.JSONB),   # face/body/hair/fashion/palette
        sa.Column("voice_signals", postgresql.JSONB),    # timbre/range/delivery from analysis
        sa.Column("lyrical_signals", postgresql.JSONB),  # theme extraction
        sa.Column("social_signals", postgresql.JSONB),   # post tone, engagement style
        sa.Column("confidence_report", postgresql.JSONB),
        sa.Column("image_urls", postgresql.ARRAY(sa.Text)),
        sa.Column("top_track_urls", postgresql.ARRAY(sa.Text)),
        sa.Column("momentum_window_start", sa.Date),
        sa.Column("momentum_window_end", sa.Date),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_reference_artists_primary_genre", "reference_artists", ["primary_genre"])

    # artist_visual_assets (§20) -----------------------------------------
    op.create_table(
        "artist_visual_assets",
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ai_artists.artist_id"), nullable=False),
        sa.Column("asset_type", sa.String(40), nullable=False),
        # reference_sheet | sheet_view | song_artwork | promo | avatar | behind_scenes
        sa.Column("view_angle", sa.String(40)),
        # front | side_l | side_r | back | top_l | top_r | bottom_l | bottom_r | N/A
        sa.Column("parent_sheet_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("storage_url", sa.Text, nullable=False),
        sa.Column("storage_checksum", sa.String(80)),
        sa.Column("width", sa.Integer),
        sa.Column("height", sa.Integer),
        sa.Column("generation_provider", sa.String(40)),
        sa.Column("generation_params", postgresql.JSONB),
        sa.Column("source_prompt", sa.Text),
        sa.Column("embedding", postgresql.JSONB),  # serialized vector for consistency check
        sa.Column("consistency_score", sa.Float),
        sa.Column("is_canonical_sheet", sa.Boolean, server_default="FALSE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_visual_assets_artist", "artist_visual_assets", ["artist_id"])
    op.create_index("idx_visual_assets_type", "artist_visual_assets", ["asset_type"])

    # artist_voice_state (§21 two-phase rule) ----------------------------
    op.create_table(
        "artist_voice_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ai_artists.artist_id"), nullable=False, unique=True),
        sa.Column("seed_song_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("best_reference_song_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("latest_reference_song_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("seed_song_audio_url", sa.Text),
        sa.Column("best_reference_audio_url", sa.Text),
        sa.Column("latest_reference_audio_url", sa.Text),
        sa.Column("suno_persona_id", sa.String(100), nullable=True),
        sa.Column("consistency_stats", postgresql.JSONB),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # releases -----------------------------------------------------------
    op.create_table(
        "releases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ai_artists.artist_id"), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("release_type", sa.String(20), nullable=False),  # single | EP | album | compilation
        sa.Column("release_date", sa.Date),
        sa.Column("pre_save_date", sa.Date),
        sa.Column("upc", sa.String(20)),
        sa.Column("distributor", sa.String(50)),
        sa.Column("distributor_release_id", sa.Text),
        sa.Column("artwork_asset_id", postgresql.UUID(as_uuid=True)),
        sa.Column("territory_rights", postgresql.ARRAY(sa.Text)),
        sa.Column("status", sa.String(30), server_default="planning"),
        # planning | submitted | live | takedown_requested | taken_down
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_releases_artist", "releases", ["artist_id"])
    op.create_index("idx_releases_status", "releases", ["status"])

    # audio_assets (§24) -------------------------------------------------
    op.create_table(
        "audio_assets",
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("song_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("songs_master.song_id"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_job_id", sa.Text),
        sa.Column("music_generation_call_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("music_generation_calls.id"), nullable=True),
        sa.Column("format", sa.String(10)),  # mp3 | wav | flac
        sa.Column("sample_rate", sa.Integer),
        sa.Column("bitrate", sa.Integer),
        sa.Column("duration_seconds", sa.Float),
        sa.Column("storage_url", sa.Text, nullable=False),
        sa.Column("storage_backend", sa.String(30)),  # replicate | s3 | local
        sa.Column("checksum", sa.String(80)),
        sa.Column("is_master_candidate", sa.Boolean, server_default="FALSE"),
        sa.Column("loudness_lufs", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_audio_assets_song", "audio_assets", ["song_id"])
    op.create_index("idx_audio_assets_master", "audio_assets", ["is_master_candidate"])

    # song_qa_reports (§25) ----------------------------------------------
    op.create_table(
        "song_qa_reports",
        sa.Column("qa_report_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("song_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("songs_master.song_id"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("audio_assets.asset_id"), nullable=False),
        sa.Column("duration_ok", sa.Boolean),
        sa.Column("tempo_match_score", sa.Float),
        sa.Column("key_match_score", sa.Float),
        sa.Column("energy_match_score", sa.Float),
        sa.Column("silence_score", sa.Float),
        sa.Column("clipping_score", sa.Float),
        sa.Column("loudness_lufs", sa.Float),
        sa.Column("lyric_intelligibility_score", sa.Float),
        sa.Column("vocal_prominence_score", sa.Float),
        sa.Column("duplication_risk_score", sa.Float),
        sa.Column("pass_fail", sa.Boolean, nullable=False),
        sa.Column("failure_reasons", postgresql.ARRAY(sa.Text)),
        sa.Column("report_json", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_qa_reports_song", "song_qa_reports", ["song_id"])

    # release_track_record ----------------------------------------------
    op.create_table(
        "release_track_record",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("song_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("songs_master.song_id"), nullable=False),
        sa.Column("release_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("releases.id"), nullable=False),
        sa.Column("track_number", sa.Integer, nullable=False),
        sa.Column("is_lead_single", sa.Boolean, server_default="FALSE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("release_id", "track_number", name="rtr_release_track_unique"),
    )

    # song_submissions (distribution lane) -------------------------------
    op.create_table(
        "song_submissions",
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("song_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("songs_master.song_id"), nullable=False),
        sa.Column("release_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("releases.id"), nullable=True),
        sa.Column("distributor", sa.String(50), nullable=False),
        # labelgrid | revelator | sonosuite
        sa.Column("submission_type", sa.String(30), nullable=False),
        # initial_release | metadata_update | takedown | artwork_update
        sa.Column("payload", postgresql.JSONB),
        sa.Column("response_payload", postgresql.JSONB),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        # pending | submitted | processing | live | rejected | takedown
        sa.Column("distributor_work_id", sa.Text),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_submissions_song", "song_submissions", ["song_id"])
    op.create_index("idx_submissions_status", "song_submissions", ["status"])

    # royalty_registrations (rights lanes) -------------------------------
    op.create_table(
        "royalty_registrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("song_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("songs_master.song_id"), nullable=False),
        sa.Column("lane", sa.String(30), nullable=False),
        # pro_ascap | pro_bmi | mlc_mechanical | soundex_neighboring | youtube_cid | sync_marketplace
        sa.Column("target_org", sa.String(100), nullable=False),
        sa.Column("external_id", sa.Text),
        sa.Column("status", sa.String(30), server_default="pending"),
        sa.Column("submission_payload", postgresql.JSONB),
        sa.Column("response_payload", postgresql.JSONB),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_royalty_song", "royalty_registrations", ["song_id"])
    op.create_index("idx_royalty_lane_status", "royalty_registrations", ["lane", "status"])

    # marketing_campaigns -----------------------------------------------
    op.create_table(
        "marketing_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("song_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("songs_master.song_id"), nullable=False),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ai_artists.artist_id"), nullable=False),
        sa.Column("phase", sa.String(10), nullable=False),  # M0 | M1 | M2 | M3 | M4 | M5
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("phase_entered_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("next_gate_check_at", sa.DateTime(timezone=True)),
        sa.Column("metrics_snapshot", postgresql.JSONB),
        sa.Column("status", sa.String(30), server_default="active"),
        # active | paused | graduated | killed
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_campaigns_song", "marketing_campaigns", ["song_id"])
    op.create_index("idx_campaigns_artist", "marketing_campaigns", ["artist_id"])
    op.create_index("idx_campaigns_phase_status", "marketing_campaigns", ["phase", "status"])

    # social_accounts ---------------------------------------------------
    op.create_table(
        "social_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ai_artists.artist_id"), nullable=False),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("handle", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(200)),
        sa.Column("platform_user_id", sa.String(200)),
        sa.Column("oauth_token_encrypted", sa.Text),
        sa.Column("refresh_token_encrypted", sa.Text),
        sa.Column("token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("follower_count", sa.Integer, server_default="0"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(30), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("artist_id", "platform", name="social_accounts_artist_platform_unique"),
    )

    # social_posts ------------------------------------------------------
    op.create_table(
        "social_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ai_artists.artist_id"), nullable=False),
        sa.Column("social_account_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("social_accounts.id"), nullable=False),
        sa.Column("song_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("songs_master.song_id"), nullable=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("marketing_campaigns.id"), nullable=True),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("post_kind", sa.String(30), nullable=False),
        sa.Column("content_brief", sa.Text),
        sa.Column("asset_url", sa.Text),
        sa.Column("caption", sa.Text),
        sa.Column("hashtags", postgresql.ARRAY(sa.Text)),
        sa.Column("scheduled_for", sa.DateTime(timezone=True)),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("platform_post_id", sa.String(200)),
        sa.Column("views", sa.BigInteger, server_default="0"),
        sa.Column("likes", sa.BigInteger, server_default="0"),
        sa.Column("shares", sa.BigInteger, server_default="0"),
        sa.Column("saves", sa.BigInteger, server_default="0"),
        sa.Column("comments", sa.BigInteger, server_default="0"),
        sa.Column("last_metrics_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(30), server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_posts_campaign", "social_posts", ["campaign_id"])
    op.create_index("idx_posts_scheduled", "social_posts", ["scheduled_for"])

    # revenue_events ----------------------------------------------------
    op.create_table(
        "revenue_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("song_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("songs_master.song_id"), nullable=False),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ai_artists.artist_id"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("territory", sa.String(10)),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("stream_count", sa.BigInteger, server_default="0"),
        sa.Column("revenue_cents", sa.BigInteger, server_default="0"),
        sa.Column("royalty_type", sa.String(30)),
        sa.Column("source", sa.String(50)),
        sa.Column("raw_payload", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_revenue_song", "revenue_events", ["song_id"])
    op.create_index("idx_revenue_period", "revenue_events", ["period_start", "period_end"])

    # Deferred FK backfill on songs_master ------------------------------
    op.create_foreign_key(
        "fk_songs_master_release", "songs_master", "releases",
        ["release_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_songs_master_qa_report", "songs_master", "song_qa_reports",
        ["qa_report_id"], ["qa_report_id"],
    )
    op.create_foreign_key(
        "fk_songs_master_artwork", "songs_master", "artist_visual_assets",
        ["primary_artwork_asset_id"], ["asset_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_songs_master_artwork", "songs_master", type_="foreignkey")
    op.drop_constraint("fk_songs_master_qa_report", "songs_master", type_="foreignkey")
    op.drop_constraint("fk_songs_master_release", "songs_master", type_="foreignkey")
    for t in [
        "revenue_events", "social_posts", "social_accounts", "marketing_campaigns",
        "royalty_registrations", "song_submissions", "release_track_record",
        "song_qa_reports", "audio_assets", "releases", "artist_voice_state",
        "artist_visual_assets", "reference_artists",
    ]:
        op.drop_table(t)
