# SoundPulse — API Credentials Guide

> Every external API you need, how to get it, what it costs, and what it gives you.

---

## Quick Overview

| # | Provider | What It Gives SoundPulse | Cost | Signup Time | Required? |
|---|----------|--------------------------|------|-------------|-----------|
| 1 | Spotify | Stream data, playlists, audio features, artist metadata | Free | 5 min | **YES** — build this first |
| 2 | Chartmetric | Cross-platform charts (Spotify, Apple, TikTok, Shazam all in one) | $150+/mo | 10 min | **YES** — most valuable single source |
| 3 | Shazam (RapidAPI) | Discovery/recognition data — the #1 leading indicator | $10+/mo | 5 min | **YES** — critical for predictions |
| 4 | Apple Music | Apple Music chart positions, artist metadata | $99/yr | 15 min | Nice to have — Chartmetric covers this too |
| 5 | TikTok | Viral sound data, creator adoption patterns | Free | 2-6 weeks (application) | Nice to have — Chartmetric covers basics |
| 6 | MusicBrainz | ISRC codes, metadata enrichment, artist disambiguation | Free | 0 min (no signup) | Yes but no action needed |
| 7 | Luminate / Radio | Radio airplay data | Enterprise pricing | Weeks (sales process) | No — Billboard scrape covers it |

