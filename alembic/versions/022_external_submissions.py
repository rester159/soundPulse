"""External submissions registry (T-200..T-229, PRD §28..§37)

Revision ID: 022
Revises: 021
Create Date: 2026-04-13

Single generic `external_submissions` table that every downstream
submission agent writes to — distributors, PROs, sync marketplaces,
marketing destinations. Each row captures:

  - target_service: e.g. 'distrokid', 'cd-baby', 'bmi', 'mlc', 'musicbed',
    'soundexchange', 'youtube_content_id', 'spotify_editorial',
    'playlist_push', 'marmoset', 'artlist', 'submithub', etc
  - target_type: 'distributor' | 'pro' | 'sync' | 'playlist' | 'marketing'
  - submission_subject_type: 'song' | 'release' | 'artist' | 'video'
  - subject_id: UUID into songs_master / releases / ai_artists
  - external_id: identifier the service returned (upc, isrc, submission
    number, etc)
  - status: queued | in_progress | submitted | accepted | rejected | failed
  - payload_json: the exact body/form sent to the service (audit trail)
  - response_json: the raw response
  - retry_count, last_error_message

Why ONE table instead of N per-service tables:
  - The external services have different field vocabularies but the
    AGENT LOGIC (queue → submit → poll → retry → CEO escalate) is
    identical. Sharing the table lets the Submissions Agent sweep all
    services uniformly.
  - Per-service tables would explode into 15+ schemas without adding
    capability. Generic + JSONB is the right tradeoff for v1.
  - ASCAP specifically keeps its own table (ascap_submissions) because
    it has structured writer/publisher splits that are legally load-
    bearing. Everything else is loose enough for JSONB.

Seeds the submission_targets lookup with the canonical service ids so
admin endpoints can list available integration targets.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_submissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("target_service", sa.Text, nullable=False),
        sa.Column("target_type", sa.Text, nullable=False),
        sa.Column("submission_subject_type", sa.Text, nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.Text, nullable=False, server_default="queued"),
        sa.Column("external_id", sa.Text, nullable=True),
        sa.Column("payload_json", postgresql.JSONB, nullable=True),
        sa.Column("response_json", postgresql.JSONB, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error_message", sa.Text, nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
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
        "ck_external_submissions_status",
        "external_submissions",
        "status IN ('queued','in_progress','submitted','accepted','rejected','failed','awaiting_review')",
    )
    op.create_check_constraint(
        "ck_external_submissions_target_type",
        "external_submissions",
        "target_type IN ('distributor','pro','sync','playlist','marketing','rights','content_id')",
    )
    op.create_check_constraint(
        "ck_external_submissions_subject_type",
        "external_submissions",
        "submission_subject_type IN ('song','release','artist','video','track','writer')",
    )
    op.create_index(
        "ix_external_submissions_status",
        "external_submissions",
        ["status"],
    )
    op.create_index(
        "ix_external_submissions_target",
        "external_submissions",
        ["target_service", "submission_subject_type", "subject_id"],
    )

    # submission_targets — one row per known integration. Seed the
    # canonical ids so admin endpoints can list what's available.
    op.create_table(
        "submission_targets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("target_service", sa.Text, nullable=False, unique=True),
        sa.Column("target_type", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column(
            "credential_env_keys",
            postgresql.ARRAY(sa.Text),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "integration_status",
            sa.Text,
            nullable=False,
            server_default="stub",  # stub | partial | live
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_submission_targets_type",
        "submission_targets",
        "target_type IN ('distributor','pro','sync','playlist','marketing','rights','content_id')",
    )

    # Seed the 20 canonical integration targets. All start as 'stub'
    # integration_status — the agent service in api/services/
    # external_submission_agent.py resolves each service at call time.
    seed = [
        # target_service,     target_type,  display_name,         credential_env_keys, notes
        ("distrokid",         "distributor", "DistroKid",          ["DISTROKID_USERNAME","DISTROKID_PASSWORD"], "CEO account; Playwright-driven portal"),
        ("tunecore",          "distributor", "TuneCore",           ["TUNECORE_USERNAME","TUNECORE_PASSWORD"], "Playwright portal"),
        ("cd-baby",           "distributor", "CD Baby",            ["CDBABY_USERNAME","CDBABY_PASSWORD"], "Playwright portal"),
        ("amuse",             "distributor", "Amuse",              ["AMUSE_USERNAME","AMUSE_PASSWORD"], "Playwright portal"),
        ("unitedmasters",     "distributor", "UnitedMasters",      ["UNITEDMASTERS_USERNAME","UNITEDMASTERS_PASSWORD"], "Playwright portal"),
        ("bmi",               "pro",         "BMI",                ["BMI_USERNAME","BMI_PASSWORD"], "Alt PRO to ASCAP for writers split"),
        ("mlc",               "rights",      "MLC (DDEX)",         ["MLC_CLIENT_ID","MLC_CLIENT_SECRET"], "DDEX XML API"),
        ("soundexchange",     "rights",      "SoundExchange",      ["SOUNDEXCHANGE_USERNAME","SOUNDEXCHANGE_PASSWORD"], "Digital performance royalties"),
        ("youtube_content_id","content_id",  "YouTube Content ID", ["YOUTUBE_CMS_SERVICE_ACCOUNT_JSON"], "Google partner API"),
        ("musicbed",          "sync",        "Musicbed",           ["MUSICBED_USERNAME","MUSICBED_PASSWORD"], "Sync licensing marketplace"),
        ("marmoset",          "sync",        "Marmoset",           ["MARMOSET_USERNAME","MARMOSET_PASSWORD"], "Sync licensing curation"),
        ("artlist",           "sync",        "Artlist",            ["ARTLIST_USERNAME","ARTLIST_PASSWORD"], "Sync subscription marketplace"),
        ("submithub",         "sync",        "SubmitHub",          ["SUBMITHUB_API_KEY"], "Has a real API"),
        ("groover",           "playlist",    "Groover",            ["GROOVER_USERNAME","GROOVER_PASSWORD"], "Curator submission portal"),
        ("playlistpush",      "playlist",    "Playlist Push",      ["PLAYLISTPUSH_USERNAME","PLAYLISTPUSH_PASSWORD"], "Playlist pitching service"),
        ("spotify_editorial", "playlist",    "Spotify for Artists", ["SPOTIFY_FOR_ARTISTS_SESSION"], "Editorial pitch flow"),
        ("apple_music_for_artists","playlist","Apple Music for Artists",["APPLE_MUSIC_FOR_ARTISTS_SESSION"], "Editorial pitch flow"),
        ("press_release_agent","marketing",  "Press Release Agent", [], "LLM-generated press kits, future Mailchimp hookup"),
        ("social_media_agent","marketing",   "Social Media Agent",  ["BUFFER_ACCESS_TOKEN"], "Instagram + TikTok + X schedule"),
        ("tiktok_upload",     "marketing",   "TikTok Upload Bot",   ["TIKTOK_UPLOAD_SESSION"], "Playwright-driven upload for snippet posts"),
    ]
    conn = op.get_bind()
    insert = sa.text("""
        INSERT INTO submission_targets
            (target_service, target_type, display_name, credential_env_keys, integration_status, notes)
        VALUES (:svc, :tt, :dn, :ck, 'stub', :nt)
        ON CONFLICT (target_service) DO NOTHING
    """)
    for svc, tt, dn, ck, nt in seed:
        conn.execute(insert, {"svc": svc, "tt": tt, "dn": dn, "ck": ck, "nt": nt})


def downgrade() -> None:
    op.drop_constraint("ck_submission_targets_type", "submission_targets", type_="check")
    op.drop_table("submission_targets")
    op.drop_index("ix_external_submissions_target", table_name="external_submissions")
    op.drop_index("ix_external_submissions_status", table_name="external_submissions")
    op.drop_constraint("ck_external_submissions_subject_type", "external_submissions", type_="check")
    op.drop_constraint("ck_external_submissions_target_type", "external_submissions", type_="check")
    op.drop_constraint("ck_external_submissions_status", "external_submissions", type_="check")
    op.drop_table("external_submissions")
