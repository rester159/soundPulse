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


# ---- Vocal entry detection (Suno side, post-Demucs) -----------------
#
# Finds the first time the singer actually starts singing in the
# isolated vocals stem. This replaces the old phase-correlation trick,
# which only worked when the two files were roughly head-aligned — it
# breaks when Suno's intro is 4 bars and the user's instrumental intro
# is 16 bars.
#
# Stack:
#   (1) silero-vad on 16 kHz downsampled vocals stem → first speech
#       window. Silero is a ~2 MB PyTorch model trained on voice
#       activity (speech and singing); it rejects Demucs drum/bass
#       bleed that naive RMS-threshold picks up.
#   (2) librosa.pyin pitch-stability check on the flagged window.
#       Singing has a clean fundamental; leakage has chaotic pitch.
#       Drops the remaining false positives.
#   (3) Snap to the nearest downbeat using librosa.beat.beat_track
#       so the vocal always enters on-grid.

def _detect_vocal_entry_seconds(vocal_stem_path: Path) -> float | None:
    """
    Return the timestamp (seconds from t=0) where the singer starts
    singing in the Demucs vocals stem, or None if we can't find one.

    Three-stage detection:
      1. silero-vad on a 16 kHz mono downsample
      2. pyin pitch-stability verification (filters Demucs bleed)
      3. downbeat snap via librosa.beat.beat_track

    Graceful: any exception returns None and the caller falls back to
    an unaligned mix.
    """
    import librosa
    import numpy as np

    # Stage 1 — silero-vad. Load the stem at 16 kHz mono (silero's
    # native sample rate — it's trained on 16 kHz speech). librosa
    # resamples on load; cheap.
    y16, _sr16 = librosa.load(str(vocal_stem_path), sr=16000, mono=True)
    try:
        from silero_vad import load_silero_vad, get_speech_timestamps
        import torch
        vad_model = load_silero_vad()
        # silero expects a torch tensor
        speech_ts = get_speech_timestamps(
            torch.from_numpy(y16),
            vad_model,
            sampling_rate=16000,
            threshold=0.5,
            min_speech_duration_ms=250,
            min_silence_duration_ms=150,
        )
    except Exception as e:
        log.warning("silero-vad unavailable (%s) — falling back to RMS split", e)
        # Fallback: librosa.effects.split finds non-silent intervals.
        # Less accurate (false positives on drum bleed) but shipped as
        # a backup so we still produce a value.
        intervals = librosa.effects.split(y16, top_db=25, frame_length=2048, hop_length=512)
        if len(intervals) == 0:
            return None
        speech_ts = [
            {"start": int(intervals[0][0]), "end": int(intervals[0][1])}
        ]

    if not speech_ts:
        return None

    # Stage 2 — pyin verification on the first candidate window. Only
    # accept it if the pitch is stable in the first 250 ms (singing
    # has a clean fundamental; Demucs bleed has chaotic/no pitch).
    for window in speech_ts:
        start_sample = window["start"]
        start_seconds = start_sample / 16000.0
        # Reject the first 300 ms of the file — that's ring-down from
        # Demucs and not real vocal content.
        if start_seconds < 0.3:
            continue
        # Slice a 400 ms window and run pyin on it at the native rate.
        # Load from the original file at its native sr for better
        # pyin resolution.
        try:
            y_full, sr_full = librosa.load(
                str(vocal_stem_path),
                sr=None,
                mono=True,
                offset=start_seconds,
                duration=0.4,
            )
            if len(y_full) < sr_full // 4:
                continue
            f0, voiced_flag, voiced_prob = librosa.pyin(
                y_full,
                fmin=float(librosa.note_to_hz("C2")),  # 65 Hz
                fmax=float(librosa.note_to_hz("C6")),  # 1047 Hz
                sr=sr_full,
                frame_length=1024,
            )
            # Require >40% of frames to be voiced with prob > 0.5
            if voiced_prob is None or len(voiced_prob) == 0:
                continue
            voiced_ratio = float(np.nanmean(voiced_prob > 0.5))
            if voiced_ratio < 0.4:
                continue
        except Exception as e:
            log.warning("pyin verify failed on window@%.2fs (%s) — accepting silero", start_seconds, e)

        # Stage 3 — snap to nearest downbeat on the full stem (22050 Hz
        # is enough for beat tracking).
        try:
            y_beat, sr_beat = librosa.load(str(vocal_stem_path), sr=22050, mono=True)
            tempo, beat_frames = librosa.beat.beat_track(y=y_beat, sr=sr_beat, hop_length=512)
            beat_times = librosa.frames_to_time(beat_frames, sr=sr_beat, hop_length=512)
            if len(beat_times) > 0:
                # Pick the beat closest to start_seconds
                nearest = min(beat_times, key=lambda t: abs(t - start_seconds))
                # Only snap if within 200 ms — otherwise the beat grid
                # isn't trustworthy on a vocal stem
                if abs(nearest - start_seconds) < 0.2:
                    return float(nearest)
        except Exception as e:
            log.warning("downbeat snap failed (%s) — using raw silero timestamp", e)

        return float(start_seconds)

    return None


