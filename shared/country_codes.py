"""
Canonical country code handling.

Every scraper talks to external APIs with different expectations for the
country code parameter:
  - Chartmetric's /api/charts/spotify wants `country_code=us` (lowercase)
  - Chartmetric's /api/charts/amazon wants `code2=US` (uppercase, different param!)
  - Chartmetric's /api/cities wants `country_code=US` (uppercase)
  - Spotify Web API uses `market=US` (uppercase)
  - Apple Music uses `storefront=us` (lowercase)

Without a canonical helper, scrapers drift into case-inconsistent params
(we had `"us"` in some files and `"US"` in others, sometimes even within
the same file — the audit flagged 5 separate call sites). This module
centralizes the normalization so every scraper calls one function and
every API gets what it expects.

Usage:
    from shared.country_codes import canonical_iso2, country_param

    # Normalize any user input to the canonical uppercase ISO-3166-1 alpha-2
    cc = canonical_iso2("  us ")    # → "US"
    cc = canonical_iso2("USA")      # → "US"  (maps common 3-letter codes)

    # Build the right (key, value) tuple for a given API target
    key, value = country_param("chartmetric_spotify")   # → ("country_code", "us")
    key, value = country_param("chartmetric_amazon")    # → ("code2", "US")
    key, value = country_param("spotify_web")           # → ("market", "US")
"""

from __future__ import annotations


# Common 3-letter → 2-letter mappings, extended as needed.
# The ISO 3166-1 standard has 249 countries; we just handle the ones
# SoundPulse actually queries. Unknown inputs are passed through.
_ISO3_TO_ISO2: dict[str, str] = {
    "USA": "US",
    "GBR": "GB",
    "DEU": "DE",
    "FRA": "FR",
    "JPN": "JP",
    "BRA": "BR",
    "MEX": "MX",
    "KOR": "KR",
    "IND": "IN",
    "CAN": "CA",
    "AUS": "AU",
    "NZL": "NZ",
    "NLD": "NL",
    "IRL": "IE",
}


def canonical_iso2(country: str | None) -> str:
    """
    Normalize a country input to canonical uppercase ISO-3166-1 alpha-2.

    Accepts:
      - 2-letter codes in any case (`us`, `US`, `Us`) → `US`
      - 3-letter codes (`USA`) → `US` (via internal mapping)
      - None or empty → empty string

    Never raises. Unknown inputs are returned uppercased as-is (better
    to pass through than to reject, since Chartmetric occasionally
    accepts non-standard codes).
    """
    if not country:
        return ""
    cleaned = country.strip().upper()
    if len(cleaned) == 3 and cleaned in _ISO3_TO_ISO2:
        return _ISO3_TO_ISO2[cleaned]
    return cleaned


# Per-API country parameter conventions.
# Key = logical target name; value = (query_param_name, case_transform).
# case_transform is "upper" or "lower".
_API_CONVENTIONS: dict[str, tuple[str, str]] = {
    # Chartmetric endpoints — case and param name vary per sub-resource
    "chartmetric_default":        ("country_code", "lower"),
    "chartmetric_spotify":        ("country_code", "lower"),
    "chartmetric_shazam":         ("country_code", "lower"),
    "chartmetric_applemusic":     ("country_code", "lower"),
    "chartmetric_itunes":         ("country_code", "lower"),
    "chartmetric_soundcloud":     ("country_code", "upper"),
    "chartmetric_amazon":         ("code2",        "upper"),
    "chartmetric_airplay":        ("country_code", "lower"),
    "chartmetric_cities":         ("country_code", "upper"),
    "chartmetric_artist_list":    ("code2",        "upper"),

    # Direct platform APIs (not going through Chartmetric)
    "spotify_web":                ("market",       "upper"),
    "apple_music":                ("storefront",   "lower"),
}


def country_param(api_target: str, country: str = "US") -> tuple[str, str]:
    """
    Return the correct `(param_name, param_value)` tuple for a given API.

    Callers use this as:
        key, value = country_param("chartmetric_amazon")
        params[key] = value

    Unknown api_target falls back to `chartmetric_default`
    (`country_code=us` lowercase) since that's the most common convention.
    """
    spec = _API_CONVENTIONS.get(api_target, _API_CONVENTIONS["chartmetric_default"])
    param_name, case = spec
    iso2 = canonical_iso2(country)
    value = iso2.lower() if case == "lower" else iso2.upper()
    return param_name, value
