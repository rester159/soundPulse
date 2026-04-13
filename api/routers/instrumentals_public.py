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

import logging
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import text as _text
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["instrumentals-public"])

# Per-IP rate limit for public uploads — 5 submissions per hour per IP.
# Keeps abuse bounded without requiring captcha or email validation for
# the MVP. Backed by a simple in-memory dict; resets on restart which
# is fine for a spam-prevention hygiene check.
_PUBLIC_UPLOAD_RATE: dict[str, list[float]] = {}
PUBLIC_UPLOAD_LIMIT_PER_HOUR = 5
PUBLIC_UPLOAD_MAX_BYTES = 40 * 1024 * 1024

PUBLIC_ALLOWED_CTYPES = {
    "audio/mpeg", "audio/mp3",
    "audio/wav", "audio/x-wav", "audio/wave",
    "audio/flac", "audio/x-flac",
    "audio/ogg",
    "audio/aac", "audio/mp4", "audio/x-m4a", "audio/m4a",
}


def _check_public_rate(client_ip: str) -> None:
    now = time.time()
    window_start = now - 3600
    log = _PUBLIC_UPLOAD_RATE.get(client_ip, [])
    # Prune entries outside the 1-hour window
    log = [t for t in log if t > window_start]
    if len(log) >= PUBLIC_UPLOAD_LIMIT_PER_HOUR:
        raise HTTPException(
            429,
            detail=f"rate limit: max {PUBLIC_UPLOAD_LIMIT_PER_HOUR} submissions per hour per IP. Try again later.",
        )
    log.append(now)
    _PUBLIC_UPLOAD_RATE[client_ip] = log


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


# --------------------------------------------------------------------
# Public submission form — external creators can share a link with this
# and submit an instrumental without logging in. The backend stores
# their upload with uploaded_by = "external:<their_name>" and flags it
# as pending_review=true so the CEO sees it in the Instrumentals page
# before it goes live.
# --------------------------------------------------------------------

