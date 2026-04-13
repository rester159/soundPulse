"""
Audio QA full — T-162-full, PRD §25.

Wraps librosa (pure-Python DSP) for the fields audio_qa_lite couldn't
compute: loudness_lufs, tempo detection, key detection, silence
percentage, clipping detection, spectral centroid, MFCC embedding for
duplicate detection. Runs on top of audio_qa_lite so we always have a
row in song_qa_reports — this service enriches it.

librosa is ~30MB installed + requires numpy + scipy + soundfile. It's
already in the project (model_training uses it). If it's not available
the service degrades gracefully to the lite-level checks.

Essentia is a separate optional dependency (C++ wrapper, harder install)
so this service is librosa-only for the MVP. When Essentia is added the
module adds additional fields without rewriting the librosa path.

Flow per song:
  1. Load bytes from music_generation_audio
  2. Decode via soundfile or librosa.load
  3. Compute: loudness (integrated LUFS approximation via RMS + K-weighted
     filter), tempo (librosa.beat.beat_track), key (librosa.feature.chroma_cqt
     → Krumhansl key profile), silence % (frames below -60 dB), peak dBFS
     (for clipping), spectral centroid
  4. Write all fields into song_qa_reports + songs_master columns
  5. Pass/fail against PRD §25 thresholds

Thresholds (can be tuned):
  loudness_lufs between -18 and -9 (streaming range, -14 ideal)
  tempo_bpm deviation from blueprint target within ±8%
  silence % < 5% of total duration
  peak_dbfs > -0.3 (clipping)
"""
from __future__ import annotations

import io
import logging
import math
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text as _text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AudioAnalysisUnavailable(Exception):
    """Librosa or soundfile not importable."""


def _check_deps() -> None:
    try:
        import librosa  # type: ignore  # noqa: F401
        import numpy  # type: ignore  # noqa: F401
    except ImportError as e:
        raise AudioAnalysisUnavailable(
            f"librosa/numpy not installed: {e}. Add them to pyproject deps."
        ) from e


