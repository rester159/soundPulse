"""Genre traits — multi-dimensional genre profile (task follow-up on CEO feedback)

Revision ID: 020
Revises: 019
Create Date: 2026-04-13

Powers the 'not all genres lend themselves to meme-y content' feedback
from the CEO. Stores a rich per-genre trait profile so the edge rules,
pop-culture scraper, and earworm rule can dial themselves up or down
per genre instead of treating every genre the same.

Core insight: K-pop tolerates (and rewards) chronically-online slang
like 'delulu'; outlaw country does not. Hip-hop tolerates savage named-
target takes; lullabies do not. We need a structured place to encode
this rather than hardcoding it in if/else branches.

Schema:
  genre_traits (
    id                  UUID PK
    genre_id            TEXT UNIQUE — canonical taxonomy id (e.g. 'pop.k-pop')
    edginess            INT 0-100 — how opinionated the lyrics should be
    meme_density        INT 0-100 — how much internet/TikTok slang is appropriate
    earworm_demand      INT 0-100 — how strict the earworm mechanics are
    sonic_experimentation INT 0-100 — how much the sonic gap should stretch
    lyrical_complexity  INT 0-100 — simple pop hooks vs dense poetic rap
    vocal_processing    INT 0-100 — none (folk) → heavy (hyperpop)
    tempo_range_bpm     INT[2] — [min_bpm, max_bpm]
    key_mood            TEXT — 'minor_default' | 'major_default' | 'mixed'
    default_edge_profile TEXT — clean_edge | flirty_edge | savage_edge
    vocabulary_era      TEXT — which pop culture era fits — 'gen_z' | 'millennial' |
                              'timeless' | 'outlaw_classic' | 'diaspora'
    pop_culture_sources TEXT[] — which scraper reference_types to pull from
    instrumentation_palette TEXT[] — canonical instruments for the genre
    structural_conventions TEXT — notes on song structure, length, transitions
    notes               TEXT — free-form spec notes
    updated_by          TEXT — who set this (CEO | agent | persona_blender)
    is_system_default   BOOLEAN — TRUE if seeded, FALSE if CEO-overridden
    created_at          TIMESTAMPTZ
    updated_at          TIMESTAMPTZ
  )

The seven numeric dimensions sit on a 0-100 scale so we can blend
genre traits via linear interpolation for hybrid artists (a K-pop-meets-
afrobeats artist gets midpoints). Discrete fields (key_mood, default_edge_
profile, vocabulary_era) keep options bounded.

Seed data: 20 genre rows covering the most common SoundPulse targets.
CEO can override any field via the admin UI; is_system_default flips to
FALSE on override so subsequent seed runs don't clobber customization.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "genre_traits",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("genre_id", sa.Text, nullable=False, unique=True),
        sa.Column("edginess", sa.Integer, nullable=False, server_default="50"),
        sa.Column("meme_density", sa.Integer, nullable=False, server_default="30"),
        sa.Column("earworm_demand", sa.Integer, nullable=False, server_default="70"),
        sa.Column("sonic_experimentation", sa.Integer, nullable=False, server_default="40"),
        sa.Column("lyrical_complexity", sa.Integer, nullable=False, server_default="50"),
        sa.Column("vocal_processing", sa.Integer, nullable=False, server_default="40"),
        sa.Column(
            "tempo_range_bpm",
            postgresql.ARRAY(sa.Integer),
            nullable=False,
            server_default="{80,120}",
        ),
        sa.Column("key_mood", sa.Text, nullable=False, server_default="mixed"),
        sa.Column("default_edge_profile", sa.Text, nullable=False, server_default="flirty_edge"),
        sa.Column("vocabulary_era", sa.Text, nullable=False, server_default="timeless"),
        sa.Column(
            "pop_culture_sources",
            postgresql.ARRAY(sa.Text),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "instrumentation_palette",
            postgresql.ARRAY(sa.Text),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("structural_conventions", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("updated_by", sa.Text, nullable=True),
        sa.Column(
            "is_system_default",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
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
        "ck_genre_traits_scores",
        "genre_traits",
        (
            "edginess BETWEEN 0 AND 100 AND "
            "meme_density BETWEEN 0 AND 100 AND "
            "earworm_demand BETWEEN 0 AND 100 AND "
            "sonic_experimentation BETWEEN 0 AND 100 AND "
            "lyrical_complexity BETWEEN 0 AND 100 AND "
            "vocal_processing BETWEEN 0 AND 100"
        ),
    )
    op.create_check_constraint(
        "ck_genre_traits_edge",
        "genre_traits",
        "default_edge_profile IN ('clean_edge','flirty_edge','savage_edge')",
    )
    op.create_check_constraint(
        "ck_genre_traits_key_mood",
        "genre_traits",
        "key_mood IN ('minor_default','major_default','mixed')",
    )
    op.create_check_constraint(
        "ck_genre_traits_era",
        "genre_traits",
        "vocabulary_era IN ('gen_z','millennial','timeless','outlaw_classic','diaspora','global')",
    )

    # Seed 20 genre rows. We'll insert via raw SQL so the migration stays
    # self-contained without importing the model. Updated_by = 'seed_020'
    # so CEO overrides can be distinguished.
    seed_rows = [
        # (genre_id, edginess, meme_density, earworm, sonic_exp, lyr_cmplx,
        #  vocal_proc, tempo_min, tempo_max, key_mood, edge, era,
        #  pop_sources, instr_palette, structural, notes)
        (
            "pop.k-pop", 60, 85, 90, 55, 45, 70, 90, 130,
            "mixed", "flirty_edge", "gen_z",
            ["tiktok_phrase", "tiktok_sound", "tiktok_dance", "brand", "app", "slang"],
            ["supersaw", "trap drums", "wurlitzer stabs", "sub bass", "vocal chops"],
            "Verse-Prechorus-Chorus-Verse-Prechorus-Chorus-Bridge-Chorus; English hook with Hangul verses is standard; 3:00-3:30 ideal",
            "K-pop rewards internet slang, code-switching, and concept-teaser lyricism. delulu, mothering, it's giving all land. Avoid darker takes — keep confident not bitter."
        ),
        (
            "pop", 55, 65, 95, 50, 40, 60, 85, 125,
            "mixed", "flirty_edge", "gen_z",
            ["tiktok_phrase", "brand", "celeb_moment", "slang", "app"],
            ["piano", "acoustic guitar", "synth pads", "pocket drums", "bass"],
            "Sabrina Carpenter / Olivia Rodrigo era — double entendre choruses, specific imagery. 2:30-3:15 ideal for TikTok virality.",
            "Mainstream pop is the sweet spot for the full edgy + earworm + meme pipeline. Highest tolerance for pop-culture references."
        ),
        (
            "hip-hop", 85, 70, 80, 55, 75, 75, 80, 160,
            "minor_default", "savage_edge", "gen_z",
            ["tiktok_phrase", "brand", "gaming", "celeb_moment", "slang"],
            ["trap drums", "808", "sub bass", "orchestral pads", "melodic vocal"],
            "Verse-hook-verse-hook structure; trap convention 2:30-3:00; hook isolation is MANDATORY",
            "Hip-hop tolerates maximum savage_edge — named targets, drug references, explicit. Meme density high."
        ),
        (
            "rap", 90, 60, 75, 50, 85, 70, 75, 170,
            "minor_default", "savage_edge", "gen_z",
            ["tiktok_phrase", "brand", "gaming", "celeb_moment", "slang"],
            ["trap drums", "808", "sub bass", "minimal melody"],
            "Dense lyrical — rhyme schemes and internal rhymes matter more than melodic hook",
            "Rap (drill/trap/underground) — max lyrical complexity, max edge, lower earworm demand since hook is delivery-based not melodic."
        ),
        (
            "r&b", 60, 55, 85, 60, 65, 55, 70, 110,
            "minor_default", "flirty_edge", "gen_z",
            ["tiktok_phrase", "brand", "slang", "app"],
            ["rhodes", "electric bass", "ghost snares", "lush pads", "vocal harmonies"],
            "Slower, verse-chorus with pre-chorus lift; 3:00-4:00; melismatic runs in chorus",
            "Modern R&B (SZA, Kehlani, Summer Walker) tolerates meme references but more grown than K-pop."
        ),
        (
            "caribbean.reggae", 70, 40, 75, 50, 65, 50, 80, 100,
            "minor_default", "savage_edge", "diaspora",
            ["brand", "slang", "lyric_phrase"],
            ["pocket bass", "rim-shot drums", "wurlitzer", "afro-latin percussion", "horns"],
            "Verse-chorus with bridge; 3:00-3:30; chorus must loop",
            "Reggae/dancehall rewards specific Kingston references, Patois authenticity, dancehall swagger. Avoid TikTok slang — use Caribbean vocabulary. Named-target savagery works (see Popcaan, Masicka)."
        ),
        (
            "caribbean.dancehall", 80, 50, 80, 60, 65, 55, 95, 110,
            "minor_default", "savage_edge", "diaspora",
            ["brand", "slang", "lyric_phrase"],
            ["pocket bass", "drum machine", "horn stabs", "vocal ad-libs"],
            "Dubplate-style verses, heavy chorus loop, 3:00-3:30",
            "Dancehall maxes edginess and tempo. Kingston street references, not global internet memes."
        ),
        (
            "country", 50, 20, 85, 35, 55, 30, 80, 120,
            "major_default", "clean_edge", "outlaw_classic",
            ["brand", "news_event"],
            ["acoustic guitar", "pedal steel", "fiddle", "upright bass", "stomp drums"],
            "Verse-chorus-verse-chorus-bridge-chorus; 3:00-3:45; story songs OK",
            "Country uses concrete imagery — truck, beer, whiskey, small town, dirt road. Avoid TikTok slang. Sierra Ferrell / Tyler Childers tolerate edginess but through storytelling, not meme references."
        ),
        (
            "country.outlaw", 70, 15, 80, 40, 60, 30, 75, 115,
            "mixed", "savage_edge", "outlaw_classic",
            ["brand", "news_event"],
            ["acoustic guitar", "telecaster", "pedal steel", "stomp drums"],
            "Verse-chorus-verse-chorus-bridge-chorus; songs can run longer (3:30-4:30)",
            "Outlaw country (Zach Bryan, Tyler Childers) rewards named-target savagery but through storytelling not slang."
        ),
        (
            "country.bluegrass", 30, 5, 75, 25, 70, 15, 120, 170,
            "mixed", "clean_edge", "timeless",
            [],
            ["banjo", "fiddle", "mandolin", "acoustic guitar", "upright bass"],
            "Fast verse-chorus, instrumental breaks between, 2:30-3:30",
            "Bluegrass is classic — no meme content at all. Timeless vocabulary."
        ),
        (
            "folk", 40, 10, 70, 40, 70, 20, 60, 100,
            "minor_default", "clean_edge", "timeless",
            [],
            ["acoustic guitar", "piano", "strings", "ambient pads"],
            "Intimate verse-chorus; 3:00-4:30; story-driven",
            "Folk (Phoebe Bridgers, Bon Iver) uses concrete imagery but eschews internet slang. Specific without trendy."
        ),
        (
            "indie", 55, 35, 80, 65, 55, 45, 95, 135,
            "mixed", "flirty_edge", "millennial",
            ["tiktok_phrase", "brand", "app"],
            ["dry drums", "reverby guitar", "synth bass", "bedroom pop aesthetic"],
            "Verse-chorus-bridge, 3:00-3:30; chorus looping is key",
            "Indie pop (Clairo, Beabadoobee, Men I Trust) tolerates moderate meme references through an ironic lens."
        ),
        (
            "afrobeats", 65, 55, 85, 60, 50, 55, 100, 120,
            "major_default", "flirty_edge", "diaspora",
            ["brand", "slang", "celeb_moment"],
            ["kick + shaker pattern", "conga", "talking drum", "afro bass", "horn stabs"],
            "Rhythmic verse-chorus-verse-chorus-bridge-chorus; 3:00-3:45",
            "Afrobeats (Burna Boy, Rema, Tems) references West African culture + global pop. Pidgin English + local slang lands better than TikTok slang."
        ),
        (
            "latin.reggaeton", 75, 55, 90, 55, 55, 55, 85, 105,
            "minor_default", "savage_edge", "diaspora",
            ["brand", "slang", "tiktok_phrase"],
            ["dembow pattern", "bass", "latin percussion", "synth stabs"],
            "Hook-heavy verse-chorus with pre-chorus ramp, 2:30-3:30",
            "Reggaeton (Bad Bunny, Karol G, Rauw Alejandro) — max earworm demand, flirty-savage edge, bilingual refs work great."
        ),
        (
            "latin.bachata", 55, 25, 85, 35, 55, 40, 115, 135,
            "minor_default", "flirty_edge", "diaspora",
            [],
            ["nylon guitar", "bongó", "güira", "bass", "piano"],
            "AABA + breakdown, 3:00-3:30",
            "Bachata is traditional — romantic themes, no meme content, concrete sensual imagery."
        ),
        (
            "electronic.house", 40, 40, 95, 75, 30, 70, 118, 130,
            "mixed", "flirty_edge", "millennial",
            ["brand"],
            ["four-on-floor kick", "claps", "hi-hats", "stabs", "sub bass"],
            "Build-drop-build-drop structure; vocals are hook-driven; 3:00-4:30",
            "House music — vocal is a hook loop, not a story. Low lyrical complexity, max earworm."
        ),
        (
            "electronic.techno", 25, 20, 85, 80, 15, 80, 125, 140,
            "minor_default", "flirty_edge", "timeless",
            [],
            ["kick drum", "hi-hats", "synth bass", "atmospheric pads"],
            "Long instrumental arrangement, minimal vocal, 4:00-7:00",
            "Techno — mostly instrumental, vocals are atmospheric. Low meme, low edge."
        ),
        (
            "electronic.hyperpop", 85, 80, 95, 95, 40, 100, 130, 180,
            "mixed", "savage_edge", "gen_z",
            ["tiktok_phrase", "tiktok_sound", "gaming", "viral_meme", "slang"],
            ["glitched drums", "pitched vocals", "distorted synth", "chopped samples"],
            "Chaotic structure, 1:30-2:30, maximum density",
            "Hyperpop (SOPHIE, 100 gecs, Dorian Electra) — maxes everything. Internet native, maximum meme, maximum edginess."
        ),
        (
            "rock", 60, 25, 80, 50, 60, 55, 95, 150,
            "minor_default", "savage_edge", "timeless",
            ["brand", "news_event"],
            ["electric guitar", "bass", "rock drums", "vocal grit"],
            "Verse-chorus-verse-chorus-solo-chorus, 3:00-4:00",
            "Modern rock (Tyler Childers edge, Wolf Alice, Fontaines DC) — tolerates named-target takes but not TikTok slang."
        ),
        (
            "classical", 10, 0, 60, 60, 90, 10, 60, 140,
            "mixed", "clean_edge", "timeless",
            [],
            ["strings", "piano", "woodwinds", "brass"],
            "Classical forms — sonata, rondo, through-composed. Variable length.",
            "Classical is instrumental first — skip most of the edge/meme/earworm pipeline. Structural rigor matters more."
        ),
    ]

    conn = op.get_bind()
    insert_stmt = sa.text("""
        INSERT INTO genre_traits (
            genre_id, edginess, meme_density, earworm_demand,
            sonic_experimentation, lyrical_complexity, vocal_processing,
            tempo_range_bpm, key_mood, default_edge_profile, vocabulary_era,
            pop_culture_sources, instrumentation_palette,
            structural_conventions, notes, updated_by, is_system_default
        ) VALUES (
            :genre_id, :edginess, :meme_density, :earworm,
            :sonic_exp, :lyr_cmplx, :vocal_proc,
            :tempo_range, :key_mood, :edge, :era,
            :pop_sources, :instr_palette,
            :structural, :notes, 'seed_020', TRUE
        )
        ON CONFLICT (genre_id) DO NOTHING
    """)
    for row in seed_rows:
        (
            genre_id, edginess, meme_density, earworm, sonic_exp, lyr_cmplx,
            vocal_proc, tempo_min, tempo_max, key_mood, edge, era,
            pop_sources, instr_palette, structural, notes,
        ) = row
        conn.execute(
            insert_stmt,
            {
                "genre_id": genre_id,
                "edginess": edginess,
                "meme_density": meme_density,
                "earworm": earworm,
                "sonic_exp": sonic_exp,
                "lyr_cmplx": lyr_cmplx,
                "vocal_proc": vocal_proc,
                "tempo_range": [tempo_min, tempo_max],
                "key_mood": key_mood,
                "edge": edge,
                "era": era,
                "pop_sources": pop_sources,
                "instr_palette": instr_palette,
                "structural": structural,
                "notes": notes,
            },
        )


def downgrade() -> None:
    op.drop_constraint("ck_genre_traits_era", "genre_traits", type_="check")
    op.drop_constraint("ck_genre_traits_key_mood", "genre_traits", type_="check")
    op.drop_constraint("ck_genre_traits_edge", "genre_traits", type_="check")
    op.drop_constraint("ck_genre_traits_scores", "genre_traits", type_="check")
    op.drop_table("genre_traits")
