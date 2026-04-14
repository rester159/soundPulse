"""Dump the full /analysis payload for one instrumental. Debug helper."""
import json
import os
import sys
import urllib.request

if len(sys.argv) < 2:
    print("usage: _dump_instrumental_analysis.py <instrumental_id>", file=sys.stderr)
    raise SystemExit(2)

iid = sys.argv[1]
base = os.environ["SOUNDPULSE_API_URL"].rstrip("/")
req = urllib.request.Request(
    f"{base}/api/v1/admin/instrumentals/{iid}/analysis",
    headers={"X-API-Key": os.environ["API_ADMIN_KEY"]},
)
data = json.loads(urllib.request.urlopen(req, timeout=30).read())
print(json.dumps(data, indent=2, default=str))
