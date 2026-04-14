"""Throwaway song lookup helper for ad-hoc debugging."""
import json
import os
import sys
import urllib.request
import urllib.error


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _find_song_adhoc.py <uuid_or_prefix>", file=sys.stderr)
        return 2
    needle = sys.argv[1]
    base = os.environ["SOUNDPULSE_API_URL"].rstrip("/")
    headers = {"X-API-Key": os.environ["API_ADMIN_KEY"]}

    def get(path: str):
        req = urllib.request.Request(base + path, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    # Try the single-song GET first in case it's a full UUID
    try:
        s = get(f"/api/v1/admin/songs/{needle}")
        if isinstance(s, dict):
            _print_song(s, base, headers)
            return 0
    except urllib.error.HTTPError as e:
        if e.code != 404:
            sys.stderr.write(f"single-get HTTP {e.code}: {e.read()[:300].decode('utf-8', 'ignore')}\n")

    # Otherwise paginate the list endpoint and match on prefix / substring.
    offset = 0
    page_size = 500
    total_seen = 0
    first_page_shape = None
    while offset < 20000:
        try:
            page = get(f"/api/v1/admin/songs?limit={page_size}&offset={offset}")
        except urllib.error.HTTPError as e:
            sys.stderr.write(f"list HTTP {e.code}: {e.read()[:300].decode('utf-8', 'ignore')}\n")
            return 3
        if first_page_shape is None:
            first_page_shape = type(page).__name__
            if isinstance(page, dict):
                print(f"(debug) list keys: {list(page.keys())}", file=sys.stderr)
        items = None
        if isinstance(page, dict):
            for key in ("songs", "data", "items"):
                if isinstance(page.get(key), list):
                    items = page[key]
                    break
        elif isinstance(page, list):
            items = page
        if not isinstance(items, list):
            sys.stderr.write(f"unexpected shape (offset={offset}): {type(items).__name__}\n")
            return 4
        if not items:
            break
        total_seen += len(items)
        for s in items:
            sid = str(s.get("song_id") or s.get("id") or "")
            title = str(s.get("title") or "")
            if needle in sid or needle.lower() in title.lower():
                _print_song(s, base, headers)
                return 0
        offset += page_size

    sys.stderr.write(f"no song with {needle!r} in id (scanned {total_seen} rows)\n")
    return 5


def _print_song(s: dict, base: str, headers: dict) -> None:
    sid = str(s.get("song_id") or s.get("id"))
    print(f"song_id={sid}")
    for k in ("title", "artist_name", "artist", "status", "audio_url", "artist_id"):
        if k in s:
            print(f"{k}={s.get(k)!r}")

    def get(path: str):
        req = urllib.request.Request(base + path, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    try:
        stems = get(f"/api/v1/admin/songs/{sid}/stems")
    except urllib.error.HTTPError as e:
        print(f"(stems HTTP {e.code})")
        return
    job = stems.get("job") or stems.get("latest_job") or {}
    if job:
        print(f"job_id={job.get('id')}")
        print(f"job_status={job.get('status')}")
        print(f"source_instrumental_id={job.get('source_instrumental_id')}")
    else:
        print("NO_STEM_JOB")
    stem_types = [x.get("stem_type") for x in stems.get("stems", [])]
    print(f"stem_types={stem_types}")

    iid = job.get("source_instrumental_id") if job else None
    if iid:
        try:
            analysis = get(f"/api/v1/admin/instrumentals/{iid}/analysis")
            print(f"analysis_vocal_entry_seconds={analysis.get('vocal_entry_seconds')}")
            print(f"analysis_vocal_entry_source={analysis.get('vocal_entry_source')}")
            print(f"analysis_analyzed_at={analysis.get('analyzed_at')}")
        except urllib.error.HTTPError as e:
            print(f"(analysis HTTP {e.code})")


if __name__ == "__main__":
    raise SystemExit(main())