# ---- Instrumental entry detection (no-vocals side) ------------------
#
# Finds the timestamp where verse 1 should start on the CEO's
# instrumental, so we can align the vocal to land on the right bar.
# Hard problem — there's no signal that says "verse starts here".
# Best-effort heuristic combining two signals:
#
#   (a) Agglomerative segmentation on CQT features. The second-longest
#       segment boundary usually marks the end of the intro.
#   (b) Spectral flatness jump. Intros are harmonic (low flatness);
#       verses add percussion (higher flatness). First big jump often
#       == "beat drops".
#
# We vote between the two. When they agree within 2 s, confidence is
# high. When they disagree, we return the earlier one and flag low
# confidence so the UI can suggest CEO correction.

def _detect_instrumental_entry_seconds(instr_path: Path) -> tuple[float | None, str]:
    """
    Return (entry_seconds, method) where method is a short tag
    describing which signal won. method='none' if detection failed.
    """
    import librosa
    import numpy as np

    try:
        y, sr = librosa.load(str(instr_path), sr=22050, mono=True, duration=90.0)
    except Exception as e:
        log.warning("instrumental load failed: %s", e)
        return None, "none"

    if len(y) < sr * 4:  # shorter than 4 s — give up
        return None, "none"

    candidates: list[tuple[float, str]] = []

    # Signal (a): agglomerative segmentation
    try:
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=512)
        # 5 segments is a reasonable prior for a 90-s window of music
        boundaries = librosa.segment.agglomerative(chroma, k=5)
        boundary_times = librosa.frames_to_time(boundaries, sr=sr, hop_length=512)
        # Skip t=0 (always present); take the first boundary > 2 s
        for t in boundary_times:
            if t > 2.0:
                candidates.append((float(t), "agglomerative"))
                break
    except Exception as e:
        log.warning("agglomerative seg failed: %s", e)

    # Signal (b): spectral flatness jump
    try:
        flatness = librosa.feature.spectral_flatness(y=y, hop_length=512)[0]
        # Smooth with a 1-s median filter to reject transient spikes
        win = int(sr / 512)  # frames per second at hop=512
        if len(flatness) > 2 * win:
            smoothed = np.convolve(flatness, np.ones(win) / win, mode="same")
            # Find the first frame where smoothed jumps > 50% above
            # the median of the first 2 seconds
            baseline = float(np.median(smoothed[:2 * win]))
            jump_threshold = baseline * 1.5
            for i in range(2 * win, len(smoothed)):
                if smoothed[i] > jump_threshold:
                    t = i * 512 / sr
                    if t > 2.0:
                        candidates.append((float(t), "flatness_jump"))
                        break
    except Exception as e:
        log.warning("spectral flatness failed: %s", e)

    if not candidates:
        return None, "none"

    # Vote: if both signals agree within 2 s, use the earlier one with
    # high confidence. If they disagree, return the earlier one with
    # the method tag 'low_confidence'.
    if len(candidates) == 1:
        return candidates[0][0], candidates[0][1]

    t1, m1 = candidates[0]
    t2, m2 = candidates[1]
    if abs(t1 - t2) < 2.0:
        earlier = min(t1, t2)
        return earlier, f"{m1}+{m2}"
    earlier = min(t1, t2)
    return earlier, f"low_confidence:{m1 if t1 < t2 else m2}"


def _analyze_instrumental_full(instr_path: Path) -> dict:
    """Run the full librosa analysis on an instrumental: BPM, key
    (via chroma), duration, and vocal-entry estimate. Returns a dict
    shaped for the instrumentals.analysis_json column."""
    import librosa
    import numpy as np

    result: dict = {}
    try:
        bpm = _detect_bpm(instr_path)
        result["detected_bpm"] = round(bpm, 2)
    except Exception as e:
        log.warning("instrumental BPM detect failed: %s", e)

    try:
        y, sr = librosa.load(str(instr_path), sr=22050, mono=True)
        result["detected_duration_seconds"] = round(len(y) / sr, 3)
        # Crude key detection: average chroma → most energetic pitch class
        # This is not Krumhansl-Schmuckler, but it's free and usable as
        # a hint field. The blueprint/assignment engine can override.
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        pitch_class_energy = chroma.mean(axis=1)
        idx = int(np.argmax(pitch_class_energy))
        pitch_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        result["detected_key_pitch_class"] = pitch_names[idx]
    except Exception as e:
        log.warning("instrumental duration/key detect failed: %s", e)

    try:
        entry_seconds, method = _detect_instrumental_entry_seconds(instr_path)
        if entry_seconds is not None:
            result["vocal_entry_seconds"] = round(entry_seconds, 3)
            result["vocal_entry_method"] = method
    except Exception as e:
        log.warning("instrumental entry detect failed: %s", e)

    return result


