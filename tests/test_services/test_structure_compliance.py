"""
Pure-math tests for structure compliance measurement (task #109 Phase 6).

The librosa-driven path is tested only via the math + scoring layer;
real audio decoding is exercised manually against the Y3K regen output
(see scripts/measure_structure_compliance.py for the CLI). This file
covers the deterministic units: expected_section_starts and
score_compliance.
"""
from __future__ import annotations

import pytest

from scripts.measure_structure_compliance import (
    BAR_TOLERANCE,
    expected_section_starts,
    score_compliance,
)


POP_STRUCTURE = [
    {"name": "Intro",      "bars": 8,  "vocals": False},
    {"name": "Verse 1",    "bars": 16, "vocals": True},
    {"name": "Pre-chorus", "bars": 4,  "vocals": True},
    {"name": "Chorus",     "bars": 8,  "vocals": True},
]


# --- expected_section_starts ----------------------------------------------

def test_expected_starts_at_120_bpm():
    """At 120 BPM, 1 bar in 4/4 = 2.0 seconds. Intro 8 bars -> Verse
    starts at 16.0s, Pre-chorus at 16+32=48.0s, Chorus at 48+8=56.0s."""
    starts = expected_section_starts(POP_STRUCTURE, bpm=120.0)
    assert starts == [0.0, 16.0, 48.0, 56.0]


def test_expected_starts_at_115_bpm_realistic_pop():
    """The 'pop' seed targets ~115 BPM. Intro 8 bars at 115 BPM:
    8 * (60/115) * 4 = 16.696s. Verse should start there."""
    starts = expected_section_starts(POP_STRUCTURE, bpm=115.0)
    assert starts[0] == 0.0
    assert abs(starts[1] - (8 * 60 / 115 * 4)) < 0.001


def test_expected_starts_empty_returns_empty():
    assert expected_section_starts([], bpm=120.0) == []


def test_expected_starts_rejects_zero_bpm():
    with pytest.raises(ValueError, match="positive"):
        expected_section_starts(POP_STRUCTURE, bpm=0)


# --- score_compliance -----------------------------------------------------

def test_score_perfect_when_detected_matches_expected():
    """Detected boundaries land exactly at expected -> 100% pass."""
    bpm = 120.0
    expected = expected_section_starts(POP_STRUCTURE, bpm=bpm)
    detected = list(expected)  # exact match
    report = score_compliance(POP_STRUCTURE, expected, detected, bpm)
    assert report.score == 1.0
    assert report.sections_passed == 4
    assert all(v.passed for v in report.section_verdicts)


def test_score_full_pass_when_within_one_bar():
    """At 120 BPM, 1 bar = 2.0s. A detected boundary 1.5s off (= 0.75 bar)
    is still inside the +-1 bar tolerance -> still passes."""
    bpm = 120.0
    expected = expected_section_starts(POP_STRUCTURE, bpm=bpm)
    # nudge each detected boundary 1.5 seconds late
    detected = [t + 1.5 for t in expected]
    report = score_compliance(POP_STRUCTURE, expected, detected, bpm)
    assert report.score == 1.0
    for v in report.section_verdicts:
        assert v.delta_bars == pytest.approx(0.75, abs=0.001)
        assert v.passed


def test_score_fails_when_every_detected_is_more_than_one_bar_away():
    """At 120 BPM, 1 bar = 2.0s. Spread the detected boundaries far enough
    from every expected that nearest-neighbor matching always lands >1 bar
    away -> score 0.0."""
    bpm = 120.0
    expected = expected_section_starts(POP_STRUCTURE, bpm=bpm)
    # Detected boundaries placed in gaps between expected slots and
    # >1 bar (>2s) from the nearest expected. Expected = [0, 16, 48, 56];
    # placing detected at [8, 32, 80, 100] keeps every expected at least
    # 8s (4 bars) away from the nearest detected.
    detected = [8.0, 32.0, 80.0, 100.0]
    report = score_compliance(POP_STRUCTURE, expected, detected, bpm)
    assert report.score == 0.0
    assert report.sections_passed == 0
    for v in report.section_verdicts:
        assert v.delta_bars > BAR_TOLERANCE
        assert not v.passed


def test_score_partial_pass_some_in_some_out():
    """Two boundaries land cleanly, two drift far. Pick detected positions
    that are unambiguously nearest one expected each so nearest-neighbor
    behavior doesn't double-bind."""
    bpm = 120.0
    expected = expected_section_starts(POP_STRUCTURE, bpm=bpm)  # [0, 16, 48, 56]
    detected = [
        0.0,    # exact match to exp 0.0 -> pass
        17.0,   # 0.5 bar from exp 16.0 -> pass
        38.0,   # 5 bars from exp 48.0 (nearest) -> fail
        80.0,   # 12 bars from exp 56.0 (nearest) -> fail
    ]
    report = score_compliance(POP_STRUCTURE, expected, detected, bpm)
    assert report.score == 0.5
    assert report.sections_passed == 2
    assert [v.passed for v in report.section_verdicts] == [True, True, False, False]


def test_score_handles_empty_detected_as_all_fail():
    bpm = 120.0
    expected = expected_section_starts(POP_STRUCTURE, bpm=bpm)
    report = score_compliance(POP_STRUCTURE, expected, [], bpm)
    assert report.score == 0.0
    assert all(v.detected_start_sec is None for v in report.section_verdicts)
    assert all(not v.passed for v in report.section_verdicts)


def test_compliance_label_passing_at_70_percent():
    """The plan locks 0.70 as the promote-to-default gate."""
    bpm = 120.0
    expected = expected_section_starts(POP_STRUCTURE, bpm=bpm)
    # 3 of 4 land cleanly, 1 drifts -> score 0.75 -> passing
    detected = [expected[0], expected[1], expected[2], expected[3] + 5.0]
    report = score_compliance(POP_STRUCTURE, expected, detected, bpm)
    assert report.score == 0.75
    assert report.as_dict()["compliance_label"] == "passing"


def test_compliance_label_failing_below_70_percent():
    bpm = 120.0
    expected = expected_section_starts(POP_STRUCTURE, bpm=bpm)
    detected = [expected[0], expected[1] + 5.0, expected[2] + 5.0, expected[3] + 5.0]
    report = score_compliance(POP_STRUCTURE, expected, detected, bpm)
    assert report.score == 0.25
    assert report.as_dict()["compliance_label"] == "failing"


def test_bar_tolerance_is_one():
    """Regression guard: the plan locks +-1 bar as the per-section
    pass threshold. Bumping this would let near-misses count as wins
    and obscure real structural drift."""
    assert BAR_TOLERANCE == 1.0