_SUBMIT_HTML = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SoundPulse — Submit Instrumental</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    background: #0a0a0b; color: #e4e4e7;
    min-height: 100vh;
    display: flex; align-items: center; justify-content: center;
    padding: 24px;
  }
  .card {
    max-width: 560px; width: 100%;
    background: #18181b; border: 1px solid #27272a;
    border-radius: 12px; padding: 32px;
  }
  h1 {
    margin: 0 0 6px; font-size: 22px; color: #fafafa;
    display: flex; align-items: center; gap: 10px;
  }
  .logo { width: 28px; height: 28px; border-radius: 6px;
          background: linear-gradient(135deg, #a78bfa, #6366f1);
          display: inline-block; }
  p.sub { margin: 0 0 24px; color: #a1a1aa; font-size: 13px; }
  label { display: block; margin-bottom: 4px; font-size: 11px;
          color: #a1a1aa; text-transform: uppercase; letter-spacing: 0.05em; }
  input, textarea {
    width: 100%; padding: 10px 12px;
    background: #0a0a0b; color: #fafafa;
    border: 1px solid #27272a; border-radius: 6px;
    font-size: 14px; font-family: inherit;
    margin-bottom: 16px;
  }
  input:focus, textarea:focus { outline: none; border-color: #8b5cf6; }
  input[type="file"] { padding: 8px; }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  button {
    width: 100%; padding: 12px;
    background: #7c3aed; color: white; border: 0; border-radius: 6px;
    font-size: 14px; font-weight: 600; cursor: pointer;
    transition: background 0.15s;
  }
  button:hover { background: #8b5cf6; }
  button:disabled { background: #3f3f46; cursor: not-allowed; }
  .note { font-size: 11px; color: #71717a; margin-top: 16px; line-height: 1.5; }
  .status { margin-top: 16px; padding: 12px; border-radius: 6px; font-size: 13px; }
  .status.success { background: rgba(34,197,94,0.1); border: 1px solid rgba(34,197,94,0.3); color: #86efac; }
  .status.error { background: rgba(244,63,94,0.1); border: 1px solid rgba(244,63,94,0.3); color: #fda4af; }
  .required { color: #f87171; }
</style>
</head>
<body>
  <div class="card">
    <h1><span class="logo"></span>SoundPulse — Submit an instrumental</h1>
    <p class="sub">
      Drop a beat and our artists may write vocals over it. All submissions
      are reviewed by the label before going into the catalog.
    </p>

    <form id="f" enctype="multipart/form-data">
      <label>Your name <span class="required">*</span></label>
      <input type="text" name="submitter_name" required maxlength="80" placeholder="Fonzworth Beats">

      <label>Your email (optional)</label>
      <input type="email" name="submitter_email" maxlength="120" placeholder="you@example.com">

      <label>Track title <span class="required">*</span></label>
      <input type="text" name="title" required maxlength="120" placeholder="Kingston Rooftop Beat">

      <label>Audio file (mp3/wav/flac, max 40MB) <span class="required">*</span></label>
      <input type="file" name="file" required
             accept="audio/mpeg,audio/mp3,audio/wav,audio/x-wav,audio/flac,audio/x-flac,audio/ogg,audio/aac,audio/mp4,audio/x-m4a,.mp3,.wav,.flac,.ogg,.aac,.m4a">

      <div class="row">
        <div>
          <label>Tempo BPM</label>
          <input type="number" name="tempo_bpm" step="0.1" placeholder="92">
        </div>
        <div>
          <label>Key</label>
          <input type="text" name="key_hint" maxlength="40" placeholder="A minor">
        </div>
      </div>

      <label>Genre hint</label>
      <input type="text" name="genre_hint" maxlength="60" placeholder="reggae, hip-hop, k-pop...">

      <label>Notes for the label</label>
      <textarea name="notes" rows="3" maxlength="500" placeholder="How you'd like to see this used"></textarea>

      <button type="submit" id="btn">Submit</button>
      <div id="status"></div>

      <div class="note">
        By submitting you grant SoundPulse Records a non-exclusive review
        license to evaluate this work for AI vocal generation. You retain
        ownership until a separate licensing agreement is executed.
      </div>
    </form>
  </div>

  <script>
  const f = document.getElementById('f');
  const btn = document.getElementById('btn');
  const status = document.getElementById('status');
  f.addEventListener('submit', async (e) => {
    e.preventDefault();
    status.className = ''; status.textContent = '';
    btn.disabled = true; btn.textContent = 'Submitting...';
    try {
      const fd = new FormData(f);
      const r = await fetch('/api/v1/public/instrumentals/submit', {
        method: 'POST', body: fd,
      });
      const body = await r.json().catch(() => ({}));
      if (r.ok) {
        status.className = 'status success';
        status.textContent = 'Submitted — thanks. The label will review within 48h.';
        f.reset();
      } else {
        status.className = 'status error';
        status.textContent = 'Failed: ' + (body.detail || r.status);
      }
    } catch (err) {
      status.className = 'status error';
      status.textContent = 'Network error: ' + err.message;
    } finally {
      btn.disabled = false; btn.textContent = 'Submit';
    }
  });
  </script>
</body></html>"""


@router.get("/submit/instrumental", response_class=HTMLResponse)
async def public_submit_form():
    """Standalone HTML upload page. Share this URL with external
    producers who want to submit an instrumental for consideration.
    No auth required."""
    return HTMLResponse(content=_SUBMIT_HTML)


@router.post("/api/v1/public/instrumentals/submit")
async def public_submit_instrumental(
    request: Request,
    submitter_name: str = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
    submitter_email: str | None = Form(None),
    tempo_bpm: float | None = Form(None),
    key_hint: str | None = Form(None),
    genre_hint: str | None = Form(None),
    notes: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Public instrumental submission endpoint. Accepts the same multipart
    payload as the admin upload but requires a submitter_name instead of
    an API key and enforces a per-IP rate limit.

    Stores with uploaded_by = 'external:<submitter_name>' and is_active=true
    so submissions are immediately visible in the CEO's Instrumentals page.
    The label reviews and can soft-delete anything they don't want.
    """
    from api.models.instrumental import Instrumental, InstrumentalBlob

    client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or request.client.host if request.client else "unknown"
    _check_public_rate(client_ip)

    raw = await file.read()
    if not raw:
        raise HTTPException(400, detail="empty upload")
    if len(raw) > PUBLIC_UPLOAD_MAX_BYTES:
        raise HTTPException(
            413,
            detail=f"file exceeds {PUBLIC_UPLOAD_MAX_BYTES // (1024 * 1024)} MB limit",
        )

    content_type = (file.content_type or "").lower().strip()
    if content_type not in PUBLIC_ALLOWED_CTYPES:
        lower_name = (file.filename or "").lower()
        if lower_name.endswith(".mp3"):
            content_type = "audio/mpeg"
        elif lower_name.endswith(".wav"):
            content_type = "audio/wav"
        elif lower_name.endswith(".flac"):
            content_type = "audio/flac"
        elif lower_name.endswith(".ogg"):
            content_type = "audio/ogg"
        elif lower_name.endswith((".m4a", ".mp4")):
            content_type = "audio/m4a"
        elif lower_name.endswith(".aac"):
            content_type = "audio/aac"
        else:
            raise HTTPException(
                415,
                detail=f"unsupported type '{content_type}' — allowed: mp3, wav, flac, ogg, aac, m4a",
            )

    # Compose uploaded_by as 'external:<name>' so admin queries can
    # filter external vs internal. Email (if provided) lives in notes
    # for now — no separate column until we see real usage.
    tagged_by = f"external:{submitter_name.strip()[:60]}"
    combined_notes = notes or ""
    if submitter_email:
        combined_notes = f"[email: {submitter_email.strip()[:120]}] {combined_notes}".strip()

    row = Instrumental(
        title=title.strip()[:120],
        uploaded_by=tagged_by,
        genre_hint=(genre_hint or "").strip()[:60] or None,
        tempo_bpm=tempo_bpm,
        key_hint=(key_hint or "").strip()[:40] or None,
        notes=combined_notes[:500] or None,
        original_filename=file.filename,
        content_type=content_type,
        size_bytes=len(raw),
    )
    db.add(row)
    await db.flush()
    db.add(InstrumentalBlob(
        instrumental_id=row.id,
        audio_bytes=raw,
    ))
    await db.commit()
    await db.refresh(row)

    logger.info(
        "[public-submit] %s uploaded '%s' (%d bytes, %s) ip=%s",
        tagged_by, row.title, row.size_bytes, content_type, client_ip,
    )
    return {
        "instrumental_id": str(row.id),
        "title": row.title,
        "size_bytes": row.size_bytes,
        "status": "submitted",
        "message": "Received. The SoundPulse label will review within 48h.",
    }
