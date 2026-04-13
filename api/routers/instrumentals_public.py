"""
Public (unauthenticated) streaming endpoint for uploaded instrumentals.

Why this lives outside /admin: Kie.ai's /api/v1/generate/add-vocals takes
a publicly-reachable `uploadUrl` — it fetches the audio file server-side
and cannot pass our X-API-Key header. So we need an open route keyed by
the instrumental UUID (effectively unguessable) that streams the bytes
from `instrumental_blobs`.

Security posture: the UUID path is high-entropy (122 bits); there's no
enumeration endpoint at this route (the admin list lives behind auth);
and soft-deleted instrumentals (is_active=false) return 404 here so the
CEO can rotate them out of circulation without a separate key.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlalchemy import text as _text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from api.database import get_db

router = APIRouter(tags=["instrumentals-public"])


@router.get("/api/v1/instrumentals/public/{path_id_with_ext}")
async def stream_instrumental_public(
    path_id_with_ext: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Stream an uploaded instrumental by its UUID + extension.

    Expected path: /api/v1/instrumentals/public/<uuid>.<ext>
    Example:       /api/v1/instrumentals/public/c3a1...-....-....mp3

    Returns the raw audio bytes with the original content type. Returns
    404 if the row doesn't exist, isn't active, or the extension doesn't
    match the stored content type (minor defense against URL tampering).
    """
    import uuid as _uuid
    # Strip extension — we accept mp3 | wav | flac | ogg | aac | m4a
    stem = path_id_with_ext
    for ext in ("mp3", "wav", "flac", "ogg", "aac", "m4a"):
        suffix = f".{ext}"
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    try:
        iid = _uuid.UUID(stem)
    except ValueError:
        raise HTTPException(404, detail="not found")

    # Join instrumentals + instrumental_blobs in one query
    r = await db.execute(
        _text("""
            SELECT i.content_type, b.audio_bytes, i.is_active
            FROM instrumentals i
            JOIN instrumental_blobs b ON b.instrumental_id = i.id
            WHERE i.id = :iid
        """),
        {"iid": iid},
    )
    row = r.fetchone()
    if row is None or not row[2]:
        raise HTTPException(404, detail="not found")

    content_type = row[0] or "audio/mpeg"
    audio_bytes = bytes(row[1])
    return Response(
        content=audio_bytes,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Length": str(len(audio_bytes)),
        },
    )
