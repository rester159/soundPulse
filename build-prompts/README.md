# SoundPulse — Build Kit

> Everything needed to build SoundPulse from scratch using Claude Code.

---

## What's In This Kit

### Claude Code Prompts (paste directly into Claude Code)

| File | What It Builds | Lines | Tokens (~) |
|------|----------------|-------|------------|
| `CLAUDE_CODE_PROMPT.md` | **Master prompt.** Full API + DB + scrapers + prediction + frontend + Docker. All 7 phases, sequenced build order. | ~700 | ~8K |
| `CLAUDE_CODE_SCRAPERS_PROMPT.md` | Scraper layer only. Base class, all 7 platform scrapers, fallback chains, Celery schedule, health monitoring. | ~550 | ~6K |
| `CLAUDE_CODE_CREDENTIALS_PROMPT.md` | Interactive CLI wizard for obtaining all API keys. Verification functions, cost breakdown. | ~450 | ~5K |
| `CLAUDE_CODE_FRONTEND_PROMPT.md` | React dashboard. 3 pages (Dashboard, Explore, API Tester), hooks, endpoint definitions, design spec. | ~400 | ~4K |
| `CLAUDE_CODE_PREDICTION_TESTING_PROMPT.md` | 6-layer testing framework. Unit tests, integration tests, backtesting, shadow mode, drift detection, failure analysis, 26-week roadmap. | ~650 | ~7K |
| `CLAUDE_CODE_GENRE_TAXONOMY_PROMPT.md` | 850+ genre taxonomy. All 12 root trees, cross-platform mappings, adjacency graph, audio profiles. | ~500 | ~5K |

### API Documentation (reference material)

| File | Audience | Content |
|------|----------|---------|
| `API_DOCS_HIGH_LEVEL.md` | Stakeholders, README, onboarding | What SoundPulse is, endpoints overview, auth, architecture, quick start |
| `API_DOCS_LOW_LEVEL.md` | Claude Code (ingest as context) | Every field on every endpoint, entity resolution logic, normalization formulas, all signal schemas, DB indexes, prediction features |

---

## Recommended Build Sequence

### Option A: Full Build (give Claude Code the master prompt)

1. Open Claude Code
2. Paste the entire contents of `CLAUDE_CODE_PROMPT.md`
3. Also paste `API_DOCS_LOW_LEVEL.md` as reference context
4. Let it build phases 1-7 sequentially
5. When scrapers need credentials, run `CLAUDE_CODE_CREDENTIALS_PROMPT.md` separately

### Option B: Modular Build (one piece at a time)

This gives you more control and is recommended for a system this large.

```
Step 1: API + Database
  → Use CLAUDE_CODE_PROMPT.md (Phase 0-1 only)
  → Reference: API_DOCS_LOW_LEVEL.md

Step 2: Genre Taxonomy
  → Use CLAUDE_CODE_GENRE_TAXONOMY_PROMPT.md
  
Step 3: Get API Keys
  → Use CLAUDE_CODE_CREDENTIALS_PROMPT.md
  
Step 4: Scrapers
  → Use CLAUDE_CODE_SCRAPERS_PROMPT.md
  
Step 5: Prediction Engine
  → Use CLAUDE_CODE_PROMPT.md (Phase 5 only)
  → Then: CLAUDE_CODE_PREDICTION_TESTING_PROMPT.md
  
Step 6: Frontend
  → Use CLAUDE_CODE_FRONTEND_PROMPT.md
```

### Option C: MVP First

Fastest path to a working demo:

1. Database + API (Phase 0-1 from master prompt)
2. Spotify scraper only (from scrapers prompt, just the Spotify section)
3. Frontend (from frontend prompt)
4. → You now have a working API with Spotify data and a testing dashboard
5. Add more scrapers one by one
6. Add prediction engine last

---

## Minimum Viable Cost

| Item | Monthly Cost |
|------|-------------|
| Spotify API | $0 |
| Chartmetric Starter | $150 |
| Shazam (RapidAPI Pro) | $10 |
| Apple Developer Account | ~$8 |
| MusicBrainz | $0 |
| TikTok Research API | $0 (if approved) |
| **Total** | **~$168/month** |

Infrastructure (when deploying beyond local):
- Railway / Render: ~$25/month for API + DB + Redis
- Or AWS/GCP: varies

---

## Key Design Decisions Already Made

These are baked into the prompts — Claude Code should NOT ask about them:

- **Language**: Python 3.12 + FastAPI
- **Database**: PostgreSQL 16 + SQLAlchemy async
- **Cache**: Redis 7
- **Task Queue**: Celery + Redis
- **Frontend**: React 18 + Vite + Tailwind
- **ML Stack**: LightGBM + PyTorch (LSTM) + XGBoost + scikit-learn (Ridge, Isotonic)
- **Containers**: Docker Compose
- **Auth**: API key in header (not OAuth — simpler for an internal/B2B tool)
- **Genre IDs**: Dot-notation strings, not integers
- **Entity IDs**: UUIDs
- **Scoring**: 0-100 normalized scale, weighted composite
