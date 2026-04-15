"""Quick status dump for the Chartmetric ingestion pipeline.
Runs under `railway run --service soundPulse` so it inherits
SOUNDPULSE_API_URL + API_ADMIN_KEY from the prod service env.
"""
import json
import os
import sys
import urllib.request
import urllib.error


def get(path: str) -> dict:
    base = os.environ["SOUNDPULSE_API_URL"].rstrip("/")
    key = os.environ["API_ADMIN_KEY"]
    req = urllib.request.Request(base + path, headers={"X-API-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} on {path}: {e.read()[:300].decode('utf-8','ignore')}", file=sys.stderr)
        return {}


def main() -> int:
    print("=" * 60)
    print("CHARTMETRIC INGESTION STATUS")
    print("=" * 60)

    burn = get("/api/v1/admin/chartmetric/burn")
    print("\n[BURN] last-24h vs daily quota")
    for k in (
        "daily_quota", "utilization_pct_24h",
        "calls_last_1h", "calls_last_24h", "calls_last_7d",
        "successes_last_24h", "rate_limited_last_24h", "errors_last_24h",
        "adaptive_multiplier", "last_429_at",
    ):
        if k in burn:
            print(f"  {k:28} = {burn[k]}")

    queue = get("/api/v1/admin/chartmetric/queue")
    inflight = queue.get("in_flight") or {}
    print(f"\n[QUEUE] in_flight: {inflight.get('count', 0)} (oldest: {inflight.get('oldest')})")
    pending = queue.get("pending_by_bucket") or []
    total_pending = sum(int(p.get("count", 0)) for p in pending)
    print(f"[QUEUE] pending total: {total_pending}")
    if pending:
        print("[QUEUE] pending by producer / bucket:")
        for p in pending[:30]:
            print(f"   {p.get('producer','?'):24} {p.get('handler','?'):20} {p.get('priority_bucket','?'):10} n={p.get('count',0):6} oldest={p.get('oldest','-')}")

    handlers = get("/api/v1/admin/chartmetric/handlers")
    reg = handlers.get("registered") or []
    print(f"\n[HANDLERS] registered: {reg}")
    stats = handlers.get("stats_24h") or {}
    if stats:
        print("[HANDLERS] 24h stats:")
        for name, row in stats.items():
            print(f"   {name:24} total={row.get('total_24h',0):6} ok={row.get('ok',0):6} rl={row.get('rate_limited',0):4} err={row.get('errors',0):4}")
    else:
        print("[HANDLERS] no 24h stats yet — fetcher may still be in dry mode or queue empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# cache-bust: force rebuild to pick up CHARTMETRIC_FETCHER_DRY_MODE=0 from Railway env
