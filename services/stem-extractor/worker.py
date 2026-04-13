"""
SoundPulse stem-extractor worker — Demucs + ffmpeg on Railway.

Runs as a separate Railway service that polls the SoundPulse API for
pending stem extraction jobs, downloads the Suno output + the user's
original instrumental, runs Demucs to separate vocals from the Suno
output, then ffmpeg-mixes the isolated vocals onto the ORIGINAL
instrumental to produce a 'final_mixed' track. Posts every stem
(suno_original, vocals_only, final_mixed, and optionally drums/bass/
other) back to the API as base64.

Env vars (required on the Railway service):
  SOUNDPULSE_API     base URL of the main API
  API_ADMIN_KEY      X-API-Key with admin privilege
  WORKER_ID          stable identifier (defaults to hostname)
  POLL_INTERVAL_SEC  sleep between empty polls (default 30)
  DEMUCS_MODEL       model name (default 'htdemucs' — hybrid transformer)
  STEM_STORE_EXTRAS  '1' to store drums/bass/other stems (default '0')

Flow per job:
  1. POST /admin/worker/stem-claim-next → get job + source URLs
  2. Download source_audio_url (Suno output MP3)
  3. Download source_instrumental_url (user upload) if present
  4. Run `demucs` CLI on the Suno output → 4 stems (vocals, drums, bass, other)
  5. If instrumental present: ffmpeg-mix vocals.wav + instrumental.mp3
     → final_mixed.mp3
  6. Convert vocals.wav + final_mixed.mp3 to base64 payloads
  7. POST /admin/worker/stem-ack/{job_id} with the stem list
  8. On any failure: POST /admin/worker/stem-fail/{job_id}

Why Demucs CLI instead of the Python API: subprocess is cleaner for
large memory releases between jobs (the PyTorch model stays resident
in the CLI process too, but isolation is simpler to reason about).
"""
from __future__ import annotations

import base64
import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s stem-extractor] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("stem-extractor")

API_BASE = (os.environ.get("SOUNDPULSE_API") or "http://localhost:8000").rstrip("/")
API_KEY = os.environ.get("API_ADMIN_KEY", "").strip()
WORKER_ID = os.environ.get("WORKER_ID", socket.gethostname())
POLL_INTERVAL_SEC = int(os.environ.get("POLL_INTERVAL_SEC", "30"))
DEMUCS_MODEL = os.environ.get("DEMUCS_MODEL", "htdemucs")
STORE_EXTRAS = os.environ.get("STEM_STORE_EXTRAS", "0") == "1"

if not API_KEY:
    log.error("FATAL: API_ADMIN_KEY env var is required")
    sys.exit(1)


# ---- HTTP helpers (urllib — no external deps beyond demucs) ----

