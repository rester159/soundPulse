# SoundPulse Genre Taxonomy — Claude Code Build Prompt

> **Build the full genre taxonomy: 850+ genres, 12 root categories, dot-notation IDs, cross-platform mappings, adjacency graph, audio profiles.**
> Output: `shared/genre_taxonomy.py` + `scripts/seed_genres.py`

---

## STRUCTURE

Each genre is a dict:
```python
{
    "id": "electronic.house.tech-house",       # dot-notation, URL-safe
    "name": "Tech House",                       # display name
    "parent_id": "electronic.house",            # None for roots
    "root_category": "electronic",
    "depth": 2,                                 # 0=root, 1, 2, 3 max
    "spotify_genres": ["tech house", "minimal tech house"],
    "apple_music_genres": ["Tech House"],
    "musicbrainz_tags": ["tech house"],
    "chartmetric_genres": ["Tech House"],
    "audio_profile": {
        "tempo_range": [120, 130],
        "energy_range": [0.6, 0.85],
        "valence_range": [0.3, 0.7],
        "danceability_range": [0.7, 0.9],
    },
    "adjacent_genres": ["electronic.house.deep-house", "electronic.techno.minimal-techno"],
    "status": "active",
}
```

---

## THE 12 ROOT CATEGORIES

Build the taxonomy by expanding each root. Below is the skeleton with key subgenres to include. Claude Code should fill gaps intelligently — use Spotify's genre list, MusicBrainz tag database, and common music classification knowledge to reach 850+ total.

### 1. POP (id: `pop`)
```
pop
├── pop.dance-pop
├── pop.synth-pop
│   └── pop.synth-pop.electropop
├── pop.art-pop
├── pop.indie-pop
│   ├── pop.indie-pop.bedroom-pop
│   └── pop.indie-pop.dream-pop
├── pop.chamber-pop
├── pop.bubblegum-pop
├── pop.teen-pop
├── pop.power-pop
├── pop.baroque-pop
├── pop.sophisti-pop
├── pop.jangle-pop
├── pop.noise-pop
├── pop.twee-pop
├── pop.k-pop
│   ├── pop.k-pop.k-pop-boy-group
│   ├── pop.k-pop.k-pop-girl-group
│   └── pop.k-pop.k-pop-soloist
├── pop.j-pop
├── pop.c-pop
│   ├── pop.c-pop.mandopop
│   └── pop.c-pop.cantopop
├── pop.latin-pop (adjacent → latin.pop-latino)
├── pop.euro-pop
│   ├── pop.euro-pop.italo-disco
│   └── pop.euro-pop.schlager
├── pop.pop-rock (adjacent → rock.pop-rock)
├── pop.pop-rap (adjacent → hip-hop.pop-rap)
└── pop.dark-pop
```

### 2. ROCK (id: `rock`)
```
rock
├── rock.alternative
│   ├── rock.alternative.indie-rock
│   │   ├── rock.alternative.indie-rock.lo-fi-indie
│   │   ├── rock.alternative.indie-rock.math-rock
│   │   └── rock.alternative.indie-rock.midwest-emo
│   ├── rock.alternative.shoegaze
│   ├── rock.alternative.post-punk
│   │   └── rock.alternative.post-punk.darkwave
│   ├── rock.alternative.grunge
│   ├── rock.alternative.britpop
│   └── rock.alternative.noise-rock
├── rock.classic-rock
│   ├── rock.classic-rock.blues-rock
│   ├── rock.classic-rock.psychedelic-rock
│   ├── rock.classic-rock.progressive-rock
│   └── rock.classic-rock.southern-rock
├── rock.hard-rock
│   └── rock.hard-rock.glam-rock
├── rock.metal
│   ├── rock.metal.heavy-metal
│   ├── rock.metal.thrash-metal
│   ├── rock.metal.death-metal
│   │   ├── rock.metal.death-metal.melodic-death-metal
│   │   └── rock.metal.death-metal.technical-death-metal
│   ├── rock.metal.black-metal
│   │   └── rock.metal.black-metal.atmospheric-black-metal
│   ├── rock.metal.doom-metal
│   │   └── rock.metal.doom-metal.stoner-metal
│   ├── rock.metal.power-metal
│   ├── rock.metal.symphonic-metal
│   ├── rock.metal.nu-metal
│   ├── rock.metal.metalcore
│   │   └── rock.metal.metalcore.deathcore
│   ├── rock.metal.djent
│   └── rock.metal.post-metal
├── rock.punk
│   ├── rock.punk.hardcore-punk
│   │   └── rock.punk.hardcore-punk.straight-edge
│   ├── rock.punk.pop-punk
│   ├── rock.punk.skate-punk
│   ├── rock.punk.post-hardcore
│   │   └── rock.punk.post-hardcore.screamo
│   └── rock.punk.emo
├── rock.post-rock
├── rock.garage-rock
├── rock.surf-rock
├── rock.folk-rock (adjacent → country.folk)
├── rock.pop-rock (adjacent → pop.pop-rock)
└── rock.stoner-rock
```

