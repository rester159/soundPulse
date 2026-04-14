"""Lesson-to-code enforcement tests.

Each test in this file asserts that a lesson documented in
`planning/lessons.md` has not been silently reintroduced somewhere in
the codebase. This is L010's prevention rule #3: lessons that are
written but not enforced don't count.

Add a new test here every time a lesson can be checked with a grep or
small static check.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRAPERS_DIR = REPO_ROOT / "scrapers"


def test_L004_chartmetric_request_delay_minimum():
    """L004: Chartmetric's token bucket needs >= 1.0s/req.

    Any Chartmetric-facing scraper that declares a `REQUEST_DELAY` class
    constant less than 1.0 triggers the token-bucket throttling that
    caused the P0 outage on 2026-04-11. This test fails fast if a new
    scraper (or a refactor) lowers the constant.
    """
    offenders: list[tuple[str, str]] = []
    pattern = re.compile(r"^\s*REQUEST_DELAY\s*=\s*([0-9]*\.?[0-9]+)", re.MULTILINE)
    for path in SCRAPERS_DIR.glob("chartmetric*.py"):
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            value = float(match.group(1))
            if value < 1.0:
                offenders.append((path.name, match.group(0).strip()))
    assert not offenders, (
        "L004 violation: Chartmetric REQUEST_DELAY must be >= 1.0s. "
        f"Offenders: {offenders}"
    )