def _fetch_instrumental_analysis(instrumental_id: str) -> dict | None:
    """GET the cached analysis for an instrumental from the main API.
    Returns {vocal_entry_seconds, vocal_entry_source, analysis_json,
    analyzed_at} or None if uncached/unknown."""
    try:
        res = _api_request("GET", f"/api/v1/admin/instrumentals/{instrumental_id}/analysis")
        return res if res and res.get("analyzed_at") else None
    except Exception as e:
        log.warning("fetch instrumental analysis failed: %s", e)
        return None


def _post_instrumental_analysis(instrumental_id: str, payload: dict) -> None:
    """POST detected features back to the main API so the next job
    using this instrumental reads from cache. payload shape:
      {vocal_entry_seconds: float|None, analysis_json: dict}"""
    try:
        _api_request(
            "POST",
            f"/api/v1/admin/instrumentals/{instrumental_id}/analysis",
            payload,
        )
    except Exception as e:
        log.warning("post instrumental analysis failed: %s", e)


def _download_existing_stem(song_id: str, stem_type: str, target: Path) -> None:
    """Download a previously-stored song_stems row for remix_only jobs."""
    _download(
        f"/api/v1/admin/songs/{song_id}/stems/{stem_type}.mp3",
        target,
    )


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

def _align_vocals_to_instrumental(
    vocal_path: Path,
    instr_path: Path,
    instrumental_id: str | None,
    alignment_note: dict,
    tmp: Path,
) -> Path:
    """
    Given a Demucs vocals stem and the real instrumental, compute:
      (a) vocal entry time in the stem (silero+pyin+beat-snap)
      (b) intended vocal entry time in the instrumental (cache → auto)
    and return a new vocals file shifted so the two entry points
    coincide. Falls back to the original vocal_path on any failure.

    alignment_note is mutated in place for structured logging / ack.
    """
    # (a) Find vocal entry in the Demucs output
    try:
        t_voc_suno = _detect_vocal_entry_seconds(vocal_path)
        alignment_note["suno_vocal_entry_seconds"] = (
            round(t_voc_suno, 3) if t_voc_suno is not None else None
        )
        log.info("suno vocal entry: %s", t_voc_suno)
    except Exception as e:
        log.warning("suno vocal entry detect failed: %s", e)
        t_voc_suno = None
        alignment_note["suno_entry_error"] = str(e)[:200]

    if t_voc_suno is None:
        return vocal_path

    # (b) Intended vocal entry on the instrumental. Prefer the
    # CEO-set / cached value over re-running librosa every time.
    t_instr_entry: float | None = None
    cache_hit = False
    if instrumental_id:
        cached = _fetch_instrumental_analysis(instrumental_id)
        if cached and cached.get("vocal_entry_seconds") is not None:
            t_instr_entry = float(cached["vocal_entry_seconds"])
            alignment_note["instr_entry_source"] = (
                cached.get("vocal_entry_source") or "cache"
            )
            cache_hit = True
            log.info("instr vocal entry from cache: %.3f s (source=%s)",
                     t_instr_entry, alignment_note["instr_entry_source"])

    if t_instr_entry is None:
        # Cache miss — run full librosa analysis on the instrumental
        # and push the results back to the API for future jobs.
        analysis = _analyze_instrumental_full(instr_path)
        if "vocal_entry_seconds" in analysis:
            t_instr_entry = float(analysis["vocal_entry_seconds"])
            alignment_note["instr_entry_source"] = "auto"
            alignment_note["instr_entry_method"] = analysis.get(
                "vocal_entry_method", "unknown"
            )
            log.info("instr vocal entry auto-detected: %.3f s (%s)",
                     t_instr_entry, alignment_note["instr_entry_method"])
        if instrumental_id and analysis:
            _post_instrumental_analysis(
                instrumental_id,
                {
                    "analysis_json": analysis,
                    "vocal_entry_seconds": analysis.get("vocal_entry_seconds"),
                    "vocal_entry_source": (
                        "auto" if "vocal_entry_seconds" in analysis else None
                    ),
                },
            )

    if t_instr_entry is None:
        log.warning("no instrumental entry found — mixing vocals head-aligned")
        return vocal_path

    alignment_note["instr_vocal_entry_seconds"] = round(t_instr_entry, 3)
    # Shift the vocal so t_voc_suno lands on t_instr_entry
    shift = t_instr_entry - t_voc_suno
    alignment_note["entry_shift_seconds"] = round(shift, 3)
    log.info("entry shift: %+.3f s (suno=%.3f → instr=%.3f%s)",
             shift, t_voc_suno, t_instr_entry, " [cache]" if cache_hit else "")

    if abs(shift) < 0.010:
        return vocal_path

    aligned_vocals = tmp / "vocals_entry_locked.mp3"
    try:
        if shift > 0:
            # Vocal comes in earlier than desired — pad silence
            _trim_or_pad_start(vocal_path, aligned_vocals, pad_start_seconds=shift)
        else:
            # Vocal comes in later than desired — trim head
            _trim_or_pad_start(vocal_path, aligned_vocals, trim_start_seconds=-shift)
        return aligned_vocals
    except Exception as e:
        log.warning("entry-point shift failed (%s) — mixing as-is", e)
        return vocal_path