### 3. ELECTRONIC (id: `electronic`)
```
electronic
├── electronic.house
│   ├── electronic.house.deep-house
│   │   └── electronic.house.deep-house.organic-house
│   ├── electronic.house.tech-house
│   │   ├── electronic.house.tech-house.afro-tech
│   │   └── electronic.house.tech-house.minimal-tech-house
│   ├── electronic.house.progressive-house
│   │   └── electronic.house.progressive-house.melodic-house
│   ├── electronic.house.afro-house (adjacent → african.afrobeats)
│   ├── electronic.house.electro-house
│   ├── electronic.house.acid-house
│   ├── electronic.house.chicago-house
│   ├── electronic.house.uk-garage
│   │   └── electronic.house.uk-garage.speed-garage
│   ├── electronic.house.bass-house
│   ├── electronic.house.future-house
│   ├── electronic.house.tropical-house
│   ├── electronic.house.piano-house
│   └── electronic.house.jackin-house
├── electronic.techno
│   ├── electronic.techno.minimal-techno
│   ├── electronic.techno.industrial-techno
│   ├── electronic.techno.detroit-techno
│   ├── electronic.techno.acid-techno
│   ├── electronic.techno.hard-techno
│   ├── electronic.techno.dub-techno
│   ├── electronic.techno.melodic-techno
│   └── electronic.techno.peak-time-techno
├── electronic.trance
│   ├── electronic.trance.progressive-trance
│   ├── electronic.trance.psytrance
│   │   ├── electronic.trance.psytrance.full-on
│   │   ├── electronic.trance.psytrance.darkpsy
│   │   └── electronic.trance.psytrance.forest
│   ├── electronic.trance.uplifting-trance
│   ├── electronic.trance.vocal-trance
│   └── electronic.trance.tech-trance
├── electronic.drum-and-bass
│   ├── electronic.drum-and-bass.liquid-dnb
│   ├── electronic.drum-and-bass.neurofunk
│   ├── electronic.drum-and-bass.jungle
│   └── electronic.drum-and-bass.jump-up
├── electronic.dubstep
│   ├── electronic.dubstep.brostep
│   ├── electronic.dubstep.riddim
│   └── electronic.dubstep.melodic-dubstep
├── electronic.ambient
│   ├── electronic.ambient.dark-ambient
│   ├── electronic.ambient.space-ambient
│   └── electronic.ambient.drone
├── electronic.idm
├── electronic.breakbeat
│   ├── electronic.breakbeat.big-beat
│   └── electronic.breakbeat.breaks
├── electronic.downtempo
│   ├── electronic.downtempo.trip-hop
│   ├── electronic.downtempo.chillout
│   └── electronic.downtempo.lo-fi-beats (adjacent → hip-hop.lo-fi-hip-hop)
├── electronic.edm
│   ├── electronic.edm.big-room
│   ├── electronic.edm.future-bass
│   ├── electronic.edm.hardstyle
│   │   └── electronic.edm.hardstyle.rawstyle
│   └── electronic.edm.festival-progressive
├── electronic.synthwave
│   ├── electronic.synthwave.retrowave
│   └── electronic.synthwave.darksynth
├── electronic.experimental-electronic
│   ├── electronic.experimental-electronic.glitch
│   └── electronic.experimental-electronic.vaporwave
├── electronic.garage
│   ├── electronic.garage.2-step
│   └── electronic.garage.bassline
├── electronic.uk-bass
│   ├── electronic.uk-bass.grime (adjacent → hip-hop.grime)
│   └── electronic.uk-bass.uk-funky
└── electronic.eurodance
```

