"""
Measure how closely a generated audio file matches an expected
[{name, bars, vocals}] structure (task #109 Phase 6, PRD §70).

This is the "did the [STRUCTURE] block actually constrain Suno?"
verification step. The orchestrator now prepends a Suno tag block; this
script checks whether the resulting audio respects it.

Usage:
    python -m scripts.measure_structure_compliance \\
        --audio /path/to/song.mp3 \\
        --structure-json '[{"name":"Intro","bars":8,"vocals":false},...]'

Or, more typically, point at a song_id and let the script load both the
expected structure (from the orchestrator log / genre_structures) and
the audio (from songs_master.audio_url) — but for tonight we just take
both as args so it can be exercised in isolation against a downloaded
Y3K mix.

Compliance gate per the plan: pass if >=70 % of section boundaries land
within +-1 bar of the expected boundary.

Method:
  1. Detect tempo via librosa.beat.beat_track (BPM, beat times).
  2. Convert expected (bars-per-section) -> expected boundary times in
     seconds at the detected BPM, anchored at t=0.
  3. Detect section boundaries via librosa.segment.agglomerative with
     k = len(structure). This gives the boundary timestamps Suno's
     output actually changes texture at.
  4. For each expected boundary, find the nearest detected boundary
     and compute |delta| in bars.
  5. A section "passes" if its boundary is within 1.0 bar.
  6. Overall score = passing_sections / total_sections.

Notes:
  - librosa.beat.beat_track can octave-error on dense textures. Guard:
    if measured BPM is way off the expected (caller-supplied) range,
    halve/double until it's plausible. Caller can pass --bpm-hint to
    skip detection entirely.
  - Bar = 4 beats (assumes 4/4). For genres in 6/8 or 3/4 the math is
    off; the seed is currently all 4/4 so this matches.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass

import librosa
import numpy as np


BAR_TOLERANCE = 1.0  # +-N bars considered "in spec"


@dataclass
class SectionVerdict:
    name: str
    expected_bars: int
    expected_start_sec: float
    detected_start_sec: float | None
    delta_bars: float | None
    passed: bool


@dataclass
class ComplianceReport:
    bpm: float
    total_sections: int
    sections_passed: int
    score: float
    section_verdicts: list[SectionVerdict]

    def as_dict(self) -> dict:
        return {
            "bpm": round(self.bpm, 2),
            "total_sections": self.total_sections,
            "sections_passed": self.sections_passed,
            "score": round(self.score, 3),
            "compliance_label": (
                "passing" if self.score >= 0.70 else "failing"
            ),
            "verdicts": [
                {
                    "name": v.name,
                    "expected_bars": v.expected_bars,
                    "expected_start_sec": round(v.expected_start_sec, 2),
                    "detected_start_sec": (
                        round(v.detected_start_sec, 2)
                        if v.detected_start_sec is not None
                        else None
                    ),
                    "delta_bars": (
                        round(v.delta_bars, 3)
                        if v.delta_bars is not None
                        else None
                    ),
                    "passed": v.passed,
                }
                for v in self.section_verdicts
            ],
        }


def expected_section_starts(structure: list[dict], bpm: float, beats_per_bar: int = 4) -> list[float]:
    """Return the expected start time (seconds) for each section, anchored
    at t=0.0. Uses beats_per_bar=4 (4/4 time) which matches the seed.
    """
    if bpm <= 0:
        raise ValueError("bpm must be positive")
    if not structure:
        return []
    seconds_per_bar = (60.0 / bpm) * beats_per_bar
    starts: list[float] = []
    cursor = 0.0
    for sec in structure:
        starts.append(cursor)
        cursor += float(sec["bars"]) * seconds_per_bar
    return starts


def detect_bpm(y: np.ndarray, sr: int, *, bpm_hint: float | None = None) -> float:
    """Detect tempo. If a hint is provided, accept it directly (caller
    knows). Otherwise call librosa and clamp to the reasonable 60-200
    range — outside that it almost always means an octave error."""
    if bpm_hint is not None and bpm_hint > 0:
        return float(bpm_hint)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0])
    # Octave-error guard
    while bpm < 60.0:
        bpm *= 2.0
    while bpm > 200.0:
        bpm /= 2.0
    return bpm


def detect_section_starts(y: np.ndarray, sr: int, k: int) -> list[float]:
    """Use librosa.segment.agglomerative to find k section boundaries
    in seconds. Returns the start times (frame[0] is always 0.0 from
    librosa, included as the first section's start)."""
    if k <= 0:
        return []
    # Compute a chroma feature, then agglomerative segmentation
    hop_length = 512
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length)
    boundary_frames = librosa.segment.agglomerative(chroma, k)
    boundary_times = librosa.frames_to_time(
        boundary_frames, sr=sr, hop_length=hop_length
    )
    return [float(t) for t in boundary_times]


