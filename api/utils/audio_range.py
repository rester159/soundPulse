"""HTTP Range-aware audio response helper.

HTML5 `<audio>` needs byte-range support to seek mid-file. Without
`Accept-Ranges: bytes` (and proper handling of incoming `Range:`
headers) every mid-file seek either stalls or silently falls back
to t=0 — because the browser hasn't downloaded the bytes near the
target and has no way to ask for just that range.

This helper takes an in-memory audio buffer, a content type, and
the incoming `Request`, and returns either:
  - 206 Partial Content with the requested slice + Content-Range
  - 200 OK with the full buffer and Accept-Ranges advertised

Use from any router that streams audio from a DB blob. For audio
streamed from disk, FastAPI's `FileResponse` already handles ranges.
"""
from __future__ import annotations

import re

from fastapi import HTTPException, Request
from fastapi.responses import Response

_RANGE_RE = re.compile(r"bytes=(\d+)-(\d*)")


def audio_range_response(
    audio_bytes: bytes,
    content_type: str,
    request: Request,
    *,
    cache_max_age: int = 3600,
) -> Response:
    """Return a Range-aware response for an audio blob.

    Args:
        audio_bytes: full file bytes (held in memory; fine up to a few MB).
        content_type: media type for the response.
        request: the incoming FastAPI request (so we can read `Range:`).
        cache_max_age: seconds for the Cache-Control header.
    """
    total = len(audio_bytes)
    common = {
        "Accept-Ranges": "bytes",
        "Cache-Control": f"public, max-age={cache_max_age}",
    }
    range_header = request.headers.get("range") or request.headers.get("Range")
    if range_header:
        m = _RANGE_RE.match(range_header.strip())
        if m:
            start = int(m.group(1))
            end_raw = m.group(2)
            end = int(end_raw) if end_raw else total - 1
            end = min(end, total - 1)
            if start > end or start >= total:
                raise HTTPException(
                    status_code=416,
                    detail="range not satisfiable",
                    headers={"Content-Range": f"bytes */{total}"},
                )
            chunk = audio_bytes[start : end + 1]
            return Response(
                content=chunk,
                status_code=206,
                media_type=content_type,
                headers={
                    **common,
                    "Content-Range": f"bytes {start}-{end}/{total}",
                    "Content-Length": str(len(chunk)),
                },
            )

    return Response(
        content=audio_bytes,
        media_type=content_type,
        headers={
            **common,
            "Content-Length": str(total),
        },
    )
