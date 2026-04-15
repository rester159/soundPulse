"""Probe Chartmetric to find the real URL for per-track stats.

Tries several candidate URL shapes against a known track (cm_id
fetched from our tracks table) and prints the response code for
each so we can pick the one that returns 2xx.
"""
import json
import os
import urllib.request
import urllib.error

import psycopg2

dsn = os.environ["DATABASE_URL"]
if dsn.startswith("postgresql+asyncpg://"):
    dsn = "postgresql://" + dsn[len("postgresql+asyncpg://"):]
dsn = dsn.replace("?ssl=", "?sslmode=").replace("&ssl=", "&sslmode=")

# Step 1: get a bearer token
api_key = os.environ["CHARTMETRIC_API_KEY"]
req = urllib.request.Request(
    "https://api.chartmetric.com/api/token",
    data=json.dumps({"refreshtoken": api_key}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
token_resp = json.loads(urllib.request.urlopen(req, timeout=20).read())
token = token_resp.get("token") or token_resp.get("access_token")
if not token:
    print("AUTH FAILED:", token_resp)
    raise SystemExit(1)
print("auth OK")

# Step 2: pick a known-good cm_track_id from our DB
with psycopg2.connect(dsn) as c, c.cursor() as cur:
    cur.execute("""
        SELECT chartmetric_id, title FROM tracks
        WHERE chartmetric_id IS NOT NULL
        ORDER BY chartmetric_id
        LIMIT 1
    """)
    row = cur.fetchone()
if not row:
    print("no track with chartmetric_id")
    raise SystemExit(1)
cm_id, title = row
print(f"using track cm_id={cm_id} title={title!r}")

# Step 3: try candidate URL shapes
candidates = [
    f"/api/track/{cm_id}/stat/spotify?latest=true",
    f"/api/track/{cm_id}/stats/spotify?latest=true",
    f"/api/track/{cm_id}/spotify/stat?latest=true",
    f"/api/track/{cm_id}?source=spotify",
    f"/api/track/{cm_id}",
    f"/api/track/{cm_id}/stat/spotify",
    f"/api/track/{cm_id}/spotify/history",
    f"/api/track/{cm_id}/stat/tiktok?latest=true",
    f"/api/track/{cm_id}/stat/youtube?latest=true",
    f"/api/track/{cm_id}/fanmetric/spotify?latest=true",
    f"/api/track/{cm_id}/fanmetric/spotify",
]
for path in candidates:
    url = "https://api.chartmetric.com" + path
    try:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read()[:500]
            print(f"  200 {path}  body[:200]={body[:200].decode('utf-8','ignore')}")
    except urllib.error.HTTPError as e:
        body = e.read()[:300].decode("utf-8", "ignore")
        print(f"  {e.code} {path}  err={body[:180]}")
    except Exception as e:
        print(f"  ERR {path}  {type(e).__name__}: {e}")