def score_compliance(
    structure: list[dict],
    expected_starts: list[float],
    detected_starts: list[float],
    bpm: float,
    *,
    beats_per_bar: int = 4,
) -> ComplianceReport:
    """Match each expected boundary to its nearest detected boundary,
    measure the delta in bars, and tally how many fall within the
    BAR_TOLERANCE."""
    seconds_per_bar = (60.0 / bpm) * beats_per_bar
    verdicts: list[SectionVerdict] = []
    for sec, exp in zip(structure, expected_starts):
        if not detected_starts:
            verdicts.append(SectionVerdict(
                name=sec["name"],
                expected_bars=int(sec["bars"]),
                expected_start_sec=exp,
                detected_start_sec=None,
                delta_bars=None,
                passed=False,
            ))
            continue
        # Nearest detected boundary
        deltas = [abs(d - exp) for d in detected_starts]
        nearest_idx = int(np.argmin(deltas))
        nearest = detected_starts[nearest_idx]
        delta_seconds = abs(nearest - exp)
        delta_bars = delta_seconds / seconds_per_bar
        verdicts.append(SectionVerdict(
            name=sec["name"],
            expected_bars=int(sec["bars"]),
            expected_start_sec=exp,
            detected_start_sec=nearest,
            delta_bars=delta_bars,
            passed=delta_bars <= BAR_TOLERANCE,
        ))
    passed = sum(1 for v in verdicts if v.passed)
    score = passed / len(verdicts) if verdicts else 0.0
    return ComplianceReport(
        bpm=bpm,
        total_sections=len(verdicts),
        sections_passed=passed,
        score=score,
        section_verdicts=verdicts,
    )


def measure_audio_compliance(
    audio_path: str,
    structure: list[dict],
    *,
    bpm_hint: float | None = None,
) -> ComplianceReport:
    """End-to-end: load audio, detect tempo, detect boundaries, score."""
    y, sr = librosa.load(audio_path, sr=None, mono=True)
    bpm = detect_bpm(y, sr, bpm_hint=bpm_hint)
    expected = expected_section_starts(structure, bpm)
    detected = detect_section_starts(y, sr, k=len(structure))
    return score_compliance(structure, expected, detected, bpm)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--audio", required=True, help="Path to the generated audio file")
    p.add_argument(
        "--structure-json",
        required=True,
        help="JSON list of {name, bars, vocals} sections (the [STRUCTURE] block)",
    )
    p.add_argument(
        "--bpm-hint",
        type=float,
        default=None,
        help="Override BPM detection (avoids librosa octave errors)",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        structure = json.loads(args.structure_json)
    except json.JSONDecodeError as exc:
        print(f"ERROR: --structure-json is not valid JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(structure, list) or not structure:
        print("ERROR: --structure-json must be a non-empty list", file=sys.stderr)
        return 2

    report = measure_audio_compliance(args.audio, structure, bpm_hint=args.bpm_hint)
    print(json.dumps(report.as_dict(), indent=2))
    return 0 if report.score >= 0.70 else 1


if __name__ == "__main__":
    sys.exit(main())