**Minimum to get started: Spotify alone (#1).** 
**Recommended minimum: Spotify + Chartmetric + Shazam (#1-3) = ~$160/month.**

---

## 1. SPOTIFY WEB API

### What SoundPulse Uses It For
- Monitoring trending playlists (Today's Top Hits, Viral 50, genre playlists)
- Track audio features (tempo, energy, valence, danceability)
- Artist metadata (followers, popularity, genres, images)
- Entity resolution (Spotify IDs as primary identifiers)

### Credentials Needed
| Field | Example | Where It Goes |
|-------|---------|---------------|
| `client_id` | `a1b2c3d4e5f6...` (32 chars) | `SPOTIFY_CLIENT_ID` env var |
| `client_secret` | `x9y8z7w6v5u4...` (32 chars) | `SPOTIFY_CLIENT_SECRET` env var |

### How to Get Them
1. Go to **https://developer.spotify.com/dashboard**
2. Log in with any Spotify account (free tier works)
3. Click **"Create app"**
4. Fill in:
   - App name: `SoundPulse`
   - App description: `Music trend intelligence`
   - Redirect URI: `http://localhost:8000/callback`
   - Which APIs: check **Web API**
5. Click **Save**
6. On the app dashboard, click **Settings**
7. Copy **Client ID** and **Client Secret** (click "View client secret" to reveal it)

### Auth Flow Used
Client Credentials (server-to-server, no user login needed):
```
POST https://accounts.spotify.com/api/token
Body: grant_type=client_credentials
Header: Authorization: Basic base64(client_id:client_secret)
→ Returns: access_token (expires in 1 hour, auto-refresh)
```

### Rate Limits
- 180 requests/minute with proper token management
- No monthly cap

### Cost
**Free.** No paid plan needed.

### Test It Works
```bash
# Get token
TOKEN=$(curl -s -X POST "https://accounts.spotify.com/api/token" \
  -H "Authorization: Basic $(echo -n 'YOUR_CLIENT_ID:YOUR_CLIENT_SECRET' | base64)" \
  -d "grant_type=client_credentials" | python -m json.tool | grep access_token)

# Hit the API
curl -s "https://api.spotify.com/v1/browse/new-releases?limit=1" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

---

## 2. CHARTMETRIC

### What SoundPulse Uses It For
- Cross-platform chart data (Spotify, Apple Music, TikTok, Shazam, YouTube) through **one API**
- Artist and track analytics across platforms
- Chartmetric's proprietary scoring
- Fills data gaps when direct APIs aren't available
- **This is the most valuable single source** — it gives you multi-platform coverage without needing every individual API

### Credentials Needed
| Field | Example | Where It Goes |
|-------|---------|---------------|
| `api_key` (refresh token) | `eyJhbGciOi...` (long JWT-like string) | `CHARTMETRIC_API_KEY` env var |

### How to Get It
1. Go to **https://chartmetric.com/pricing**
2. Choose a plan:

   | Plan | Price | API Calls/Day | Recommendation |
   |------|-------|---------------|----------------|
   | Starter | $150/mo | 2,000 | **Start here** — enough for initial build |
   | Pro | $400/mo | 10,000 | Upgrade when you need more scraping frequency |
   | Enterprise | Custom | Unlimited | Only if you're reselling the data |

3. After account activation, go to **https://app.chartmetric.com/settings/api**
4. Click **Generate API Token**
5. Copy the refresh token

### Auth Flow Used
```
POST https://api.chartmetric.com/api/token
Body: {"refreshtoken": "YOUR_API_KEY"}
→ Returns: access_token (expires in 1 hour)
```

### Rate Limits
- Starter: 100 requests/minute, 2,000/day
- Pro: 300 requests/minute, 10,000/day

### Cost
**$150/month minimum** (Starter plan).

### Test It Works
```bash
# Get access token
TOKEN=$(curl -s -X POST "https://api.chartmetric.com/api/token" \
  -H "Content-Type: application/json" \
  -d '{"refreshtoken":"YOUR_API_KEY"}' | python -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Fetch Spotify viral chart
curl -s "https://api.chartmetric.com/api/charts/spotify/viral/latest" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool | head -30
```

---

## 3. SHAZAM (via RapidAPI)

### What SoundPulse Uses It For
- Shazam chart data (most Shazamed tracks globally and by country)
- **The Shazam-to-Spotify ratio is the #1 leading indicator** in the prediction model
- Logic: a track being heavily Shazamed but not yet streaming big = people are discovering it in the wild → it's about to blow up on streaming platforms

### Credentials Needed
| Field | Example | Where It Goes |
|-------|---------|---------------|
| `rapidapi_key` | `a1b2c3d4e5...` (50+ chars) | `SHAZAM_RAPIDAPI_KEY` env var |

### How to Get It
1. Go to **https://rapidapi.com/signup** — create a RapidAPI account
2. Navigate to **https://rapidapi.com/apidojo/api/shazam**
3. Click **"Subscribe to Test"**
4. Choose a plan:

   | Plan | Price | Requests/Month | Recommendation |
   |------|-------|----------------|----------------|
   | Basic | Free | 500 | **Not enough** — only for initial testing |
   | Pro | $10/mo | 10,000 | **Start here** — 4x daily collection works |
   | Ultra | $50/mo | 100,000 | Comfortable headroom |
   | Mega | $200/mo | 1,000,000 | Overkill unless you're hitting many countries |

5. After subscribing, your API key appears in the **"Header Parameters"** section on the right side of the API page
6. Copy the value next to **X-RapidAPI-Key**

### Auth Flow Used
```
GET https://shazam.p.rapidapi.com/charts/track
Headers:
  X-RapidAPI-Key: YOUR_KEY
  X-RapidAPI-Host: shazam.p.rapidapi.com
```

### Rate Limits
- Depends on plan (see above)
- Check `X-RateLimit-Requests-Remaining` header on each response

### Cost
**$10/month minimum** (Pro plan).

### Test It Works
```bash
curl -s "https://shazam.p.rapidapi.com/charts/track?locale=en-US&pageSize=3&startFrom=0" \
  -H "X-RapidAPI-Key: YOUR_KEY" \
  -H "X-RapidAPI-Host: shazam.p.rapidapi.com" | python -m json.tool | head -30
```

---

## 4. APPLE MUSIC (MusicKit API)

### What SoundPulse Uses It For
- Apple Music chart positions across storefronts (US, UK, DE, etc.)
- Artist metadata
- Entity resolution (Apple Music IDs)

**Note:** Apple Music's API is more limited than Spotify — no stream counts, no playlist analytics, no audio features. Chartmetric already provides Apple Music chart data, so this is supplementary. You can defer this and rely on Chartmetric for Apple Music coverage.

### Credentials Needed
| Field | Example | Where It Goes |
|-------|---------|---------------|
| `team_id` | `A1B2C3D4E5` (10 chars) | `APPLE_MUSIC_TEAM_ID` env var |
| `key_id` | `ABC123DEFG` (10 chars) | `APPLE_MUSIC_KEY_ID` env var |
| `private_key_path` | `./keys/apple_music.p8` | `APPLE_MUSIC_PRIVATE_KEY_PATH` env var |

### How to Get Them
1. You need an **Apple Developer account** ($99/year)
   - Go to **https://developer.apple.com/account**
   - Enroll if you don't have one (may take 24-48h for approval)
   - If you already have one from other projects, skip this

2. Create a MusicKit key:
   - Go to **https://developer.apple.com/account/resources/authkeys/list**
   - Click **"+"** to create a new key
   - Key name: `SoundPulse MusicKit`
   - Check **"MusicKit"** under capabilities
   - Click **Continue** → **Register**
   - **Download the .p8 file** — you can only download it **ONCE**
   - Move it to your project: `./keys/apple_music.p8`
   - Note the **Key ID** shown on the page

3. Find your Team ID:
   - Go to **https://developer.apple.com/account** → **Membership details**
   - Your Team ID is listed there

### Auth Flow Used
JWT signed with ES256:
```
Header: {"alg": "ES256", "kid": "YOUR_KEY_ID"}
Payload: {"iss": "YOUR_TEAM_ID", "iat": now, "exp": now + 15777000}
Signed with: your .p8 private key
→ Use as: Authorization: Bearer {jwt_token}
```
Token is valid for ~6 months. Generate once and cache.

### Rate Limits
- Not officially documented; ~20 requests/second appears safe

### Cost
**$99/year** (~$8.25/month) for the Apple Developer account.

### Test It Works
```python
# Quick Python test (requires PyJWT + cryptography)
import jwt, time, httpx

private_key = open("./keys/apple_music.p8", "rb").read()
token = jwt.encode(
    {"iss": "YOUR_TEAM_ID", "iat": int(time.time()), "exp": int(time.time()) + 15777000},
    private_key, algorithm="ES256",
    headers={"kid": "YOUR_KEY_ID"}
)
r = httpx.get("https://api.music.apple.com/v1/catalog/us/charts?types=songs&limit=1",
              headers={"Authorization": f"Bearer {token}"})
print(r.status_code, r.json())
```

---

## 5. TIKTOK RESEARCH API

### What SoundPulse Uses It For
- Deep data on trending sounds: video counts, creator tier distribution, geographic spread
- **Creator tier migration rate** — when bigger creators start using a sound that small creators discovered, it's a breakout signal
- Geographic velocity — rapid spread across countries = viral potential

**Note:** Chartmetric provides basic TikTok chart data (trending sounds, rankings). The Research API provides the deeper signals (creator tiers, geo spread) that make predictions more accurate. You can start without it.

### Credentials Needed
| Field | Example | Where It Goes |
|-------|---------|---------------|
| `client_key` | `abcdef123456...` | `TIKTOK_CLIENT_KEY` env var |
| `client_secret` | `xyz789...` | `TIKTOK_CLIENT_SECRET` env var |

### How to Get Them
1. Go to **https://developers.tiktok.com/** and create a developer account
2. Navigate to **https://developers.tiktok.com/products/research-api/**
3. Click **"Apply for access"**
4. Fill out the application:
   - **Organization**: Your company or entity name
   - **Use case**: "Music trend analysis and prediction for industry professionals"
   - **Data usage**: "Aggregated trend data on music sound adoption patterns. No individual user data collection."
   - **Research description**: "Analyzing how music sounds spread across creator tiers and geographies to predict emerging trends"
5. Submit and wait — **approval takes 2 to 6 weeks**
6. If approved, you'll receive `client_key` and `client_secret` via email

### Auth Flow Used
```
POST https://open.tiktokapis.com/v2/oauth/token/
Body: client_key=X&client_secret=Y&grant_type=client_credentials
→ Returns: access_token
```

### Rate Limits
- 1,000 requests/day (Research API tier)

### Cost
**Free** (if approved).

### What to Do While Waiting
SoundPulse automatically falls back to Chartmetric's TikTok data. You get chart-level trending sounds but not the deeper creator-tier signals. The system works fine without it — predictions will just be slightly less accurate for TikTok-driven breakouts.

---

## 6. MUSICBRAINZ

### What SoundPulse Uses It For
- ISRC lookups (connecting the same track across platforms)
- Artist disambiguation ("The National" the band vs other entities)
- Release date metadata
- Additional genre tags
- Canonical metadata enrichment for newly discovered entities

### Credentials Needed
| Field | Value | Where It Goes |
|-------|-------|---------------|
| `user_agent` | `SoundPulse/1.0 (your@email.com)` | `MUSICBRAINZ_USER_AGENT` env var |

### How to Get It
**Nothing to do.** MusicBrainz is an open API with no authentication. You just need to set a proper User-Agent header identifying your application (this is their only requirement).

### Rate Limits
- **1 request per second** — this is a hard limit
- Exceeding it will get your IP temporarily banned
- The scraper must enforce `asyncio.sleep(1.1)` between all requests

### Cost
**Free.**

---

## 7. LUMINATE / RADIO DATA

### What SoundPulse Uses It For
- Radio airplay data: how many spins, which stations, audience impressions
- Validates mainstream crossover (radio is a lagging indicator)
- Radio has the lowest weight in the composite score (0.10)

### Status
**Skip this for now.** Luminate and Radiomonitor are enterprise APIs requiring sales conversations. Not worth pursuing for MVP.

### Free Fallback
SoundPulse automatically scrapes Billboard Airplay charts:
- https://www.billboard.com/charts/radio-songs/
- https://www.billboard.com/charts/pop-airplay/
- https://www.billboard.com/charts/country-airplay/

This gives you weekly chart positions (not real-time spins), which is good enough for the 0.10 weight radio carries.

### If You Want It Later
- **Luminate**: Contact `luminate.support@luminate.com`
- **Radiomonitor**: https://www.radiomonitor.com/ → request demo
- Both are enterprise pricing (likely $500+/month)

---

## TOTAL COST SUMMARY

### Minimum Viable (start here)
| Provider | Plan | Monthly |
|----------|------|---------|
| Spotify | Free | $0 |
| Chartmetric | Starter | $150 |
| Shazam | RapidAPI Pro | $10 |
| MusicBrainz | Free | $0 |
| **Total** | | **$160/mo** |

### Recommended (full coverage)
| Provider | Plan | Monthly |
|----------|------|---------|
| Spotify | Free | $0 |
| Chartmetric | Pro | $400 |
| Shazam | RapidAPI Ultra | $50 |
| Apple Music | Developer Account | $8 |
| TikTok | Research API | $0 |
| MusicBrainz | Free | $0 |
| **Total** | | **$458/mo** |

### Bare Minimum (Spotify only, for initial development)
| Provider | Plan | Monthly |
|----------|------|---------|
| Spotify | Free | $0 |
| **Total** | | **$0/mo** |

You can build and test the entire API with just Spotify data. Add Chartmetric and Shazam when you're ready to collect real cross-platform intelligence.

---

## CREDENTIAL FILE FORMAT

Once you have your keys, put them in `config/credentials.yaml`:

```yaml
spotify:
  client_id: "your_spotify_client_id"
  client_secret: "your_spotify_client_secret"

chartmetric:
  api_key: "your_chartmetric_refresh_token"

shazam:
  rapidapi_key: "your_rapidapi_key"

apple_music:
  team_id: "A1B2C3D4E5"
  key_id: "ABC123DEFG"
  private_key_path: "./keys/apple_music.p8"

tiktok:
  client_key: ""
  client_secret: ""
  status: "pending"  # change to "approved" when you get access

musicbrainz:
  user_agent: "SoundPulse/1.0 (your@email.com)"

luminate:
  status: "not_configured"
```

And the corresponding `.env` file:
```bash
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
CHARTMETRIC_API_KEY=your_chartmetric_refresh_token
SHAZAM_RAPIDAPI_KEY=your_rapidapi_key
APPLE_MUSIC_TEAM_ID=A1B2C3D4E5
APPLE_MUSIC_KEY_ID=ABC123DEFG
APPLE_MUSIC_PRIVATE_KEY_PATH=./keys/apple_music.p8
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
MUSICBRAINZ_USER_AGENT=SoundPulse/1.0 (your@email.com)
```