def _process_remix_only(job: dict, tmp: Path) -> None:
    """
    Remix-only flow: skip Demucs (15+ min), reuse the cached vocals_only
    stem from song_stems, re-fetch the (possibly nudged) vocal_entry
    from the instrumentals table, re-apply the entry-point shift, and
    re-mix. Runs in ~5-10 s instead of ~15 min.
    """
    job_id = job["job_id"]
    song_id = job["song_id"]
    src_instr = job.get("source_instrumental_url")
    instrumental_id = job.get("source_instrumental_id")

    if not src_instr:
        raise RuntimeError("remix_only requires an instrumental URL")

    log.info("REMIX-ONLY JOB %s (song=%s)", job_id, song_id)

    vocals_path = tmp / "vocals_only_cached.mp3"
    instr_path = tmp / "instrumental.mp3"
    log.info("download vocals_only from cache")
    _download_existing_stem(song_id, "vocals_only", vocals_path)
    log.info("download instrumental")
    _download(src_instr, instr_path)

    alignment_note: dict = {"job_type": "remix_only"}
    aligned_vocals = _align_vocals_to_instrumental(
        vocals_path, instr_path, instrumental_id, alignment_note, tmp
    )

    final_mixed_path = tmp / "final_mixed.mp3"
    _ffmpeg_mix(aligned_vocals, instr_path, final_mixed_path)
    log.info("remix alignment: %s", json.dumps(alignment_note))

    # Ack with the new final_mixed only — vocals_only + suno_original
    # are unchanged and remain on the original row.
    stems_payload = [{
        "stem_type": "final_mixed",
        "content_type": "audio/mpeg",
        "audio_base64": _b64(final_mixed_path),
        "duration_seconds": _duration_seconds(final_mixed_path),
    }]
    log.info("ack %s (remix) with %d stems", job_id, len(stems_payload))
    ack(job_id, stems_payload)


def process_job(job: dict) -> None:
    job_type = job.get("job_type", "full")
    with tempfile.TemporaryDirectory(prefix="stem-") as tdir:
        tmp = Path(tdir)
        if job_type == "remix_only":
            _process_remix_only(job, tmp)
            return
        _process_full(job, tmp)


def _process_full(job: dict, tmp: Path) -> None:
    """Full pipeline: download → tempo-lock → Demucs → entry-lock → mix."""
    job_id = job["job_id"]
    song_id = job.get("song_id")
    src_audio = job["source_audio_url"]
    src_instr = job.get("source_instrumental_url")
    instrumental_id = job.get("source_instrumental_id")
    song_title = job.get("song_title", "")

    log.info("JOB %s (song=%s title=%r)", job_id, song_id, song_title)

    suno_path = tmp / "suno.mp3"
    instr_path: Path | None = tmp / "instrumental.mp3" if src_instr else None

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
    alignment_note: dict = {"job_type": "full"}
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

    # 5. Entry-point-lock pre-mix pass: find vocal entry in the Demucs
    #    stem, find intended entry on the real instrumental (cache or
    #    auto-detect), then shift vocals so the two timestamps match.
    #    This is the fix for structural intro-length mismatches that
    #    the old phase-correlation approach couldn't handle.
    if instr_path is not None and instr_path.exists():
        try:
            vocal_path = _align_vocals_to_instrumental(
                vocal_path, instr_path, instrumental_id, alignment_note, tmp,
            )
        except Exception as e:
            log.warning("entry-lock failed (%s) — mixing as-is", e)
            alignment_note["entry_lock_error"] = str(e)[:200]

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

    # 7. Build stems payload
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
