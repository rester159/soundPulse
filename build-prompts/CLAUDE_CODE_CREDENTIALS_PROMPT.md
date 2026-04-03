# SoundPulse Credential Agent — Claude Code Build Prompt

> **Build an interactive CLI tool + automated agents that obtain all necessary API keys for SoundPulse to operate.**

---

## WHAT THIS IS

SoundPulse needs credentials from 7 upstream providers. Some are self-serve (Spotify, RapidAPI), some require applications (TikTok Research API), and some require enterprise sales conversations (Luminate). This prompt builds:

1. **Interactive CLI** — walks the user through obtaining each credential step by step
2. **Automated verification** — tests each credential after entry
3. **Credential storage** — securely writes to `config/credentials.yaml`
4. **Status dashboard** — shows which credentials are configured, pending, or unavailable

---

## BUILD: `scripts/api_key_setup.py`

```python
#!/usr/bin/env python3
"""
SoundPulse API Key Setup Wizard

Run: python scripts/api_key_setup.py
Interactive CLI that guides through obtaining and verifying all upstream API credentials.
"""

import yaml
import webbrowser
import asyncio
import httpx
import jwt
import time
import secrets
from pathlib import Path
from datetime import datetime, timezone
from cryptography.hazmat.primitives import serialization

CREDENTIALS_PATH = Path("config/credentials.yaml")
KEYS_DIR = Path("keys")

# ─── Provider Configuration ───

PROVIDERS = [
    {
        "name": "Spotify",
        "key": "spotify",
        "priority": "CRITICAL",
        "cost": "Free",
        "signup_url": "https://developer.spotify.com/dashboard",
        "fields": ["client_id", "client_secret"],
        "instructions": [
            "1. Go to https://developer.spotify.com/dashboard",
            "2. Log in with your Spotify account (create one if needed — free tier is fine)",
            "3. Click 'Create app'",
            "4. App name: 'SoundPulse', Description: 'Music trend intelligence'",
            "5. Redirect URI: http://localhost:8000/callback (required but we won't use it)",
            "6. Check 'Web API' under 'Which API/SDKs are you planning to use?'",
            "7. Click 'Save'",
            "8. On the app page, click 'Settings'",
            "9. Copy the 'Client ID' and 'Client secret'",
        ],
        "test_fn": "test_spotify",
    },
    {
        "name": "Chartmetric",
        "key": "chartmetric",
        "priority": "CRITICAL",
        "cost": "From $150/month",
        "signup_url": "https://chartmetric.com/pricing",
        "fields": ["api_key"],
        "instructions": [
            "1. Go to https://chartmetric.com/pricing",
            "2. Sign up for a plan (Starter at $150/mo is sufficient to start)",
            "3. After account activation, go to https://app.chartmetric.com/settings/api",
            "4. Generate an API refresh token",
            "5. Copy the token — this is your api_key",
            "",
            "NOTE: Chartmetric is the most valuable single data source.",
            "It provides cross-platform chart data (Spotify, Apple Music, TikTok, Shazam)",
            "through a single API. The $150/mo Starter plan includes:",
            "  - 2,000 API calls/day",
            "  - Chart data across all platforms",
            "  - Artist and track analytics",
            "If budget allows, Pro ($400/mo) gives 10,000 calls/day.",
        ],
        "test_fn": "test_chartmetric",
    },
    {
        "name": "Shazam (via RapidAPI)",
        "key": "shazam",
        "priority": "HIGH",
        "cost": "From $10/month (Pro plan)",
        "signup_url": "https://rapidapi.com/apidojo/api/shazam",
        "fields": ["rapidapi_key"],
        "instructions": [
            "1. Go to https://rapidapi.com/signup — create a RapidAPI account",
            "2. Navigate to https://rapidapi.com/apidojo/api/shazam",
            "3. Click 'Subscribe to Test'",
            "4. Select the 'Pro' plan ($10/month, 10,000 requests/month)",
            "   - Basic (free, 500/month) is too few for meaningful data collection",
            "   - Ultra ($50/month, 100,000/month) if you want comfortable headroom",
            "5. After subscribing, your RapidAPI key appears in the 'Header Parameters' section",
            "6. Copy the value next to 'X-RapidAPI-Key'",
            "",
            "WHY SHAZAM MATTERS:",
            "Shazam-to-Spotify ratio is the #1 leading indicator in our prediction model.",
            "A track being heavily Shazamed but not yet streaming big = about to break out.",
        ],
        "test_fn": "test_shazam",
    },
    {
        "name": "Apple Music (MusicKit)",
        "key": "apple_music",
        "priority": "MEDIUM",
        "cost": "$99/year (Apple Developer account)",
        "signup_url": "https://developer.apple.com/account",
        "fields": ["team_id", "key_id", "private_key_path"],
        "instructions": [
            "1. You need an Apple Developer account ($99/year)",
            "   Go to https://developer.apple.com/account and enroll",
            "   (Skip if you already have one from Atlas or other projects)",
            "",
            "2. Create a MusicKit key:",
            "   a. Go to https://developer.apple.com/account/resources/authkeys/list",
            "   b. Click '+' to create a new key",
            "   c. Name: 'SoundPulse MusicKit'",
            "   d. Check 'MusicKit' under capabilities",
            "   e. Click 'Continue' then 'Register'",
            "   f. DOWNLOAD the .p8 file — you can only download it ONCE",
            "   g. Move the .p8 file to: ./keys/apple_music.p8",
            "   h. Note the 'Key ID' shown on the page",
            "",
            "3. Find your Team ID:",
            "   Go to https://developer.apple.com/account → Membership details",
            "   Your Team ID is listed there (10 character alphanumeric)",
            "",
            "NOTE: Apple Music data is less rich than Spotify (no stream counts).",
            "If budget is tight, Chartmetric provides Apple Music chart data too.",
            "You can defer this and rely on Chartmetric for Apple Music coverage.",
        ],
        "test_fn": "test_apple_music",
    },
    {
        "name": "TikTok Research API",
        "key": "tiktok",
        "priority": "HIGH (but slow to obtain)",
        "cost": "Free (requires application approval)",
        "signup_url": "https://developers.tiktok.com/products/research-api/",
        "fields": ["client_key", "client_secret"],
        "instructions": [
            "1. Go to https://developers.tiktok.com/ and create a developer account",
            "2. Navigate to https://developers.tiktok.com/products/research-api/",
            "3. Click 'Apply for access'",
            "4. Fill out the application:",
            "   - Organization: Your company/entity name",
            "   - Use case: 'Music trend analysis and prediction for industry professionals'",
            "   - Data usage: 'Aggregated trend data on music sound adoption patterns'",
            "   - You are NOT collecting individual user data",
            "",
            "5. Application review takes 2-6 weeks",
            "6. If approved, you'll get client_key and client_secret",
            "",
            "WHILE WAITING: SoundPulse will use Chartmetric's TikTok data as a fallback.",
            "This covers chart-level data (trending sounds, rankings) but not the deeper",
            "signals like creator tier distribution and geographic spread.",
            "Set status to 'pending' for now.",
        ],
        "test_fn": "test_tiktok",
        "allow_pending": True,
    },
    {
        "name": "MusicBrainz",
        "key": "musicbrainz",
        "priority": "LOW (free, no signup)",
        "cost": "Free",
        "signup_url": None,
        "fields": ["user_agent"],
        "instructions": [
            "MusicBrainz requires NO API key — just a proper User-Agent header.",
            "We'll auto-configure this with your contact email.",
            "Rate limit: 1 request/second (hard limit, IP ban if exceeded).",
        ],
        "test_fn": "test_musicbrainz",
        "auto_configure": True,
    },
    {
        "name": "Luminate / Radio Data",
        "key": "luminate",
        "priority": "LOW (enterprise, optional)",
        "cost": "Enterprise pricing (contact sales)",
        "signup_url": None,
        "fields": ["api_key"],
        "instructions": [
            "Luminate (formerly Nielsen SoundScan) provides radio airplay data.",
            "This is an enterprise API — requires a sales conversation.",
            "",
            "OPTIONS:",
            "a) Contact Luminate: luminate.support@luminate.com",
            "   Mention: 'API access for music trend analytics platform'",
            "",
            "b) Alternative: Radiomonitor (https://www.radiomonitor.com/)",
            "   Real-time airplay monitoring, also enterprise pricing",
            "",
            "c) Free fallback: Billboard Airplay chart scraping",
            "   Less granular (weekly chart positions only) but free",
            "   SoundPulse will use this fallback automatically",
            "",
            "RECOMMENDATION: Skip for now, use Billboard fallback.",
            "Radio data has the lowest platform weight (0.10) anyway.",
            "Only pursue if you need radio airplay data for specific use cases.",
        ],
        "test_fn": None,
        "allow_skip": True,
    },
]


# ─── Verification Functions ───

async def test_spotify(creds: dict) -> tuple[bool, str]:
    """Test Spotify credentials via client_credentials flow."""
    async with httpx.AsyncClient() as client:
        import base64
        auth_str = base64.b64encode(
            f"{creds['client_id']}:{creds['client_secret']}".encode()
        ).decode()
        resp = await client.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {auth_str}"},
        )
        if resp.status_code == 200:
            token = resp.json()["access_token"]
            # Verify token works
            test_resp = await client.get(
                "https://api.spotify.com/v1/browse/new-releases?limit=1",
                headers={"Authorization": f"Bearer {token}"},
            )
            if test_resp.status_code == 200:
                return True, "Token exchange successful, API responding"
        return False, f"Auth failed: {resp.status_code} — {resp.text[:200]}"


async def test_chartmetric(creds: dict) -> tuple[bool, str]:
    """Test Chartmetric credentials."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.chartmetric.com/api/token",
            json={"refreshtoken": creds["api_key"]},
        )
        if resp.status_code == 200:
            token = resp.json().get("token")
            test_resp = await client.get(
                "https://api.chartmetric.com/api/charts/spotify/top/latest",
                headers={"Authorization": f"Bearer {token}"},
            )
            if test_resp.status_code == 200:
                return True, "Token exchange successful, chart data accessible"
        return False, f"Auth failed: {resp.status_code}"


async def test_shazam(creds: dict) -> tuple[bool, str]:
    """Test Shazam/RapidAPI credentials."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://shazam.p.rapidapi.com/charts/track",
            headers={
                "X-RapidAPI-Key": creds["rapidapi_key"],
                "X-RapidAPI-Host": "shazam.p.rapidapi.com",
            },
            params={"locale": "en-US", "pageSize": "1", "startFrom": "0"},
        )
        if resp.status_code == 200:
            remaining = resp.headers.get("X-RateLimit-Requests-Remaining", "unknown")
            return True, f"API responding, {remaining} requests remaining this month"
        return False, f"Failed: {resp.status_code} — check your RapidAPI subscription"


async def test_apple_music(creds: dict) -> tuple[bool, str]:
    """Test Apple Music MusicKit credentials by generating a JWT."""
    try:
        key_path = Path(creds["private_key_path"])
        if not key_path.exists():
            return False, f"Private key file not found at {key_path}"
        
        private_key = key_path.read_bytes()
        now = int(time.time())
        token = jwt.encode(
            {"iss": creds["team_id"], "iat": now, "exp": now + 15777000},
            private_key,
            algorithm="ES256",
            headers={"kid": creds["key_id"]},
        )
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.music.apple.com/v1/catalog/us/charts?types=songs&limit=1",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                return True, "JWT generation successful, Apple Music API responding"
            return False, f"JWT works but API returned {resp.status_code}"
    except Exception as e:
        return False, f"JWT generation failed: {str(e)}"


async def test_tiktok(creds: dict) -> tuple[bool, str]:
    """Test TikTok Research API credentials."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            data={
                "client_key": creds["client_key"],
                "client_secret": creds["client_secret"],
                "grant_type": "client_credentials",
            },
        )
        if resp.status_code == 200 and "access_token" in resp.json():
            return True, "OAuth token obtained, Research API access confirmed"
        return False, f"Auth failed: {resp.status_code} — application may still be pending"


async def test_musicbrainz(creds: dict) -> tuple[bool, str]:
    """Test MusicBrainz connectivity."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://musicbrainz.org/ws/2/artist/5b11f4ce-a62d-471e-81fc-a69a8278c7da?fmt=json",
            headers={"User-Agent": creds["user_agent"]},
        )
        if resp.status_code == 200:
            name = resp.json().get("name", "")
            return True, f"Connected — test query returned '{name}'"
        return False, f"Request failed: {resp.status_code}"


# ─── CLI Interface ───

def print_banner():
    print("""
╔══════════════════════════════════════════════╗
║     🎵 SoundPulse API Key Setup Wizard      ║
╠══════════════════════════════════════════════╣
║  This wizard will guide you through          ║
║  obtaining API credentials for all           ║
║  upstream data sources.                      ║
╚══════════════════════════════════════════════╝
    """)


def print_status(credentials: dict):
    """Print current credential status dashboard."""
    print("\n┌─────────────────────────────────────────────┐")
    print("│          Credential Status Dashboard         │")
    print("├──────────────┬──────────┬───────────────────┤")
    print("│ Provider     │ Status   │ Cost              │")
    print("├──────────────┼──────────┼───────────────────┤")
    
    for provider in PROVIDERS:
        key = provider["key"]
        cred = credentials.get(key, {})
        
        if cred.get("status") == "verified":
            status = "✅ Ready  "
        elif cred.get("status") == "pending":
            status = "⏳ Pending"
        elif cred.get("status") == "skipped":
            status = "⏭️  Skipped"
        elif any(cred.get(f) for f in provider["fields"]):
            status = "⚠️  Unverif"
        else:
            status = "❌ Missing"
        
        name = provider["name"][:12].ljust(12)
        cost = provider["cost"][:17].ljust(17)
        print(f"│ {name} │ {status} │ {cost} │")
    
    print("└──────────────┴──────────┴───────────────────┘")


def run_wizard():
    """Main interactive wizard flow."""
    print_banner()
    
    # Load existing credentials
    credentials = {}
    if CREDENTIALS_PATH.exists():
        credentials = yaml.safe_load(CREDENTIALS_PATH.read_text()) or {}
    
    print_status(credentials)
    
    for provider in PROVIDERS:
        key = provider["key"]
        
        print(f"\n{'='*50}")
        print(f"  {provider['name']}")
        print(f"  Priority: {provider['priority']}")
        print(f"  Cost: {provider['cost']}")
        print(f"{'='*50}")
        
        # Check if already configured
        existing = credentials.get(key, {})
        if existing.get("status") == "verified":
            print(f"  Already configured and verified. Skip? [Y/n]")
            if input("  > ").strip().lower() != "n":
                continue
        
        # Auto-configure if applicable
        if provider.get("auto_configure"):
            email = input("  Your contact email for User-Agent: ").strip()
            credentials[key] = {
                "user_agent": f"SoundPulse/1.0 ({email})",
                "status": "verified",
            }
            print("  ✅ Auto-configured!")
            save_credentials(credentials)
            continue
        
        # Show instructions
        print("\n  SETUP INSTRUCTIONS:")
        for line in provider["instructions"]:
            print(f"  {line}")
        
        # Offer to open URL
        if provider.get("signup_url"):
            print(f"\n  Open {provider['signup_url']} in browser? [Y/n]")
            if input("  > ").strip().lower() != "n":
                webbrowser.open(provider["signup_url"])
        
        # Allow skip
        if provider.get("allow_skip"):
            print("\n  Skip this provider? [Y/n]")
            if input("  > ").strip().lower() != "n":
                credentials[key] = {"status": "skipped"}
                save_credentials(credentials)
                continue
        
        # Allow pending
        if provider.get("allow_pending"):
            print("\n  Set as 'pending' (waiting for approval)? [y/N]")
            if input("  > ").strip().lower() == "y":
                credentials[key] = {"status": "pending"}
                save_credentials(credentials)
                continue
        
        # Collect credentials
        print("\n  Enter your credentials:")
        cred_data = {}
        for field in provider["fields"]:
            if field == "private_key_path":
                KEYS_DIR.mkdir(exist_ok=True)
                default_path = str(KEYS_DIR / "apple_music.p8")
                value = input(f"  {field} [{default_path}]: ").strip() or default_path
            else:
                value = input(f"  {field}: ").strip()
            cred_data[field] = value
        
        # Verify
        if provider.get("test_fn"):
            print("\n  Verifying credentials...")
            test_fn = globals()[provider["test_fn"]]
            success, message = asyncio.run(test_fn(cred_data))
            if success:
                print(f"  ✅ {message}")
                cred_data["status"] = "verified"
                cred_data["verified_at"] = datetime.now(timezone.utc).isoformat()
            else:
                print(f"  ❌ {message}")
                print("  Save anyway? [y/N]")
                if input("  > ").strip().lower() != "y":
                    continue
                cred_data["status"] = "unverified"
        
        credentials[key] = cred_data
        save_credentials(credentials)
    
    # Generate SoundPulse's own admin key
    if "soundpulse" not in credentials or not credentials["soundpulse"].get("admin_key"):
        admin_key = f"sp_admin_{secrets.token_hex(16)}"
        credentials["soundpulse"] = {
            "admin_key": admin_key,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        save_credentials(credentials)
        print(f"\n  Generated SoundPulse admin key: {admin_key}")
    
    # Final status
    print_status(credentials)
    print("\n  Setup complete! Run 'docker compose up' to start SoundPulse.")


def save_credentials(credentials: dict):
    """Save credentials to YAML file."""
    CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_PATH.write_text(yaml.dump(credentials, default_flow_style=False))
    # Set restrictive permissions
    CREDENTIALS_PATH.chmod(0o600)


if __name__ == "__main__":
    run_wizard()
```

---

## COST SUMMARY FOR ENRICO

| Provider | Plan | Monthly Cost | What You Get |
|----------|------|-------------|-------------|
| Spotify | Free | $0 | Full Web API access |
| Chartmetric | Starter | $150 | Cross-platform charts, 2K calls/day |
| Shazam (RapidAPI) | Pro | $10 | 10K Shazam chart requests/month |
| Apple Music | Dev Account | $8.25 (~$99/yr) | MusicKit API access |
| TikTok | Research API | $0 | Deep TikTok data (if approved) |
| MusicBrainz | Free | $0 | Metadata enrichment |
| Luminate | Skip for now | $0 | Billboard scrape fallback |
| **Total** | | **~$168/month** | |

Upgrade path: Chartmetric Pro ($400/mo) + Shazam Ultra ($50/mo) = ~$460/mo for full headroom.