### 4. HIP-HOP (id: `hip-hop`)
```
hip-hop
├── hip-hop.trap
│   ├── hip-hop.trap.melodic-trap
│   ├── hip-hop.trap.drill
│   │   ├── hip-hop.trap.drill.uk-drill
│   │   ├── hip-hop.trap.drill.chicago-drill
│   │   └── hip-hop.trap.drill.brooklyn-drill
│   ├── hip-hop.trap.southern-trap
│   └── hip-hop.trap.plugg
├── hip-hop.boom-bap
│   ├── hip-hop.boom-bap.east-coast
│   └── hip-hop.boom-bap.jazz-rap (adjacent → jazz.jazz-fusion.jazz-rap)
├── hip-hop.conscious-rap
├── hip-hop.gangsta-rap
│   └── hip-hop.gangsta-rap.west-coast
├── hip-hop.cloud-rap
├── hip-hop.emo-rap
├── hip-hop.lo-fi-hip-hop (adjacent → electronic.downtempo.lo-fi-beats)
├── hip-hop.mumble-rap
├── hip-hop.phonk
│   ├── hip-hop.phonk.drift-phonk
│   └── hip-hop.phonk.brazilian-phonk
├── hip-hop.pop-rap (adjacent → pop.pop-rap)
├── hip-hop.underground-hip-hop
│   └── hip-hop.underground-hip-hop.abstract-hip-hop
├── hip-hop.grime (adjacent → electronic.uk-bass.grime)
├── hip-hop.crunk
├── hip-hop.hyphy
├── hip-hop.dirty-south
├── hip-hop.chopped-and-screwed
├── hip-hop.freestyle-rap
├── hip-hop.latin-hip-hop (adjacent → latin.reggaeton)
└── hip-hop.afro-hip-hop (adjacent → african.afrobeats)
```

### 5. R-AND-B (id: `r-and-b`)
```
r-and-b
├── r-and-b.contemporary-rnb
│   ├── r-and-b.contemporary-rnb.alternative-rnb
│   ├── r-and-b.contemporary-rnb.pnb-rnb
│   └── r-and-b.contemporary-rnb.dark-rnb
├── r-and-b.classic-rnb
│   ├── r-and-b.classic-rnb.motown
│   └── r-and-b.classic-rnb.philly-soul
├── r-and-b.neo-soul
├── r-and-b.soul
│   ├── r-and-b.soul.northern-soul
│   └── r-and-b.soul.southern-soul
├── r-and-b.funk
│   ├── r-and-b.funk.p-funk
│   ├── r-and-b.funk.electro-funk
│   └── r-and-b.funk.go-go
├── r-and-b.gospel
│   └── r-and-b.gospel.contemporary-gospel
├── r-and-b.quiet-storm
├── r-and-b.new-jack-swing
├── r-and-b.blues
│   ├── r-and-b.blues.delta-blues
│   ├── r-and-b.blues.chicago-blues
│   ├── r-and-b.blues.electric-blues
│   └── r-and-b.blues.modern-blues
└── r-and-b.disco
    ├── r-and-b.disco.nu-disco (adjacent → electronic.house)
    └── r-and-b.disco.italo-disco
```

### 6. LATIN (id: `latin`)
```
latin
├── latin.reggaeton
│   ├── latin.reggaeton.old-school-reggaeton
│   └── latin.reggaeton.perreo
├── latin.latin-trap
├── latin.pop-latino
├── latin.bachata
├── latin.salsa
│   ├── latin.salsa.salsa-dura
│   └── latin.salsa.salsa-romantica
├── latin.cumbia
│   ├── latin.cumbia.cumbia-villera
│   ├── latin.cumbia.digital-cumbia
│   └── latin.cumbia.cumbia-sonidera
├── latin.merengue
├── latin.dembow
├── latin.bossa-nova (adjacent → jazz.bossa-nova)
├── latin.samba
│   └── latin.samba.pagode
├── latin.forro
├── latin.sertanejo
├── latin.mpb
├── latin.ranchera
├── latin.banda
├── latin.norteno
├── latin.corridos
│   └── latin.corridos.corridos-tumbados
├── latin.vallenato
├── latin.tango
├── latin.bolero
├── latin.reggaeton-romantico
├── latin.latin-rock
├── latin.latin-jazz (adjacent → jazz.latin-jazz)
├── latin.funk-carioca (adjacent → hip-hop.phonk.brazilian-phonk)
└── latin.urbano
```

### 7. COUNTRY (id: `country`)
```
country
├── country.contemporary-country
│   ├── country.contemporary-country.bro-country
│   └── country.contemporary-country.country-pop
├── country.traditional-country
│   ├── country.traditional-country.honky-tonk
│   ├── country.traditional-country.western-swing
│   └── country.traditional-country.outlaw-country
├── country.country-rock
├── country.americana
│   ├── country.americana.alt-country
│   └── country.americana.roots-rock
├── country.bluegrass
│   ├── country.bluegrass.progressive-bluegrass
│   └── country.bluegrass.newgrass
├── country.folk
│   ├── country.folk.indie-folk
│   ├── country.folk.contemporary-folk
│   ├── country.folk.anti-folk
│   └── country.folk.folk-punk
├── country.singer-songwriter
├── country.red-dirt
├── country.texas-country
└── country.country-rap
```

