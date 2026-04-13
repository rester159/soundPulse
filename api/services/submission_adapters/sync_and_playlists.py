"""
Sync marketplaces + playlist pitching adapters.

Sync marketplaces (musicbed, marmoset, artlist):
  - Playwright portals where the CEO uploads a track for licensing
    curation. Each has its own review pipeline — we upload and wait
    for the platform's editorial team to approve or reject.

Playlist pitching (groover, playlistpush, spotify_editorial,
apple_music_for_artists):
  - All Playwright. Spotify for Artists and Apple Music for Artists
    specifically require the distributor to be live first (per
    SUBMISSION_DEPS dependency graph).

All 7 share the same portal flow — one PortalConfig per target.
"""
from __future__ import annotations

from .playwright_distributors import PortalConfig, _run_portal_flow
from api.services.external_submission_agent import register_adapter


# ---- Sync marketplaces ----

MUSICBED = PortalConfig(
    target_service="musicbed",
    signin_url="https://www.musicbed.com/login",
    upload_url="https://www.musicbed.com/artist/upload",
    username_env="MUSICBED_USERNAME",
    password_env="MUSICBED_PASSWORD",
)

MARMOSET = PortalConfig(
    target_service="marmoset",
    signin_url="https://www.marmosetmusic.com/login",
    upload_url="https://www.marmosetmusic.com/submit",
    username_env="MARMOSET_USERNAME",
    password_env="MARMOSET_PASSWORD",
)

ARTLIST = PortalConfig(
    target_service="artlist",
    signin_url="https://artlist.io/login",
    upload_url="https://artlist.io/submit",
    username_env="ARTLIST_USERNAME",
    password_env="ARTLIST_PASSWORD",
)


@register_adapter("musicbed")
async def musicbed(db, subject_row, target):
    return await _run_portal_flow(db, subject_row, MUSICBED)


@register_adapter("marmoset")
async def marmoset(db, subject_row, target):
    return await _run_portal_flow(db, subject_row, MARMOSET)


@register_adapter("artlist")
async def artlist(db, subject_row, target):
    return await _run_portal_flow(db, subject_row, ARTLIST)


# ---- Playlist pitching ----

GROOVER = PortalConfig(
    target_service="groover",
    signin_url="https://groover.co/login",
    upload_url="https://groover.co/send",
    username_env="GROOVER_USERNAME",
    password_env="GROOVER_PASSWORD",
)

PLAYLISTPUSH = PortalConfig(
    target_service="playlistpush",
    signin_url="https://www.playlistpush.com/login",
    upload_url="https://www.playlistpush.com/campaign/new",
    username_env="PLAYLISTPUSH_USERNAME",
    password_env="PLAYLISTPUSH_PASSWORD",
)

SPOTIFY_EDITORIAL = PortalConfig(
    target_service="spotify_editorial",
    signin_url="https://artists.spotify.com/",
    upload_url="https://artists.spotify.com/upcoming",
    username_env="SPOTIFY_FOR_ARTISTS_USERNAME",
    password_env="SPOTIFY_FOR_ARTISTS_PASSWORD",
)

APPLE_MUSIC_EDITORIAL = PortalConfig(
    target_service="apple_music_for_artists",
    signin_url="https://artists.apple.com/",
    upload_url="https://artists.apple.com/promote",
    username_env="APPLE_MUSIC_USERNAME",
    password_env="APPLE_MUSIC_PASSWORD",
)


@register_adapter("groover")
async def groover(db, subject_row, target):
    return await _run_portal_flow(db, subject_row, GROOVER)


@register_adapter("playlistpush")
async def playlistpush(db, subject_row, target):
    return await _run_portal_flow(db, subject_row, PLAYLISTPUSH)


@register_adapter("spotify_editorial")
async def spotify_editorial(db, subject_row, target):
    return await _run_portal_flow(db, subject_row, SPOTIFY_EDITORIAL)


@register_adapter("apple_music_for_artists")
async def apple_music_for_artists(db, subject_row, target):
    return await _run_portal_flow(db, subject_row, APPLE_MUSIC_EDITORIAL)