def _api_request(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "X-API-Key": API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode("utf-8")
        except Exception:
            pass
        raise RuntimeError(f"API {method} {path} {e.code}: {body_text[:300]}") from e


def claim_next() -> dict | None:
    try:
        res = _api_request("POST", "/api/v1/admin/worker/stem-claim-next", {"worker_id": WORKER_ID})
        return res.get("claimed")
    except Exception as e:
        log.warning("claim-next failed: %s", e)
        return None


def ack(job_id: str, stems: list[dict]) -> None:
    _api_request("POST", f"/api/v1/admin/worker/stem-ack/{job_id}", {"stems": stems})


def fail(job_id: str, error: str, retry: bool = True) -> None:
    try:
        _api_request(
            "POST",
            f"/api/v1/admin/worker/stem-fail/{job_id}",
            {"error": error[:900], "retry": retry},
        )
    except Exception as e:
        log.warning("fail post-back failed: %s", e)


# ---- File helpers ----

def _absolute_url(maybe_relative: str) -> str:
    """Turn '/api/v1/...' into a full URL hitting SOUNDPULSE_API."""
    if maybe_relative.startswith("http://") or maybe_relative.startswith("https://"):
        return maybe_relative
    if maybe_relative.startswith("/"):
        return f"{API_BASE}{maybe_relative}"
    return maybe_relative


def _download(url: str, target: Path) -> None:
    """Download a URL to disk. Attaches admin key so it can pull our
    own auth-gated streaming endpoints."""
    full_url = _absolute_url(url)
    req = urllib.request.Request(full_url)
    # Our admin streaming endpoint wants X-API-Key; public instrumental
    # endpoint is open but passing the header doesn't hurt.
    req.add_header("X-API-Key", API_KEY)
    with urllib.request.urlopen(req, timeout=120) as resp, target.open("wb") as f:
        shutil.copyfileobj(resp, f)


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _duration_seconds(path: Path) -> float | None:
    """Best-effort duration via ffprobe."""
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=nokey=1:noprint_wrappers=1", str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return float(out.stdout.strip()) if out.stdout.strip() else None
    except Exception:
        return None


# ---- Tempo-lock / phase-lock pre-pass --------------------------------
#
# Suno's output is beat-referenced to the uploaded instrumental but not
# atomically locked — small BPM drift (typically <2%) and small
# downbeat offsets leak through. When we mix Demucs'd vocals onto the
# original instrumental the two clocks fight each other and it sounds
# "close but off". This pre-pass fixes both:
#
#   1. BPM lock: measure Suno full-mix BPM and instrumental BPM, then
#      time-stretch Suno (pitch-preserving ffmpeg atempo) to the
#      instrumental's tempo BEFORE running Demucs. Vocals stem inherits
#      the locked tempo for free.
#
#   2. Phase lock: cross-correlate the onset envelopes of the stretched
#      Suno full-mix and the instrumental over the first 16 s to find
#      the downbeat offset. Trim or pad the vocals stem by that offset
#      before the final amix.
#
# Both steps are non-fatal: any failure in librosa / BPM estimation
# falls back to the old unlocked mix with a warning.

def _detect_bpm(path: Path) -> float:
    """Return estimated BPM via librosa beat tracker. Reliable on full
    mixes (drums + bass give strong onsets); DO NOT call on isolated
    vocal stems — the estimator will hallucinate."""
    import librosa
    y, sr = librosa.load(str(path), sr=None, mono=True)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    # librosa 0.10 returns a 0-d numpy array; coerce to float
    return float(tempo if not hasattr(tempo, "item") else tempo.item())


def _time_stretch_ffmpeg(in_path: Path, out_path: Path, ratio: float) -> None:
    """Time-stretch in_path so its tempo is multiplied by ratio, using
    ffmpeg's atempo filter. Preserves pitch. atempo supports 0.5–2.0
    in a single pass; for 1–3% drift it's well within the sweet spot."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(in_path),
        "-filter:a", f"atempo={ratio:.6f}",
        "-b:a", "192k",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg atempo failed: {result.stderr[-400:]}")


def _compute_phase_offset(reference_path: Path, target_path: Path) -> float:
    """
    Return seconds to advance the target to align it with the reference,
    via onset-envelope cross-correlation over the first 16 s.

      +  target is LATE vs reference → trim this many seconds from
         target's start
      -  target is EARLY vs reference → pad abs(this) seconds of
         silence at target's start

    Use the full (non-stemmed) Suno mix as target and the user's
    instrumental as reference — both have drums/bass for reliable
    onset detection.
    """
    import librosa
    import numpy as np
    y_ref, sr = librosa.load(str(reference_path), sr=None, mono=True, duration=16.0)
    y_tgt, _ = librosa.load(str(target_path), sr=sr, mono=True, duration=16.0)
    hop = 512
    env_ref = librosa.onset.onset_strength(y=y_ref, sr=sr, hop_length=hop)
    env_tgt = librosa.onset.onset_strength(y=y_tgt, sr=sr, hop_length=hop)
    # Zero-mean so the DC component doesn't bias the correlation peak
    env_ref = env_ref - env_ref.mean()
    env_tgt = env_tgt - env_tgt.mean()
    corr = np.correlate(env_tgt, env_ref, mode="full")
    # For np.correlate(a, b, mode='full'), index (len(b)-1) is lag 0.
    lag_frames = int(corr.argmax()) - (len(env_ref) - 1)
    return float(lag_frames * hop / sr)


def _trim_or_pad_start(in_path: Path, out_path: Path, *,
                      trim_start_seconds: float = 0.0,
                      pad_start_seconds: float = 0.0) -> None:
    """Shift content at the start of an audio file via ffmpeg. Use
    trim_start to advance (cut silence/drift off the head); use
    pad_start to delay (insert silence at the head)."""
    cmd = ["ffmpeg", "-y"]
    if trim_start_seconds > 0:
        cmd += ["-ss", f"{trim_start_seconds:.4f}"]
    cmd += ["-i", str(in_path)]
    if pad_start_seconds > 0:
        delay_ms = int(pad_start_seconds * 1000)
        cmd += ["-af", f"adelay={delay_ms}|{delay_ms}"]
    cmd += ["-b:a", "192k", str(out_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg trim/pad failed: {result.stderr[-400:]}")


# ---- Demucs separation ----

def _run_demucs(input_path: Path, out_dir: Path) -> dict[str, Path]:
    """
    Run Demucs on the input file and return a dict of
    {stem_name: path_to_wav} for the four output stems.
    """
    log.info("running demucs (%s) on %s", DEMUCS_MODEL, input_path.name)
    cmd = [
        "python", "-m", "demucs",
        "-n", DEMUCS_MODEL,
        "--out", str(out_dir),
        "--mp3",  # output mp3 so our final payload is already small
        str(input_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if result.returncode != 0:
        raise RuntimeError(
            f"demucs exit {result.returncode}: "
            f"{result.stderr[-500:]}"
        )

    # Demucs writes to {out_dir}/{model_name}/{input_stem}/{stem}.mp3
    stem_dir = out_dir / DEMUCS_MODEL / input_path.stem
    stems: dict[str, Path] = {}
    for stem_name in ("vocals", "drums", "bass", "other"):
        p = stem_dir / f"{stem_name}.mp3"
        if p.exists():
            stems[stem_name] = p
    if "vocals" not in stems:
        raise RuntimeError(f"demucs did not produce vocals.mp3 in {stem_dir}")
    return stems


def _ffmpeg_mix(vocal_path: Path, instrumental_path: Path, out_path: Path) -> None:
    """
    Mix vocals + instrumental → out_path (mp3). Vocals get a slight
    boost (+2dB) vs instrumental to sit on top without fighting the
    beat. Adjust if mixes come out muddy/bright.
    """
    log.info("ffmpeg mix: vocals=%s instrumental=%s", vocal_path.name, instrumental_path.name)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(vocal_path),
        "-i", str(instrumental_path),
        "-filter_complex",
        "[0:a]volume=1.25[v];[1:a]volume=1.0[i];[v][i]amix=inputs=2:duration=longest:dropout_transition=2[out]",
        "-map", "[out]",
        "-ac", "2",
        "-b:a", "192k",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg mix failed: {result.stderr[-500:]}")


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


# ---- Job processor ----

def process_job(job: dict) -> None:
    job_id = job["job_id"]
    song_id = job.get("song_id")
    src_audio = job["source_audio_url"]
    src_instr = job.get("source_instrumental_url")
    song_title = job.get("song_title", "")

    log.info("JOB %s (song=%s title=%r)", job_id, song_id, song_title)

    with tempfile.TemporaryDirectory(prefix="stem-") as tdir:
        tmp = Path(tdir)
        suno_path = tmp / "suno.mp3"
        instr_path = tmp / "instrumental.mp3" if src_instr else None

        # 1. Download Suno output
        log.info("download suno → %s", suno_path.name)
        _download(src_audio, suno_path)

        # 2. Download user instrumental if present
        if src_instr and instr_path is not None:
            log.info("download instrumental → %s", instr_path.name)
            try:
                _download(src_instr, instr_path)
            except Exception as e:
                log.warning("instrumental download failed (%s) — will skip mix step", e)
                instr_path = None

        # 3. Tempo-lock pre-pass: stretch Suno full mix to the
        #    instrumental's tempo before Demucs. Skip if no
        #    instrumental, if the ratio is within noise, or if the
        #    ratio is outside a sanity band (|Δ|>10% almost always
        #    means the estimator picked a half/double-time octave).
        demucs_input = suno_path
        alignment_note: dict = {}
        if instr_path is not None and instr_path.exists():
            try:
                suno_bpm = _detect_bpm(suno_path)
                instr_bpm = _detect_bpm(instr_path)
                ratio = instr_bpm / suno_bpm if suno_bpm > 0 else 1.0
                alignment_note.update(
                    suno_bpm=round(suno_bpm, 2),
                    instr_bpm=round(instr_bpm, 2),
                    tempo_ratio=round(ratio, 5),
                )
                log.info("BPM: suno=%.2f instr=%.2f ratio=%.4f",
                         suno_bpm, instr_bpm, ratio)
                if abs(ratio - 1.0) > 0.001 and 0.9 < ratio < 1.1:
                    stretched = tmp / "suno_tempoed.mp3"
                    _time_stretch_ffmpeg(suno_path, stretched, ratio)
                    demucs_input = stretched
                    alignment_note["tempo_locked"] = True
                    log.info("tempo-locked suno → %.2f BPM (ratio %.4f)",
                             instr_bpm, ratio)
                else:
                    alignment_note["tempo_locked"] = False
            except Exception as e:
                log.warning("tempo-lock pre-pass failed (%s) — using raw suno", e)
                alignment_note["tempo_lock_error"] = str(e)[:200]

        # 4. Run Demucs on the (possibly tempo-locked) Suno mix
        out_dir = tmp / "demucs_out"
        out_dir.mkdir()
        stems_paths = _run_demucs(demucs_input, out_dir)
        vocal_path = stems_paths["vocals"]

        # 5. Phase-lock pre-mix pass: measure the downbeat offset
        #    between the Demucs input (= what the vocals were split
        #    from) and the real instrumental, then trim/pad the vocals
        #    stem so their beat 1s line up. Skip if offset is subcent
        #    (noise floor) or >2 s (probably an intro-length mismatch,
        #    not a phase problem).
        if instr_path is not None and instr_path.exists():
            try:
                offset_seconds = _compute_phase_offset(instr_path, demucs_input)
                alignment_note["phase_offset_seconds"] = round(offset_seconds, 4)
                log.info("phase offset: suno is %+.3f s vs instrumental",
                         offset_seconds)
                if 0.010 < abs(offset_seconds) < 2.0:
                    aligned_vocals = tmp / "vocals_phase_locked.mp3"
                    if offset_seconds > 0:
                        _trim_or_pad_start(vocal_path, aligned_vocals,
                                          trim_start_seconds=offset_seconds)
                    else:
                        _trim_or_pad_start(vocal_path, aligned_vocals,
                                          pad_start_seconds=-offset_seconds)
                    vocal_path = aligned_vocals
                    alignment_note["phase_locked"] = True
                    log.info("phase-locked vocals by %+.3f s", offset_seconds)
                else:
                    alignment_note["phase_locked"] = False
            except Exception as e:
                log.warning("phase-lock pre-pass failed (%s) — mixing as-is", e)
                alignment_note["phase_lock_error"] = str(e)[:200]

        # 6. Mix vocals + original instrumental (if we have one)
        final_mixed_path: Path | None = None
        if instr_path is not None and instr_path.exists():
            final_mixed_path = tmp / "final_mixed.mp3"
            try:
                _ffmpeg_mix(vocal_path, instr_path, final_mixed_path)
            except Exception as e:
                log.warning("ffmpeg mix failed: %s — final_mixed will not be stored", e)
                final_mixed_path = None

        if alignment_note:
            log.info("alignment summary: %s", json.dumps(alignment_note))

        # 5. Build stems payload
        stems_payload: list[dict] = [
            {
                "stem_type": "suno_original",
                "content_type": "audio/mpeg",
                "audio_base64": _b64(suno_path),
                "duration_seconds": _duration_seconds(suno_path),
            },
            {
                "stem_type": "vocals_only",
                "content_type": "audio/mpeg",
                "audio_base64": _b64(vocal_path),
                "duration_seconds": _duration_seconds(vocal_path),
            },
        ]
        if final_mixed_path is not None:
            stems_payload.append({
                "stem_type": "final_mixed",
                "content_type": "audio/mpeg",
                "audio_base64": _b64(final_mixed_path),
                "duration_seconds": _duration_seconds(final_mixed_path),
            })
        if STORE_EXTRAS:
            for stem_name, stem_type in (
                ("drums", "drums"),
                ("bass", "bass"),
                ("other", "other"),
            ):
                p = stems_paths.get(stem_name)
                if p and p.exists():
                    stems_payload.append({
                        "stem_type": stem_type,
                        "content_type": "audio/mpeg",
                        "audio_base64": _b64(p),
                        "duration_seconds": _duration_seconds(p),
                    })

        log.info("ack %s with %d stems", job_id, len(stems_payload))
        ack(job_id, stems_payload)


MAX_RETRIES_BEFORE_PERMANENT_FAIL = 3


def main() -> None:
    log.info("starting stem-extractor worker id=%s api=%s model=%s",
             WORKER_ID, API_BASE, DEMUCS_MODEL)
    while True:
        job = claim_next()
        if not job:
            time.sleep(POLL_INTERVAL_SEC)
            continue
        prior_retries = int(job.get("retry_count") or 0)
        try:
            process_job(job)
        except Exception as e:
            log.exception("job %s failed (prior retries=%d)", job.get("job_id"), prior_retries)
            # Permanent fail after 3 total retries so we never tight-
            # loop on a systemic bug (bad model, missing numpy, etc).
            should_retry = prior_retries < MAX_RETRIES_BEFORE_PERMANENT_FAIL
            try:
                fail(
                    job["job_id"],
                    f"{type(e).__name__}: {e}",
                    retry=should_retry,
                )
                if not should_retry:
                    log.error(
                        "job %s permanently failed after %d retries",
                        job["job_id"], prior_retries,
                    )
            except Exception:
                pass
        # Small gap between jobs so we don't starve the scheduler
        time.sleep(2)


if __name__ == "__main__":
    main()