### 8. JAZZ (id: `jazz`)
```
jazz
├── jazz.bebop
├── jazz.hard-bop
├── jazz.cool-jazz
├── jazz.modal-jazz
├── jazz.free-jazz
├── jazz.smooth-jazz
├── jazz.jazz-fusion
│   ├── jazz.jazz-fusion.jazz-rock
│   ├── jazz.jazz-fusion.jazz-funk
│   └── jazz.jazz-fusion.jazz-rap (adjacent → hip-hop.boom-bap.jazz-rap)
├── jazz.swing
│   └── jazz.swing.electro-swing
├── jazz.latin-jazz (adjacent → latin.latin-jazz)
├── jazz.bossa-nova (adjacent → latin.bossa-nova)
├── jazz.acid-jazz
├── jazz.nu-jazz
├── jazz.spiritual-jazz
├── jazz.big-band
├── jazz.dixieland
├── jazz.vocal-jazz
├── jazz.avant-garde-jazz
├── jazz.chamber-jazz
└── jazz.contemporary-jazz
```

### 9. CLASSICAL (id: `classical`)
```
classical
├── classical.orchestral
│   ├── classical.orchestral.symphonic
│   ├── classical.orchestral.concerto
│   └── classical.orchestral.overture
├── classical.chamber-music
│   ├── classical.chamber-music.string-quartet
│   ├── classical.chamber-music.piano-trio
│   └── classical.chamber-music.wind-quintet
├── classical.opera
│   ├── classical.opera.italian-opera
│   ├── classical.opera.german-opera
│   └── classical.opera.contemporary-opera
├── classical.choral
│   ├── classical.choral.sacred-choral
│   └── classical.choral.secular-choral
├── classical.solo-instrument
│   ├── classical.solo-instrument.piano-solo
│   ├── classical.solo-instrument.guitar-classical
│   └── classical.solo-instrument.organ
├── classical.contemporary-classical
│   ├── classical.contemporary-classical.minimalism
│   ├── classical.contemporary-classical.spectral
│   └── classical.contemporary-classical.post-minimalism
├── classical.film-score
├── classical.baroque
├── classical.romantic
├── classical.neoclassical
├── classical.early-music
│   ├── classical.early-music.medieval
│   └── classical.early-music.renaissance
└── classical.crossover-classical
```

### 10. AFRICAN (id: `african`)
```
african
├── african.afrobeats (adjacent → electronic.house.afro-house)
│   ├── african.afrobeats.afro-pop
│   ├── african.afrobeats.afro-fusion
│   └── african.afrobeats.alté
├── african.amapiano
│   ├── african.amapiano.deep-amapiano
│   └── african.amapiano.vocal-amapiano
├── african.afro-soul
├── african.highlife
│   └── african.highlife.modern-highlife
├── african.gqom
├── african.kwaito
├── african.afro-house (adjacent → electronic.house.afro-house)
├── african.bongo-flava
├── african.gengetone
├── african.coupé-décalé
├── african.kuduro
├── african.mbalax
├── african.soukous
├── african.juju
├── african.makossa
├── african.gnawa
├── african.desert-blues
├── african.ethio-jazz
└── african.rai
```

### 11. ASIAN (id: `asian`)
```
asian
├── asian.k-pop (maps to → pop.k-pop, used as cross-reference)
├── asian.j-pop (maps to → pop.j-pop)
├── asian.j-rock
│   └── asian.j-rock.visual-kei
├── asian.c-pop (maps to → pop.c-pop)
├── asian.bollywood
│   ├── asian.bollywood.filmi
│   └── asian.bollywood.indi-pop
├── asian.qawwali
├── asian.bhangra
├── asian.enka
├── asian.city-pop
├── asian.anime-ost
├── asian.thai-pop
├── asian.pinoy-pop
├── asian.v-pop
├── asian.indo-pop
├── asian.turkish-pop
├── asian.turkish-folk
├── asian.arabic-pop (adjacent → african.rai)
└── asian.persian-pop
```

### 12. CARIBBEAN (id: `caribbean`)
```
caribbean
├── caribbean.reggae
│   ├── caribbean.reggae.roots-reggae
│   ├── caribbean.reggae.dub
│   │   └── caribbean.reggae.dub.digital-dub
│   ├── caribbean.reggae.dancehall
│   │   └── caribbean.reggae.dancehall.modern-dancehall
│   ├── caribbean.reggae.lovers-rock
│   └── caribbean.reggae.ragga
├── caribbean.soca
│   ├── caribbean.soca.power-soca
│   └── caribbean.soca.groovy-soca
├── caribbean.calypso
├── caribbean.kompa
├── caribbean.zouk
├── caribbean.chutney
├── caribbean.bouyon
└── caribbean.afroswing (adjacent → african.afrobeats)
```