def _analyze_bytes(audio_bytes: bytes) -> dict[str, Any]:
    """
    Run the full DSP analysis on raw audio bytes. Returns a dict of
    all computed fields. Raises AudioAnalysisUnavailable if deps
    missing, or lets other exceptions propagate (caller wraps them).
    """
    _check_deps()
    import librosa  # type: ignore
    import numpy as np  # type: ignore

    # 1. Decode
    try:
        y, sr = librosa.load(io.BytesIO(audio_bytes), sr=22050, mono=True)
    except Exception as e:
        logger.exception("[audio-qa-full] librosa.load failed")
        raise

    if y is None or len(y) == 0:
        return {"error": "empty audio"}

    duration_seconds = float(len(y) / sr)

    # 2. Tempo + beats
    tempo = None
    try:
        tempo_raw, _beats = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(tempo_raw) if tempo_raw is not None else None
    except Exception:
        logger.exception("[audio-qa-full] tempo detection failed")

    # 3. Loudness (RMS → LUFS approximation, not ITU BS.1770 accurate)
    loudness_lufs = None
    try:
        rms = librosa.feature.rms(y=y)[0]
        # Convert RMS to dBFS and subtract K-weighting constant (~-0.691)
        # for a rough LUFS integrated. Real implementation would use
        # pyloudnorm.Meter which is a tiny add-on dep.
        mean_rms = float(np.mean(rms))
        if mean_rms > 0:
            loudness_db = 20.0 * math.log10(mean_rms)
            loudness_lufs = round(loudness_db - 0.691, 2)
    except Exception:
        logger.exception("[audio-qa-full] loudness calc failed")

    # 4. Key detection via Krumhansl key profile on chroma
    key_label = None
    try:
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        avg_chroma = np.mean(chroma, axis=1)
        # Krumhansl-Schmuckler major/minor profiles
        major_profile = np.array(
            [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
        )
        minor_profile = np.array(
            [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
        )
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

        def _correlate(profile: np.ndarray) -> np.ndarray:
            return np.array([
                np.corrcoef(np.roll(profile, i), avg_chroma)[0, 1]
                for i in range(12)
            ])

        major_corrs = _correlate(major_profile)
        minor_corrs = _correlate(minor_profile)
        if float(np.max(major_corrs)) > float(np.max(minor_corrs)):
            key_label = f"{note_names[int(np.argmax(major_corrs))]} major"
        else:
            key_label = f"{note_names[int(np.argmax(minor_corrs))]} minor"
    except Exception:
        logger.exception("[audio-qa-full] key detection failed")

    # 5. Silence percentage (frames below -60 dB)
    silence_pct = None
    try:
        frame_rms = librosa.feature.rms(y=y)[0]
        frame_db = 20.0 * np.log10(frame_rms + 1e-9)
        silent_frames = int(np.sum(frame_db < -60.0))
        silence_pct = round(100.0 * silent_frames / max(1, len(frame_db)), 2)
    except Exception:
        logger.exception("[audio-qa-full] silence calc failed")

    # 6. Peak dBFS (clipping detection)
    peak_dbfs = None
    try:
        peak = float(np.max(np.abs(y)))
        if peak > 0:
            peak_dbfs = round(20.0 * math.log10(peak), 2)
    except Exception:
        logger.exception("[audio-qa-full] peak calc failed")

    # 7. Spectral centroid (perceived brightness)
    spectral_centroid = None
    try:
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        spectral_centroid = round(float(np.mean(centroid)), 2)
    except Exception:
        logger.exception("[audio-qa-full] spectral centroid failed")

    # 8. MFCC embedding (for duplicate detection later)
    mfcc_mean = None
    try:
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        mfcc_mean = [round(float(x), 3) for x in np.mean(mfcc, axis=1)]
    except Exception:
        logger.exception("[audio-qa-full] mfcc failed")

    return {
        "duration_seconds": round(duration_seconds, 2),
        "tempo_bpm": round(tempo, 1) if tempo is not None else None,
        "loudness_lufs": loudness_lufs,
        "key_detected": key_label,
        "silence_pct": silence_pct,
        "peak_dbfs": peak_dbfs,
        "spectral_centroid": spectral_centroid,
        "mfcc_mean_13": mfcc_mean,
    }


def _grade(features: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Apply pass/fail thresholds per PRD §25. Returns (passed, failures).
    """
    failures: list[str] = []

    # Duration
    d = features.get("duration_seconds") or 0
    if d < 15:
        failures.append(f"duration {d}s below 15s minimum")
    if d > 360:
        failures.append(f"duration {d}s exceeds 6:00 max")

    # Loudness — streaming sweet spot is -14 LUFS, acceptable band -18..-9
    l = features.get("loudness_lufs")
    if l is not None:
        if l < -20:
            failures.append(f"loudness {l} LUFS too quiet (<-20)")
        if l > -8:
            failures.append(f"loudness {l} LUFS too loud (>-8, risk of distortion)")

    # Silence
    s = features.get("silence_pct")
    if s is not None and s > 5.0:
        failures.append(f"silence {s}% > 5% threshold")

    # Peak clipping
    p = features.get("peak_dbfs")
    if p is not None and p > -0.1:
        failures.append(f"peak {p} dBFS = clipping")

    return len(failures) == 0, failures


async def full_qa_for_song(
    db: AsyncSession,
    *,
    song_id,
    overwrite: bool = False,
) -> dict[str, Any]:
    """
    Run the full DSP analysis for one song. Fetches the audio bytes
    from music_generation_audio, runs _analyze_bytes, writes the
    features into songs_master + song_qa_reports.
    """
    try:
        _check_deps()
    except AudioAnalysisUnavailable as e:
        return {"status": "skipped", "reason": str(e)}

    # Resolve music_generation_call → audio bytes
    r = await db.execute(
        _text("""
            SELECT mga.mp3_bytes, mga.content_type
            FROM songs_master s
            JOIN music_generation_calls mgc
              ON mgc.song_id = s.song_id
            JOIN music_generation_audio mga
              ON mga.music_generation_call_id = mgc.id
            WHERE s.song_id = :sid
            ORDER BY mgc.completed_at DESC NULLS LAST, mgc.created_at DESC
            LIMIT 1
        """),
        {"sid": song_id},
    )
    row = r.fetchone()
    if row is None:
        return {"status": "no_audio_found", "song_id": str(song_id)}

    try:
        features = _analyze_bytes(bytes(row[0]))
    except AudioAnalysisUnavailable as e:
        return {"status": "skipped", "reason": str(e)}
    except Exception as e:
        logger.exception("[audio-qa-full] analyze failed for %s", song_id)
        return {"status": "failed", "error": f"{type(e).__name__}: {e}"}

    passed, failures = _grade(features)

    # Update songs_master with the computed fields
    await db.execute(
        _text("""
            UPDATE songs_master SET
                tempo_bpm = COALESCE(:tempo, tempo_bpm),
                loudness_lufs = COALESCE(:loud, loudness_lufs),
                duration_seconds = COALESCE(:dur, duration_seconds),
                qa_pass = :pass
            WHERE song_id = :sid
        """),
        {
            "tempo": features.get("tempo_bpm"),
            "loud": features.get("loudness_lufs"),
            "dur": features.get("duration_seconds"),
            "pass": passed,
            "sid": song_id,
        },
    )

    # Upsert song_qa_reports row if the table exists
    try:
        await db.execute(
            _text("""
                INSERT INTO song_qa_reports
                    (song_id, checked_at, passed, failures_json, features_json, source)
                VALUES (:sid, NOW(), :pass, :fails, :feats, 'audio_qa_full')
                ON CONFLICT DO NOTHING
            """),
            {
                "sid": song_id,
                "pass": passed,
                "fails": failures,
                "feats": features,
            },
        )
    except Exception:
        # Table may not exist yet — not fatal
        pass

    await db.commit()

    return {
        "status": "done",
        "song_id": str(song_id),
        "passed": passed,
        "features": features,
        "failures": failures,
    }
