# SoundPulse — Step-by-Step Build Playbook

> Follow these steps in order. Each step = one Claude Code session.
> Don't skip ahead. Each step depends on the previous one working.

---

## BEFORE YOU START

1. Create a project folder on your machine:
   ```bash
   mkdir soundpulse && cd soundpulse
   ```

2. Make sure you have installed:
   - Docker Desktop (for PostgreSQL + Redis)
   - Node.js 20+ (for frontend)
   - Python 3.12+ (for API)

3. Download all 12 files from the kit into a folder called `build-prompts/`

---

## STEP 1: Get Your API Keys
**Time: ~30 minutes of signup work**
**Claude Code session: not needed yet**

Do this FIRST because some keys take time (TikTok = weeks).

Open `API_CREDENTIALS_GUIDE.md` — it has every provider, signup URL, exact fields to copy, costs, and test commands. Follow it provider by provider:

1. **Spotify** → https://developer.spotify.com/dashboard → Create app → Copy Client ID + Secret
2. **Chartmetric** → https://chartmetric.com/pricing → Sign up for Starter ($150/mo) → Get API key
3. **Shazam** → https://rapidapi.com/apidojo/api/shazam → Subscribe to Pro ($10/mo) → Copy RapidAPI key
4. **Apple Music** → https://developer.apple.com → Create MusicKit key → Download .p8 file
5. **TikTok** → https://developers.tiktok.com/products/research-api/ → Apply (takes 2-6 weeks)
6. **MusicBrainz** → Nothing to do (no key needed)
7. **Luminate** → Skip for now (we'll use Billboard scraping as fallback)

Save all keys somewhere safe. You'll plug them in during Step 5.

**Minimum to proceed: Spotify key.** Everything else can come later.

---

## STEP 2: Build the API + Database
**Claude Code Session #1**

This is the foundation. Nothing else works without it.

**What to paste into Claude Code:**

> Paste the following into Claude Code as your prompt. Then paste the contents of two files after it:

```
I'm building SoundPulse, a music intelligence API. 

Build Phase 0 (project scaffold + Docker) and Phase 1 (database + API endpoints) 
from the spec below. Stop after Phase 1 — don't build scrapers or prediction yet.

Start with:
1. Docker Compose (Postgres + Redis + API)
2. SQLAlchemy models + Alembic migrations
3. All 6 API endpoints (genres, trending, search, predictions)
4. Entity resolution service
5. Normalization + composite scoring services
6. Rate limiting + API key auth middleware
7. Basic tests

Here's the full spec:

[PASTE THE ENTIRE CONTENTS OF CLAUDE_CODE_PROMPT.md HERE]

And here's the detailed endpoint reference:

[PASTE THE ENTIRE CONTENTS OF API_DOCS_LOW_LEVEL.md HERE]
```

**What you should have when done:**
- `docker compose up` starts Postgres, Redis, and the API
- `curl http://localhost:8000/api/v1/genres` returns a response (empty, but 200 OK)
- `curl http://localhost:8000/api/v1/trending?entity_type=track` returns empty results
- All migrations run clean
- Basic test suite passes

**Verify before moving on:**
```bash
docker compose up -d
curl -s http://localhost:8000/docs  # FastAPI auto-docs should load
```

---

## STEP 3: Seed the Genre Taxonomy
**Claude Code Session #2**

Now we fill the database with the 850+ genre taxonomy.

**What to paste into Claude Code:**

```
I have a running SoundPulse API (FastAPI + Postgres). 
The Genre model is already in the database.

Build the full genre taxonomy and seed script from this spec.
Generate shared/genre_taxonomy.py with 850+ genres and 
scripts/seed_genres.py to load them into the database.

[PASTE THE ENTIRE CONTENTS OF CLAUDE_CODE_GENRE_TAXONOMY_PROMPT.md HERE]
```

**What you should have when done:**
- `shared/genre_taxonomy.py` with 850+ genre entries
- `python scripts/seed_genres.py` loads them all
- `curl http://localhost:8000/api/v1/genres` returns the full tree
- `curl http://localhost:8000/api/v1/genres/electronic.house.tech-house` returns genre detail with platform mappings

**Verify before moving on:**
```bash
python scripts/seed_genres.py
curl -s -H "X-API-Key: YOUR_ADMIN_KEY" http://localhost:8000/api/v1/genres | python -m json.tool | head -20
```

---

## STEP 4: Build the Genre Classifier
**Claude Code Session #3**

This is the intelligence that maps every track/artist to your proprietary taxonomy. Without this, entities only get whatever generic labels upstream platforms give them. With this, every entity gets classified into your 850-genre system using 6 signals.

**What to paste into Claude Code:**

```
I have a running SoundPulse API with the 850+ genre taxonomy seeded.
Right now, tracks and artists have no genre classification beyond 
whatever raw labels upstream platforms provide.

Build the multi-signal genre classification engine that maps every 
entity to our proprietary taxonomy. It should:
1. Create api/services/genre_classifier.py
2. Use 6 signals: platform label mapping, audio feature matching, 
   artist inheritance, playlist context, social tags, neighbor inference
3. Score every candidate genre, prefer specific over broad, resolve hierarchy
4. Wire it into POST /trending so entities get classified on creation
5. Re-classify when entities get data from new platforms
6. Add a weekly task to re-classify "low" quality entities
7. Include tests

[PASTE THE ENTIRE CONTENTS OF CLAUDE_CODE_GENRE_CLASSIFIER_PROMPT.md HERE]
```

**What you should have when done:**
- `api/services/genre_classifier.py` with the full multi-signal engine
- New entities created via POST /trending automatically get classified
- Classification includes a quality score ("high", "medium", "low")
- Entities get re-classified when new platform data arrives
- `GET /trending` responses show proper SoundPulse genre IDs (not raw platform labels)

**Verify before moving on:**
```bash
# After running a scraper (Step 5), check that entities have genre assignments:
curl -s -H "X-API-Key: YOUR_KEY" "http://localhost:8000/api/v1/trending?entity_type=track&limit=3" | python -m json.tool | grep genres
# Should show dot-notation genre IDs like "pop.dance-pop", not raw strings like "dance pop"
```

**Note:** Full verification happens after Step 5 when real data is flowing. The classifier needs entities with metadata to classify — so you'll see it in action once the Spotify scraper runs.

---

## STEP 5: Build the Spotify Scraper (First Data)
**Claude Code Session #4**

Start with just Spotify — it's the most complete API and gets data flowing fastest.

**What to paste into Claude Code:**

```
I have a running SoundPulse API with the genre taxonomy seeded 
and the genre classifier built.
Now I need to start collecting data.

Build ONLY the Spotify scraper from the spec below. Include:
1. The BaseScraper abstract class
2. The SpotifyScraper implementation
3. A simple way to run it manually (CLI command)
4. Tests with mocked API responses

Make sure the scraper flow calls the genre classifier after 
entity creation/update.

My Spotify credentials:
- Client ID: [YOUR_SPOTIFY_CLIENT_ID]
- Client Secret: [YOUR_SPOTIFY_CLIENT_SECRET]

Here's the scraper spec (build only the Base class + Spotify section):

[PASTE THE ENTIRE CONTENTS OF CLAUDE_CODE_SCRAPERS_PROMPT.md HERE]
```

**What you should have when done:**
- Running `python -m scrapers.spotify` collects data from Spotify playlists
- Data appears in the trending_snapshots table
- Entities are auto-classified into SoundPulse genres
- `curl http://localhost:8000/api/v1/trending?entity_type=track` returns actual tracks with scores
- `curl http://localhost:8000/api/v1/search?q=drake` returns results

**Verify before moving on:**
```bash
python -m scrapers.spotify
curl -s -H "X-API-Key: YOUR_KEY" "http://localhost:8000/api/v1/trending?entity_type=track&limit=5" | python -m json.tool
```

**This is your first "it works!" moment.** Real Spotify data flowing through your API, classified into your proprietary genre taxonomy.

---

## STEP 6: Add Remaining Scrapers
**Claude Code Session #5**

Now add the other data sources one at a time.

**What to paste into Claude Code:**

```
SoundPulse is running with the Spotify scraper working. 
Now add the remaining scrapers, the fallback chain, and the Celery schedule.

Build in this order:
1. Chartmetric scraper (cross-platform coverage)
2. Shazam scraper via RapidAPI (critical leading indicator)
3. Apple Music scraper
4. TikTok scraper (with Chartmetric fallback since Research API may be pending)
5. MusicBrainz enricher
6. Radio/Billboard scraper
7. Fallback chain (FallbackChain class)
8. Celery beat schedule
9. Health monitoring

When an entity gets data from a NEW platform for the first time, 
trigger genre re-classification (the classifier uses cross-platform 
signals so more platforms = better classification).

My credentials:
- Chartmetric API key: [KEY]
- Shazam RapidAPI key: [KEY]
- Apple Music Team ID: [ID], Key ID: [ID], .p8 file at: ./keys/apple_music.p8
- TikTok: [pending/approved + keys if approved]

[PASTE THE ENTIRE CONTENTS OF CLAUDE_CODE_SCRAPERS_PROMPT.md HERE]
```

**What you should have when done:**
- All configured scrapers can be run manually
- `celery -A scrapers.scheduler beat` starts the automated schedule
- Health check reports which platforms are active
- Trending data comes from multiple platforms
- Composite scores reflect cross-platform weighting
- Genre classifications improve as more platform data arrives

**Verify:**
```bash
# Run each scraper manually
python -m scrapers.chartmetric
python -m scrapers.shazam

# Check multi-platform data
curl -s -H "X-API-Key: YOUR_KEY" "http://localhost:8000/api/v1/trending?entity_type=track&min_platforms=2&limit=5" | python -m json.tool
```

---

## STEP 7: Build the React Frontend
**Claude Code Session #6**

Now you get a visual interface to see and test everything.

**What to paste into Claude Code:**

```
SoundPulse API is running at http://localhost:8000 with real data from multiple platforms.

Build the React frontend from this spec. It should proxy API calls to localhost:8000.
Focus on making the API Tester page work first (most useful for debugging),
then the Dashboard, then Explore.

[PASTE THE ENTIRE CONTENTS OF CLAUDE_CODE_FRONTEND_PROMPT.md HERE]
```

**What you should have when done:**
- `http://localhost:3000` loads the dashboard with real trending data
- API Tester page lets you hit any endpoint with custom params
- Search works with autocomplete
- Genre browser shows the full taxonomy tree

**Verify:**
```bash
cd frontend && npm run dev
# Open http://localhost:3000
# Go to API Tester → select GET /trending → hit Send → see real data
```

---

## STEP 8: Build the Prediction Engine
**Claude Code Session #7**

This is the most complex piece. Only build it after you have 2+ weeks of historical data.

**Why wait?** The prediction model needs historical trending data to train on. With freshly seeded scrapers, you'll have maybe a few days. Let the scrapers run for at least 2 weeks before this step. In the meantime, the API works perfectly for trending data — predictions will just be empty.

**What to paste into Claude Code:**

```
SoundPulse API is running with 2+ weeks of historical trending data 
from multiple platforms. The database has trending_snapshots going back to [DATE].

Build the prediction engine from Phase 5 of the spec below. Include:
1. Feature engineering pipeline (~70 features)
2. LightGBM base model (start here, get it working)
3. LSTM with attention
4. XGBoost with interaction features
5. Ridge meta-learner ensemble
6. Isotonic regression confidence calibration
7. Cold start strategy
8. Daily training loop
9. Wire predictions to GET /predictions endpoint

[PASTE PHASE 5 FROM CLAUDE_CODE_PROMPT.md HERE]

Also use this detailed feature/model reference:

[PASTE THE RELEVANT SECTIONS FROM API_DOCS_LOW_LEVEL.md — 
specifically the "PREDICTION MODEL SPECIFICATION" section near the bottom]
```

**What you should have when done:**
- Running the training loop generates predictions
- `GET /predictions?horizon=7d` returns real predictions with confidence scores
- Each prediction has top_signals explaining why
- Cold start entities get capped confidence

---

## STEP 9: Add Prediction Testing Infrastructure
**Claude Code Session #8**

Make the prediction engine trustworthy and self-improving.

**What to paste into Claude Code:**

```
SoundPulse prediction engine is running and generating predictions.
Now build the testing and monitoring infrastructure.

[PASTE THE ENTIRE CONTENTS OF CLAUDE_CODE_PREDICTION_TESTING_PROMPT.md HERE]
```

**What you should have when done:**
- Full test suite for features and models
- Backtesting framework can evaluate historical accuracy
- Drift detection runs daily
- Shadow mode can run champion vs challenger
- Failure analysis classifies bad predictions
- Weekly failure report generates automatically

---

## STEP 10: Credential Setup Script (Optional Polish)
**Claude Code Session #9 (optional)**

If you want the interactive CLI for managing credentials:

```
Build the interactive credential setup wizard from this spec.
It should help new developers get all API keys configured.

[PASTE THE ENTIRE CONTENTS OF CLAUDE_CODE_CREDENTIALS_PROMPT.md HERE]
```

---

## SUMMARY: THE 9-SESSION BUILD

| Session | What You Build | Time Estimate | Depends On |
|---------|---------------|---------------|------------|
| (prep) | Get API keys manually | 30 min | Nothing |
| #1 | API + Database + Docker | 1-2 hours | API keys |
| #2 | Genre Taxonomy | 30 min | Session #1 |
| #3 | Genre Classifier | 1 hour | Session #2 |
| #4 | Spotify Scraper | 1 hour | Session #3 |
| #5 | All Other Scrapers + Celery | 1-2 hours | Session #4 |
| #6 | React Frontend | 1-2 hours | Session #1 |
| #7 | Prediction Engine | 2-3 hours | 2+ weeks of data |
| #8 | Prediction Testing | 1-2 hours | Session #7 |
| #9 | Credential Wizard (optional) | 30 min | Anytime |

**Sessions 1-6 can be done in a single day.**
Session 7 requires waiting for data to accumulate.
Sessions 6 and 4-5 can run in parallel (frontend doesn't depend on scrapers).

---

## TIPS FOR CLAUDE CODE SESSIONS

1. **One phase at a time.** Don't paste everything at once. Claude Code works better with focused tasks.

2. **Verify each step.** Before moving to the next session, actually run the code and confirm it works. Paste error messages back into Claude Code if something breaks.

3. **Keep the low-level docs handy.** If Claude Code asks a question about field names or response shapes, paste the relevant section from `API_DOCS_LOW_LEVEL.md`.

4. **Commit after each session.** `git add . && git commit -m "Phase N: description"`. This gives you rollback points.

5. **The API docs files are reference, not prompts.** Don't ask Claude Code to "build from the API docs." The docs describe what the API should look like. The CODE prompts tell Claude Code how to build it.

6. **If a session gets too long** (Claude Code seems to lose context), start a new session and say: "Continue building SoundPulse. Here's what's done: [list]. Here's what's next: [paste relevant section]."