---

## ADJACENCY GRAPH RULES

Adjacency relationships are **bidirectional**. When you define:
```
"electronic.house.afro-house" → adjacent → "african.afrobeats"
```
Also ensure:
```
"african.afrobeats" → adjacent → "electronic.house.afro-house"
```

Key cross-branch relationships to encode:
- `electronic.downtempo.lo-fi-beats` ↔ `hip-hop.lo-fi-hip-hop`
- `electronic.house.afro-house` ↔ `african.afrobeats` ↔ `african.amapiano`
- `jazz.jazz-fusion.jazz-rap` ↔ `hip-hop.boom-bap.jazz-rap`
- `latin.bossa-nova` ↔ `jazz.bossa-nova`
- `pop.k-pop` ↔ `asian.k-pop`
- `rock.folk-rock` ↔ `country.folk`
- `electronic.uk-bass.grime` ↔ `hip-hop.grime`
- `r-and-b.disco.nu-disco` ↔ `electronic.house`
- `hip-hop.phonk.brazilian-phonk` ↔ `latin.funk-carioca`
- `caribbean.afroswing` ↔ `african.afrobeats`
- `pop.latin-pop` ↔ `latin.pop-latino`

---

## AUDIO PROFILES

Set reasonable ranges per genre. Here are key reference points:

| Genre | Tempo (BPM) | Energy (0-1) | Valence (0-1) | Danceability (0-1) |
|-------|-------------|--------------|----------------|---------------------|
| electronic.house | 120-130 | 0.6-0.85 | 0.3-0.7 | 0.7-0.9 |
| electronic.techno | 125-145 | 0.7-0.95 | 0.1-0.4 | 0.6-0.85 |
| electronic.drum-and-bass | 165-180 | 0.8-0.95 | 0.2-0.5 | 0.5-0.7 |
| hip-hop.trap | 130-170 | 0.5-0.8 | 0.2-0.5 | 0.6-0.85 |
| hip-hop.boom-bap | 85-100 | 0.5-0.7 | 0.3-0.6 | 0.7-0.85 |
| pop.dance-pop | 110-130 | 0.7-0.9 | 0.5-0.8 | 0.7-0.9 |
| rock.metal | 100-200 | 0.8-1.0 | 0.1-0.4 | 0.3-0.5 |
| jazz.bebop | 160-320 | 0.5-0.8 | 0.4-0.7 | 0.3-0.5 |
| classical.orchestral | 60-160 | 0.2-0.8 | 0.2-0.6 | 0.1-0.3 |
| african.amapiano | 110-120 | 0.5-0.7 | 0.5-0.8 | 0.7-0.9 |
| latin.reggaeton | 90-100 | 0.6-0.85 | 0.5-0.8 | 0.7-0.9 |
| country.contemporary-country | 90-140 | 0.5-0.8 | 0.5-0.8 | 0.5-0.7 |
| r-and-b.contemporary-rnb | 70-110 | 0.3-0.6 | 0.3-0.6 | 0.5-0.75 |

Child genres should inherit parent ranges and narrow them. Claude Code should interpolate sensible ranges for genres not listed here.

---

## IMPLEMENTATION

### `shared/genre_taxonomy.py`

Generate the full list as a Python constant: `GENRE_TAXONOMY: list[dict]`

Each dict follows the schema above. The total count should be 850+. Use the trees above as the skeleton and fill in subgenres to reach the target count. Prioritize depth in:
- Electronic (most subgenre-rich)
- Hip-hop (rapidly evolving)
- Latin (growing fast globally)
- African (Afrobeats/Amapiano explosion)

### `scripts/seed_genres.py`

```python
"""
Load genre taxonomy into database.
Idempotent — can be run multiple times safely (upsert by ID).
"""

from shared.genre_taxonomy import GENRE_TAXONOMY
from api.models.genre import Genre
from api.dependencies import get_db

async def seed_genres():
    async with get_db() as db:
        for genre_data in GENRE_TAXONOMY:
            existing = await db.get(Genre, genre_data["id"])
            if existing:
                # Update fields
                for key, value in genre_data.items():
                    setattr(existing, key, value)
            else:
                db.add(Genre(**genre_data))
        await db.commit()
    
    print(f"Seeded {len(GENRE_TAXONOMY)} genres")

if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_genres())
```
