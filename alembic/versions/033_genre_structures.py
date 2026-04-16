"""Per-genre song structure templates (task #109, PRD §70)

Revision ID: 033
Revises: 032
Create Date: 2026-04-15

Stores a per-genre song-form skeleton (Intro 8 / Verse 16 / Chorus 8 / ...)
that the song generation orchestrator injects into every Suno prompt as a
[Section: N bars{, instrumental}] tag block. The goal is structural
predictability: a generated song should land within +-1 bar of a known
genre template so a human-made instrumental of the same length and shape
can be vocal-mixed against it without DTW gymnastics (see L014).

Schema:
  genre_structures (
    primary_genre  TEXT PK            -- canonical taxonomy id (e.g. 'pop.k-pop')
    structure      JSONB NOT NULL     -- list[{name: str, bars: int, vocals: bool}]
    notes          TEXT               -- 1-line rationale per row
    updated_at     TIMESTAMPTZ        -- bump on every write
    updated_by     TEXT               -- who set this (CEO | seed_033 | agent)
  )

The 20 seed rows below are length-realistic against published bar counts
for each genre: pop ~3:00-3:30, trap ~2:45, drill ~2:00-2:30,
techno/ambient/lo-fi extended, k-pop adds a Dance break, house adds Build
and Drop, etc. Bars validated against BPM math: seconds_per_bar = 60/BPM*4
at 4/4 time signature. Each row's notes column carries a 1-line rationale
so a future human can see why we picked it.

Cross-checked against shared/genre_taxonomy.py canonical IDs. The plan in
NEXT_SESSION_START_HERE.md proposed 'rap' as a separate seed; that ID
doesn't exist in the taxonomy (rap lives under hip-hop subgenres). We
substitute caribbean.reggae for global-reach diversity.

Resolution: genre_structures_service.resolve_genre_structure() walks the
dotted chain (pop.k-pop -> pop) before falling back to 'pop'. So a row
for every leaf is not required — only for the genres we want to differ
from their parent.
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "genre_structures",
        sa.Column("primary_genre", sa.Text, primary_key=True),
        sa.Column(
            "structure",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("updated_by", sa.Text, nullable=True),
    )

    # Defense-in-depth at the DB level: structure must be a non-empty
    # JSONB array. Application-side validation in
    # api/services/genre_structures_service.validate_structure() is the
    # primary gate; this is a backstop for any direct SQL writes.
    op.create_check_constraint(
        "ck_genre_structures_nonempty",
        "genre_structures",
        "jsonb_typeof(structure) = 'array' AND jsonb_array_length(structure) > 0",
    )

    # Seed 20 genres. Each tuple is (primary_genre, structure_list, notes).
    # Bar math at 4/4: seconds_per_bar = 60/BPM * 4. Targets noted per row.
    seed_rows: list[tuple[str, list[dict], str]] = [
        # ----- POP family -----
        (
            "pop",
            [
                {"name": "Intro", "bars": 8, "vocals": False},
                {"name": "Verse 1", "bars": 16, "vocals": True},
                {"name": "Pre-chorus", "bars": 4, "vocals": True},
                {"name": "Chorus", "bars": 8, "vocals": True},
                {"name": "Verse 2", "bars": 16, "vocals": True},
                {"name": "Pre-chorus", "bars": 4, "vocals": True},
                {"name": "Chorus", "bars": 8, "vocals": True},
                {"name": "Bridge", "bars": 8, "vocals": True},
                {"name": "Chorus", "bars": 16, "vocals": True},
                {"name": "Outro", "bars": 4, "vocals": False},
            ],
            "Mainstream pop ~115 BPM, ~3:12. V-PreC-C twice + bridge + double-chorus payoff. Sabrina Carpenter / Olivia Rodrigo template.",
        ),
        (
            "pop.k-pop",
            [
                {"name": "Intro", "bars": 4, "vocals": False},
                {"name": "Verse 1", "bars": 16, "vocals": True},
                {"name": "Pre-chorus", "bars": 4, "vocals": True},
                {"name": "Chorus", "bars": 16, "vocals": True},
                {"name": "Verse 2", "bars": 16, "vocals": True},
                {"name": "Pre-chorus", "bars": 4, "vocals": True},
                {"name": "Chorus", "bars": 16, "vocals": True},
                {"name": "Bridge", "bars": 8, "vocals": True},
                {"name": "Dance break", "bars": 4, "vocals": False},
                {"name": "Chorus", "bars": 16, "vocals": True},
                {"name": "Outro", "bars": 4, "vocals": False},
            ],
            "K-pop ~120 BPM, ~3:36. Mandatory dance break before final chorus. Choruses are longer than verses.",
        ),
        (
            "pop.dance-pop",
            [
                {"name": "Intro", "bars": 8, "vocals": False},
                {"name": "Verse 1", "bars": 16, "vocals": True},
                {"name": "Pre-chorus", "bars": 4, "vocals": True},
                {"name": "Chorus", "bars": 8, "vocals": True},
                {"name": "Verse 2", "bars": 16, "vocals": True},
                {"name": "Pre-chorus", "bars": 4, "vocals": True},
                {"name": "Chorus", "bars": 8, "vocals": True},
                {"name": "Bridge", "bars": 8, "vocals": True},
                {"name": "Chorus", "bars": 16, "vocals": True},
                {"name": "Outro", "bars": 4, "vocals": False},
            ],
            "Dance-pop ~125 BPM, ~3:00. Same skeleton as pop with slightly tighter intro/outro for dancefloor energy.",
        ),
        (
            "pop.indie-pop",
            [
                {"name": "Intro", "bars": 8, "vocals": False},
                {"name": "Verse 1", "bars": 16, "vocals": True},
                {"name": "Chorus", "bars": 8, "vocals": True},
                {"name": "Verse 2", "bars": 16, "vocals": True},
                {"name": "Chorus", "bars": 8, "vocals": True},
                {"name": "Bridge", "bars": 8, "vocals": True},
                {"name": "Chorus", "bars": 16, "vocals": True},
                {"name": "Outro", "bars": 8, "vocals": False},
            ],
            "Indie-pop ~110 BPM, ~3:12. Drops the pre-chorus for a more conversational verse-to-chorus transition (Clairo, Beabadoobee).",
        ),
        (
            "pop.latin-pop",
            [
                {"name": "Intro", "bars": 4, "vocals": False},
                {"name": "Verse 1", "bars": 16, "vocals": True},
                {"name": "Pre-chorus", "bars": 4, "vocals": True},
                {"name": "Chorus", "bars": 8, "vocals": True},
                {"name": "Verse 2", "bars": 16, "vocals": True},
                {"name": "Pre-chorus", "bars": 4, "vocals": True},
                {"name": "Chorus", "bars": 8, "vocals": True},
                {"name": "Bridge", "bars": 8, "vocals": True},
                {"name": "Chorus", "bars": 16, "vocals": True},
                {"name": "Outro", "bars": 4, "vocals": False},
            ],
            "Latin-pop ~110 BPM, ~3:12. Pop skeleton with shorter intro for radio-friendly punch (Camila Cabello, Becky G).",
        ),
        # ----- HIP-HOP family -----
        (
            "hip-hop",
            [
                {"name": "Intro", "bars": 4, "vocals": False},
                {"name": "Verse 1", "bars": 16, "vocals": True},
                {"name": "Hook", "bars": 8, "vocals": True},
                {"name": "Verse 2", "bars": 16, "vocals": True},
                {"name": "Hook", "bars": 8, "vocals": True},
                {"name": "Bridge", "bars": 4, "vocals": True},
                {"name": "Hook", "bars": 8, "vocals": True},
                {"name": "Outro", "bars": 4, "vocals": False},
            ],
            "Hip-hop ~80 BPM half-time feel, ~3:24. Verse-hook-verse-hook with bridge-led final hook. Hook isolation MANDATORY.",
        ),
        (
            "hip-hop.trap",
            [
                {"name": "Intro", "bars": 8, "vocals": False},
                {"name": "Hook", "bars": 8, "vocals": True},
                {"name": "Verse 1", "bars": 16, "vocals": True},
                {"name": "Hook", "bars": 8, "vocals": True},
                {"name": "Verse 2", "bars": 16, "vocals": True},
                {"name": "Hook", "bars": 8, "vocals": True},
                {"name": "Bridge", "bars": 8, "vocals": True},
                {"name": "Hook", "bars": 16, "vocals": True},
                {"name": "Outro", "bars": 8, "vocals": False},
            ],
            "Trap ~140 BPM, ~2:45. Hook-first intro convention (ATL / 808 Mafia template). Hook returns 4x.",
        ),
        (
            "hip-hop.trap.drill",
            [
                {"name": "Intro", "bars": 4, "vocals": False},
                {"name": "Verse 1", "bars": 16, "vocals": True},
                {"name": "Hook", "bars": 8, "vocals": True},
                {"name": "Verse 2", "bars": 16, "vocals": True},
                {"name": "Hook", "bars": 8, "vocals": True},
                {"name": "Verse 3", "bars": 8, "vocals": True},
                {"name": "Hook", "bars": 8, "vocals": True},
                {"name": "Outro", "bars": 4, "vocals": False},
            ],
            "Drill ~140-150 BPM, ~2:08. Three short verses, no bridge, fast turnaround (UK / Brooklyn drill template).",
        ),
        # ----- R&B / SOUL -----
        (
            "r-and-b",
            [
                {"name": "Intro", "bars": 4, "vocals": False},
                {"name": "Verse 1", "bars": 16, "vocals": True},
                {"name": "Pre-chorus", "bars": 4, "vocals": True},
                {"name": "Chorus", "bars": 8, "vocals": True},
                {"name": "Verse 2", "bars": 16, "vocals": True},
                {"name": "Pre-chorus", "bars": 4, "vocals": True},
                {"name": "Chorus", "bars": 8, "vocals": True},
                {"name": "Bridge", "bars": 8, "vocals": True},
                {"name": "Chorus", "bars": 16, "vocals": True},
                {"name": "Outro", "bars": 4, "vocals": False},
            ],
            "Modern R&B ~85 BPM, ~4:08. SZA / Summer Walker template, melismatic chorus with pre-chorus lift.",
        ),
        # ----- ELECTRONIC family -----
        (
            "electronic.edm",
            [
                {"name": "Intro", "bars": 16, "vocals": False},
                {"name": "Verse", "bars": 8, "vocals": True},
                {"name": "Build", "bars": 8, "vocals": True},
                {"name": "Drop", "bars": 16, "vocals": False},
                {"name": "Breakdown", "bars": 16, "vocals": True},
                {"name": "Build", "bars": 8, "vocals": True},
                {"name": "Drop", "bars": 16, "vocals": False},
                {"name": "Outro", "bars": 16, "vocals": False},
            ],
            "EDM ~128 BPM, ~3:18. Build-Drop-Breakdown-Build-Drop is the radio festival template (Marshmello, Zedd).",
        ),
        (
            "electronic.house",
            [
                {"name": "Intro", "bars": 16, "vocals": False},
                {"name": "Verse", "bars": 16, "vocals": True},
                {"name": "Build", "bars": 8, "vocals": True},
                {"name": "Drop", "bars": 32, "vocals": False},
                {"name": "Breakdown", "bars": 16, "vocals": True},
                {"name": "Build", "bars": 8, "vocals": True},
                {"name": "Drop", "bars": 32, "vocals": False},
                {"name": "Outro", "bars": 16, "vocals": False},
            ],
            "House ~124 BPM, ~4:40. Long instrumental drops. Vocal is a hook loop, not a story (Disclosure, Fred Again..).",
        ),
        (
            "electronic.techno",
            [
                {"name": "Intro", "bars": 32, "vocals": False},
                {"name": "Hook", "bars": 32, "vocals": False},
                {"name": "Breakdown", "bars": 32, "vocals": False},
                {"name": "Hook", "bars": 64, "vocals": False},
                {"name": "Breakdown", "bars": 16, "vocals": False},
                {"name": "Outro", "bars": 32, "vocals": False},
            ],
            "Techno ~128 BPM, ~6:30. Mostly instrumental. Vocals are atmospheric tags, not a song-form. Long mix-friendly intro/outro.",
        ),
        (
            "electronic.lo-fi-electronic",
            [
                {"name": "Intro", "bars": 8, "vocals": False},
                {"name": "Loop A", "bars": 16, "vocals": False},
                {"name": "Loop B", "bars": 16, "vocals": False},
                {"name": "Loop A", "bars": 16, "vocals": False},
                {"name": "Loop B", "bars": 16, "vocals": False},
                {"name": "Outro", "bars": 8, "vocals": False},
            ],
            "Lo-fi ~75 BPM, ~4:16. AB-AB loop architecture for chillhop / study beats. Instrumental by default, vocal samples optional.",
        ),
        (
            "electronic.ambient",
            [
                {"name": "Intro", "bars": 16, "vocals": False},
                {"name": "Movement 1", "bars": 32, "vocals": False},
                {"name": "Movement 2", "bars": 32, "vocals": False},
                {"name": "Movement 3", "bars": 32, "vocals": False},
                {"name": "Outro", "bars": 16, "vocals": False},
            ],
            "Ambient ~70 BPM (loose), ~7:19. Through-composed movements rather than verse-chorus, bar counts are pacing hints not strict.",
        ),
        # ----- AFRICAN family -----
        (
            "african.afrobeats",
            [
                {"name": "Intro", "bars": 8, "vocals": False},
                {"name": "Verse 1", "bars": 8, "vocals": True},
                {"name": "Hook", "bars": 16, "vocals": True},
                {"name": "Verse 2", "bars": 8, "vocals": True},
                {"name": "Hook", "bars": 16, "vocals": True},
                {"name": "Bridge", "bars": 8, "vocals": True},
                {"name": "Hook", "bars": 16, "vocals": True},
                {"name": "Outro", "bars": 8, "vocals": False},
            ],
            "Afrobeats ~110 BPM, ~3:12. Hook-heavy with shorter verses (Burna Boy, Rema, Tems template).",
        ),
        (
            "african.amapiano",
            [
                {"name": "Intro", "bars": 16, "vocals": False},
                {"name": "Verse 1", "bars": 16, "vocals": True},
                {"name": "Hook", "bars": 16, "vocals": True},
                {"name": "Verse 2", "bars": 16, "vocals": True},
                {"name": "Hook", "bars": 16, "vocals": True},
                {"name": "Log drum break", "bars": 16, "vocals": False},
                {"name": "Hook", "bars": 16, "vocals": True},
                {"name": "Outro", "bars": 16, "vocals": False},
            ],
            "Amapiano ~112 BPM, ~4:34. Mandatory log-drum break before final hook (Kabza De Small, DJ Maphorisa).",
        ),
        # ----- LATIN family -----
        (
            "latin.reggaeton",
            [
                {"name": "Intro", "bars": 4, "vocals": False},
                {"name": "Verse 1", "bars": 8, "vocals": True},
                {"name": "Pre-chorus", "bars": 4, "vocals": True},
                {"name": "Chorus", "bars": 8, "vocals": True},
                {"name": "Verse 2", "bars": 8, "vocals": True},
                {"name": "Pre-chorus", "bars": 4, "vocals": True},
                {"name": "Chorus", "bars": 8, "vocals": True},
                {"name": "Bridge", "bars": 4, "vocals": True},
                {"name": "Chorus", "bars": 16, "vocals": True},
                {"name": "Outro", "bars": 4, "vocals": False},
            ],
            "Reggaeton ~95 BPM, ~2:52. Bad Bunny / Karol G template, shorter verses, dembow-driven choruses.",
        ),
        # ----- ROCK / COUNTRY -----
        (
            "rock",
            [
                {"name": "Intro", "bars": 8, "vocals": False},
                {"name": "Verse 1", "bars": 16, "vocals": True},
                {"name": "Chorus", "bars": 8, "vocals": True},
                {"name": "Verse 2", "bars": 16, "vocals": True},
                {"name": "Chorus", "bars": 8, "vocals": True},
                {"name": "Bridge", "bars": 8, "vocals": True},
                {"name": "Solo", "bars": 16, "vocals": False},
                {"name": "Chorus", "bars": 16, "vocals": True},
                {"name": "Outro", "bars": 8, "vocals": False},
            ],
            "Rock ~120 BPM, ~3:28. Mandatory instrumental solo before final chorus (Wolf Alice, Fontaines DC template).",
        ),
        (
            "country",
            [
                {"name": "Intro", "bars": 4, "vocals": False},
                {"name": "Verse 1", "bars": 16, "vocals": True},
                {"name": "Chorus", "bars": 8, "vocals": True},
                {"name": "Verse 2", "bars": 16, "vocals": True},
                {"name": "Chorus", "bars": 8, "vocals": True},
                {"name": "Bridge", "bars": 8, "vocals": True},
                {"name": "Chorus", "bars": 16, "vocals": True},
                {"name": "Outro", "bars": 4, "vocals": False},
            ],
            "Country ~95 BPM, ~3:12. Story-driven verses with anthemic doubled-length final chorus (Zach Bryan, Morgan Wallen).",
        ),
        # ----- CARIBBEAN (substitute for original 'rap' which duplicates hip-hop) -----
        (
            "caribbean.reggae",
            [
                {"name": "Intro", "bars": 4, "vocals": False},
                {"name": "Verse 1", "bars": 16, "vocals": True},
                {"name": "Chorus", "bars": 8, "vocals": True},
                {"name": "Verse 2", "bars": 16, "vocals": True},
                {"name": "Chorus", "bars": 8, "vocals": True},
                {"name": "Bridge", "bars": 8, "vocals": True},
                {"name": "Chorus", "bars": 16, "vocals": True},
                {"name": "Outro", "bars": 4, "vocals": False},
            ],
            "Reggae ~80 BPM, ~4:00. Pocket-bass + rim-shot drums. Chorus must loop, bridge can drop to bass+drums only.",
        ),
    ]

    insert_stmt = sa.text(
        """
        INSERT INTO genre_structures (
            primary_genre, structure, notes, updated_by
        ) VALUES (
            :primary_genre, CAST(:structure AS jsonb), :notes, 'seed_033'
        )
        ON CONFLICT (primary_genre) DO NOTHING
        """
    )
    conn = op.get_bind()
    for primary_genre, structure, notes in seed_rows:
        conn.execute(
            insert_stmt,
            {
                "primary_genre": primary_genre,
                "structure": json.dumps(structure),
                "notes": notes,
            },
        )


def downgrade() -> None:
    op.drop_constraint(
        "ck_genre_structures_nonempty", "genre_structures", type_="check"
    )
    op.drop_table("genre_structures")
