from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import require_admin
from api.models.api_key import ApiKey
from api.models.scraper_config import ScraperConfig

# Credential keys that can be managed via the admin UI
CREDENTIAL_KEYS = [
    "SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET",
    "CHARTMETRIC_API_KEY",
    "SHAZAM_RAPIDAPI_KEY",
    "APPLE_MUSIC_TEAM_ID", "APPLE_MUSIC_KEY_ID", "APPLE_MUSIC_PRIVATE_KEY_PATH",
    "TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET",
]
try:
    from scrapers.scheduler import trigger_now, update_job
except ImportError:
    # scrapers module not available in Docker container yet
    async def trigger_now(scraper_id: str) -> None:  # type: ignore[misc]
        raise HTTPException(503, detail="Scheduler not available in this environment")
    def update_job(scraper_id: str, interval_hours: float, enabled: bool) -> None:  # type: ignore[misc]
        pass

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ScraperConfigOut(BaseModel):
    id: str
    enabled: bool
    interval_hours: float
    last_run_at: datetime | None
    last_status: str | None
    last_error: str | None
    last_record_count: int | None
    config_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScraperConfigUpdate(BaseModel):
    enabled: bool | None = None
    interval_hours: float | None = None


# ---------------------------------------------------------------------------
# HTML admin page (no auth required — it's just static HTML)
# ---------------------------------------------------------------------------

ADMIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SoundPulse — Scraper Admin</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    background: #0f1117;
    color: #e0e0e0;
    min-height: 100vh;
    padding: 2rem;
  }
  h1 { font-size: 1.6rem; font-weight: 600; margin-bottom: 1.5rem; color: #fff; }
  .key-bar {
    display: flex; gap: .75rem; align-items: center;
    margin-bottom: 2rem; flex-wrap: wrap;
  }
  .key-bar label { font-size: .85rem; color: #999; }
  .key-bar input {
    background: #1a1d27; border: 1px solid #2a2d37; border-radius: 6px;
    padding: .5rem .75rem; color: #e0e0e0; width: 320px; font-size: .9rem;
  }
  .key-bar input:focus { outline: none; border-color: #6366f1; }
  .key-bar button {
    background: #6366f1; color: #fff; border: none; border-radius: 6px;
    padding: .5rem 1rem; cursor: pointer; font-size: .85rem; font-weight: 500;
  }
  .key-bar button:hover { background: #4f46e5; }
  table { width: 100%; border-collapse: collapse; }
  th {
    text-align: left; padding: .65rem 1rem; font-size: .75rem;
    text-transform: uppercase; letter-spacing: .05em; color: #888;
    border-bottom: 1px solid #1e2130;
  }
  td { padding: .75rem 1rem; border-bottom: 1px solid #1a1d27; font-size: .9rem; }
  tr:hover td { background: #161824; }
  .badge {
    display: inline-block; padding: .15rem .55rem; border-radius: 999px;
    font-size: .75rem; font-weight: 600; text-transform: uppercase;
  }
  .badge-success { background: #064e3b; color: #34d399; }
  .badge-error   { background: #4c1d1d; color: #f87171; }
  .badge-running { background: #1e3a5f; color: #60a5fa; }
  .badge-none    { background: #27272a; color: #a1a1aa; }
  .badge-enabled { background: #064e3b; color: #34d399; }
  .badge-disabled{ background: #4c1d1d; color: #f87171; }
  .actions { display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; }
  .btn {
    border: none; border-radius: 6px; padding: .4rem .75rem;
    font-size: .8rem; cursor: pointer; font-weight: 500; white-space: nowrap;
  }
  .btn-toggle { background: #374151; color: #e0e0e0; }
  .btn-toggle:hover { background: #4b5563; }
  .btn-run { background: #065f46; color: #34d399; }
  .btn-run:hover { background: #047857; }
  .interval-input {
    width: 60px; background: #1a1d27; border: 1px solid #2a2d37;
    border-radius: 4px; padding: .3rem .4rem; color: #e0e0e0;
    font-size: .85rem; text-align: center;
  }
  .interval-input:focus { outline: none; border-color: #6366f1; }
  .btn-interval { background: #374151; color: #e0e0e0; font-size: .75rem; }
  .btn-interval:hover { background: #4b5563; }
  .error-cell { color: #f87171; font-size: .8rem; max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .toast {
    position: fixed; bottom: 1.5rem; right: 1.5rem; padding: .75rem 1.25rem;
    border-radius: 8px; font-size: .85rem; color: #fff; opacity: 0;
    transition: opacity .3s; pointer-events: none; z-index: 999;
  }
  .toast.show { opacity: 1; }
  .toast-ok  { background: #065f46; }
  .toast-err { background: #7f1d1d; }
  .meta { margin-top: 1rem; font-size: .75rem; color: #555; }
</style>
</head>
<body>

<h1>Scraper Admin</h1>
<nav style="margin-bottom:1.5rem;display:flex;gap:1.5rem;font-size:.9rem;">
  <a href="/admin/scrapers" style="color:#6366f1;text-decoration:none;font-weight:600;">Scrapers</a>
  <a href="/admin/credentials" style="color:#6366f1;text-decoration:none;">Credentials</a>
  <a href="/admin/api-test" style="color:#6366f1;text-decoration:none;">API Test</a>
  <a href="/admin/dashboard" style="color:#6366f1;text-decoration:none;">Dashboard</a>
  <a href="/admin/scoring" style="color:#6366f1;text-decoration:none;">Scoring</a>
  <a href="/docs" style="color:#6366f1;text-decoration:none;">API Docs</a>
</nav>

<div class="key-bar">
  <label for="apiKey">Admin Key:</label>
  <input id="apiKey" type="password" placeholder="Enter admin API key" />
  <button onclick="saveKey()">Save</button>
</div>

<table>
  <thead>
    <tr>
      <th>Scraper</th>
      <th>Status</th>
      <th>Enabled</th>
      <th>Interval (hrs)</th>
      <th>Last Run</th>
      <th>Records</th>
      <th>Last Error</th>
      <th>Actions</th>
    </tr>
  </thead>
  <tbody id="tbody"></tbody>
</table>

<p class="meta" id="refreshMeta"></p>
<div class="toast" id="toast"></div>

<script>
const API = '/api/v1/admin/scraper-config';
const keyInput = document.getElementById('apiKey');
const tbody = document.getElementById('tbody');
const toastEl = document.getElementById('toast');
const metaEl = document.getElementById('refreshMeta');
let autoTimer = null;

// Persist key in localStorage
function saveKey() {
  localStorage.setItem('sp_admin_key', keyInput.value.trim());
  toast('Key saved', 'ok');
  loadData();
}

function getKey() {
  return localStorage.getItem('sp_admin_key') || '';
}

// On load, restore key
keyInput.value = getKey();

function headers() {
  return { 'Content-Type': 'application/json', 'X-API-Key': getKey() };
}

function toast(msg, type) {
  toastEl.textContent = msg;
  toastEl.className = 'toast show ' + (type === 'ok' ? 'toast-ok' : 'toast-err');
  setTimeout(() => { toastEl.className = 'toast'; }, 3000);
}

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString();
}

function statusBadge(s) {
  if (!s) return '<span class="badge badge-none">never</span>';
  const cls = s === 'success' ? 'badge-success' : s === 'error' ? 'badge-error' : 'badge-running';
  return '<span class="badge ' + cls + '">' + s + '</span>';
}

function enabledBadge(e) {
  return e
    ? '<span class="badge badge-enabled">enabled</span>'
    : '<span class="badge badge-disabled">disabled</span>';
}

async function loadData() {
  try {
    const res = await fetch(API, { headers: headers() });
    if (!res.ok) { toast('Failed to load: ' + res.status, 'err'); return; }
    const data = await res.json();
    renderTable(data);
    metaEl.textContent = 'Last refreshed: ' + new Date().toLocaleTimeString();
  } catch (e) {
    toast('Network error: ' + e.message, 'err');
  }
}

function renderTable(configs) {
  tbody.innerHTML = '';
  configs.forEach(c => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${c.id}</strong></td>
      <td>${statusBadge(c.last_status)}</td>
      <td>${enabledBadge(c.enabled)}</td>
      <td>${c.interval_hours}h</td>
      <td>${fmtDate(c.last_run_at)}</td>
      <td>${c.last_record_count != null ? c.last_record_count.toLocaleString() : '—'}</td>
      <td class="error-cell" title="${c.last_error || ''}">${c.last_error || '—'}</td>
      <td class="actions">
        <button class="btn btn-toggle" onclick="toggleEnabled('${c.id}', ${!c.enabled})">
          ${c.enabled ? 'Disable' : 'Enable'}
        </button>
        <button class="btn btn-run" onclick="runNow('${c.id}')">Run Now</button>
        <input class="interval-input" id="iv_${c.id}" type="number" min="0.5" step="0.5" value="${c.interval_hours}" />
        <button class="btn btn-interval" onclick="setInterval_('${c.id}')">Set</button>
      </td>`;
    tbody.appendChild(tr);
  });
}

async function toggleEnabled(id, val) {
  try {
    const res = await fetch(API + '/' + id, {
      method: 'PUT', headers: headers(),
      body: JSON.stringify({ enabled: val })
    });
    if (!res.ok) { toast('Update failed: ' + res.status, 'err'); return; }
    toast(id + (val ? ' enabled' : ' disabled'), 'ok');
    loadData();
  } catch (e) { toast('Error: ' + e.message, 'err'); }
}

async function setInterval_(id) {
  const v = parseFloat(document.getElementById('iv_' + id).value);
  if (!v || v < 0.5) { toast('Interval must be >= 0.5', 'err'); return; }
  try {
    const res = await fetch(API + '/' + id, {
      method: 'PUT', headers: headers(),
      body: JSON.stringify({ interval_hours: v })
    });
    if (!res.ok) { toast('Update failed: ' + res.status, 'err'); return; }
    toast(id + ' interval set to ' + v + 'h', 'ok');
    loadData();
  } catch (e) { toast('Error: ' + e.message, 'err'); }
}

async function runNow(id) {
  try {
    const res = await fetch(API + '/' + id + '/run-now', {
      method: 'POST', headers: headers()
    });
    if (res.status === 202) {
      toast(id + ' triggered', 'ok');
      setTimeout(loadData, 2000);
    } else {
      toast('Trigger failed: ' + res.status, 'err');
    }
  } catch (e) { toast('Error: ' + e.message, 'err'); }
}

// Initial load + auto-refresh
loadData();
autoTimer = setInterval(loadData, 30000);
</script>
</body>
</html>"""


@router.get("/admin/scrapers", response_class=HTMLResponse)
async def admin_scrapers_page():
    """Serve the scraper admin HTML page. No auth required."""
    return HTMLResponse(content=ADMIN_HTML)


# ---------------------------------------------------------------------------
# API Test page
# ---------------------------------------------------------------------------

API_TEST_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SoundPulse — API Test</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    background: #0f1117; color: #e0e0e0; min-height: 100vh; padding: 2rem;
  }
  h1 { font-size: 1.6rem; font-weight: 600; margin-bottom: .5rem; color: #fff; }
  h2 { font-size: 1.15rem; font-weight: 600; color: #fff; margin-bottom: 1rem; }
  nav {
    position: sticky; top: 0; z-index: 100; background: #0f1117;
    display: flex; gap: 1.5rem; font-size: .9rem;
    padding: .75rem 0; margin-bottom: 1.5rem; border-bottom: 1px solid #1e2130;
  }
  nav a { color: #6366f1; text-decoration: none; }
  nav a.active { font-weight: 600; }
  nav a:hover { text-decoration: underline; }
  .ep-desc-block {
    font-size: .8rem; color: #999; margin-bottom: .75rem; line-height: 1.55;
    padding: .5rem .75rem; background: #12141c; border-radius: 4px; border-left: 3px solid #6366f1;
  }
  .ep-desc-block strong { color: #a5b4fc; }

  .section {
    background: #1a1d27; border: 1px solid #2a2d37; border-radius: 8px;
    padding: 1.25rem 1.5rem; margin-bottom: 1.5rem;
  }
  .section-title {
    font-size: 1rem; font-weight: 600; color: #6366f1;
    border-bottom: 1px solid #2a2d37; padding-bottom: .5rem; margin-bottom: 1rem;
  }

  .endpoint { margin-bottom: 1.5rem; padding-bottom: 1.5rem; border-bottom: 1px solid #22253a; }
  .endpoint:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }

  .ep-header { display: flex; align-items: center; gap: .75rem; margin-bottom: .75rem; flex-wrap: wrap; }
  .method-badge {
    display: inline-block; padding: .2rem .6rem; border-radius: 4px;
    font-size: .75rem; font-weight: 700; text-transform: uppercase; letter-spacing: .03em;
    min-width: 42px; text-align: center;
  }
  .method-get  { background: #064e3b; color: #34d399; }
  .method-post { background: #1e3a5f; color: #60a5fa; }
  .ep-path { font-family: 'Menlo', 'Consolas', monospace; font-size: .9rem; color: #e0e0e0; }
  .ep-desc { font-size: .8rem; color: #888; margin-left: auto; }

  .params { display: flex; flex-wrap: wrap; gap: .5rem .75rem; margin-bottom: .75rem; align-items: flex-end; }
  .param-group { display: flex; flex-direction: column; }
  .param-group label { font-size: .72rem; color: #999; margin-bottom: .2rem; text-transform: uppercase; letter-spacing: .04em; }
  .param-group input, .param-group select {
    background: #0f1117; border: 1px solid #2a2d37; border-radius: 4px;
    padding: .4rem .6rem; color: #e0e0e0; font-size: .85rem; font-family: monospace; min-width: 100px;
  }
  .param-group input:focus, .param-group select:focus { outline: none; border-color: #6366f1; }
  .param-group textarea {
    background: #0f1117; border: 1px solid #2a2d37; border-radius: 4px;
    padding: .5rem .6rem; color: #e0e0e0; font-size: .82rem; font-family: monospace;
    width: 100%; min-height: 120px; resize: vertical;
  }
  .param-group textarea:focus { outline: none; border-color: #6366f1; }
  .param-group.full-width { width: 100%; }

  .btn-send {
    background: #6366f1; color: #fff; border: none; border-radius: 6px;
    padding: .45rem 1.2rem; cursor: pointer; font-size: .85rem; font-weight: 500;
  }
  .btn-send:hover { background: #4f46e5; }
  .btn-send:disabled { opacity: .5; cursor: not-allowed; }

  .response-area {
    margin-top: .75rem; background: #0d0f15; border: 1px solid #22253a;
    border-radius: 6px; overflow: hidden; display: none;
  }
  .response-meta {
    display: flex; gap: 1rem; padding: .5rem .75rem;
    font-size: .8rem; border-bottom: 1px solid #22253a; align-items: center;
  }
  .status-badge {
    padding: .15rem .5rem; border-radius: 4px; font-weight: 600; font-size: .8rem;
  }
  .status-2xx { background: #064e3b; color: #34d399; }
  .status-4xx { background: #4c1d1d; color: #f87171; }
  .status-5xx { background: #4c1d1d; color: #f87171; }
  .status-err { background: #4c1d1d; color: #f87171; }
  .response-time { color: #888; }
  .response-body {
    padding: .75rem; font-family: monospace; font-size: .82rem;
    white-space: pre-wrap; word-break: break-word; max-height: 400px;
    overflow-y: auto; color: #c8d6e5; line-height: 1.45;
  }

  .toast {
    position: fixed; bottom: 1.5rem; right: 1.5rem; padding: .75rem 1.25rem;
    border-radius: 8px; font-size: .85rem; color: #fff; opacity: 0;
    transition: opacity .3s; pointer-events: none; z-index: 999;
  }
  .toast.show { opacity: 1; }
  .toast-ok  { background: #065f46; }
  .toast-err { background: #7f1d1d; }
</style>
</head>
<body>

<h1>API Test Console</h1>
<nav>
  <a href="/admin/scrapers">Scrapers</a>
  <a href="/admin/credentials">Credentials</a>
  <a href="/admin/api-test" class="active">API Test</a>
  <a href="/admin/dashboard">Dashboard</a>
  <a href="/admin/scoring">Scoring</a>
  <a href="/docs">API Docs</a>
</nav>

<!-- ===== HEALTH ===== -->
<div class="section">
  <div class="section-title">Health</div>

  <div class="endpoint" id="ep-health">
    <div class="ep-header">
      <span class="method-badge method-get">GET</span>
      <span class="ep-path">/health</span>
    </div>
    <div class="ep-desc-block">
      <strong>Basic health check.</strong> No authentication required. Returns API status, version, and uptime. Use to verify the server is running.
      <br>Returns: <strong>status</strong> (ok/error), <strong>version</strong>, <strong>environment</strong>
    </div>
    <button class="btn-send" onclick="send('ep-health','GET','/health',{},false)">Send</button>
    <div class="response-area" id="ep-health-resp">
      <div class="response-meta"><span class="status-badge" id="ep-health-status"></span><span class="response-time" id="ep-health-time"></span></div>
      <pre class="response-body" id="ep-health-body"></pre>
    </div>
  </div>

  <div class="endpoint" id="ep-root">
    <div class="ep-header">
      <span class="method-badge method-get">GET</span>
      <span class="ep-path">/</span>
    </div>
    <div class="ep-desc-block">
      <strong>API root.</strong> No auth required. Returns welcome message and API version info.
    </div>
    <button class="btn-send" onclick="send('ep-root','GET','/',{},false)">Send</button>
    <div class="response-area" id="ep-root-resp">
      <div class="response-meta"><span class="status-badge" id="ep-root-status"></span><span class="response-time" id="ep-root-time"></span></div>
      <pre class="response-body" id="ep-root-body"></pre>
    </div>
  </div>

  <div class="endpoint" id="ep-admin-health">
    <div class="ep-header">
      <span class="method-badge method-get">GET</span>
      <span class="ep-path">/api/v1/admin/health</span>
    </div>
    <div class="ep-desc-block">
      <strong>Scraper health status.</strong> Admin auth required. Returns health of all scrapers — checks data freshness, stuck/error/stale states.
      <br>Returns: <strong>overall</strong> (healthy/degraded/unhealthy), <strong>scrapers</strong> (per-scraper status with last_run, freshness)
    </div>
    <button class="btn-send" onclick="send('ep-admin-health','GET','/api/v1/admin/health',{},true)">Send</button>
    <div class="response-area" id="ep-admin-health-resp">
      <div class="response-meta"><span class="status-badge" id="ep-admin-health-status"></span><span class="response-time" id="ep-admin-health-time"></span></div>
      <pre class="response-body" id="ep-admin-health-body"></pre>
    </div>
  </div>
</div>

<!-- ===== GENRES ===== -->
<div class="section">
  <div class="section-title">Genres</div>

  <div class="endpoint" id="ep-genres">
    <div class="ep-header">
      <span class="method-badge method-get">GET</span>
      <span class="ep-path">/api/v1/genres</span>
    </div>
    <div class="ep-desc-block">
      <strong>Browse genre taxonomy.</strong> Returns the full genre tree (850+ genres) or a filtered subset.
      <br><strong>root</strong>: filter to a root category (e.g. "electronic", "hip-hop"). <strong>depth</strong>: max tree depth (0=roots only). <strong>flat</strong>: return flat list instead of tree.
      <br>Returns: <strong>data[]</strong> — genre objects with id, name, parent_id, depth, children[], audio_profile, adjacent_genres
    </div>
    <div class="params">
      <div class="param-group"><label>root</label><input id="ep-genres-root" value="" placeholder="e.g. electronic" /></div>
      <div class="param-group"><label>depth</label><input id="ep-genres-depth" value="" placeholder="e.g. 2" /></div>
      <div class="param-group"><label>status</label><input id="ep-genres-status" value="active" /></div>
      <div class="param-group"><label>flat</label><select id="ep-genres-flat"><option value="false">false</option><option value="true">true</option></select></div>
    </div>
    <button class="btn-send" onclick="sendGenres()">Send</button>
    <div class="response-area" id="ep-genres-resp">
      <div class="response-meta"><span class="status-badge" id="ep-genres-status-badge"></span><span class="response-time" id="ep-genres-time"></span></div>
      <pre class="response-body" id="ep-genres-body"></pre>
    </div>
  </div>

  <div class="endpoint" id="ep-genre-detail">
    <div class="ep-header">
      <span class="method-badge method-get">GET</span>
      <span class="ep-path">/api/v1/genres/{genre_id}</span>
    </div>
    <div class="ep-desc-block">
      <strong>Get single genre details.</strong> Returns full info for one genre including audio_profile (tempo/energy/valence ranges), platform mappings (Spotify, Apple Music, MusicBrainz), and adjacent genres.
      <br><strong>genre_id</strong>: dot-notation ID (e.g. "electronic.house.tech-house")
    </div>
    <div class="params">
      <div class="param-group"><label>genre_id</label><input id="ep-genre-detail-id" value="electronic" /></div>
    </div>
    <button class="btn-send" onclick="sendGenreDetail()">Send</button>
    <div class="response-area" id="ep-genre-detail-resp">
      <div class="response-meta"><span class="status-badge" id="ep-genre-detail-status"></span><span class="response-time" id="ep-genre-detail-time"></span></div>
      <pre class="response-body" id="ep-genre-detail-body"></pre>
    </div>
  </div>
</div>

<!-- ===== TRENDING ===== -->
<div class="section">
  <div class="section-title">Trending</div>

  <div class="endpoint" id="ep-trending-get">
    <div class="ep-header">
      <span class="method-badge method-get">GET</span>
      <span class="ep-path">/api/v1/trending</span>
    </div>
    <div class="ep-desc-block">
      <strong>Get trending entities.</strong> Returns ranked list of currently trending tracks or artists with composite scores, velocity, and 7-day sparkline data.
      <br><strong>entity_type</strong>*: "track" or "artist". <strong>time_range</strong>: snapshot window. <strong>genre</strong>: filter by genre ID. <strong>platform</strong>: filter by source platform. <strong>sort</strong>: ranking method. <strong>min_platforms</strong>: minimum cross-platform appearances.
      <br>Returns: <strong>data[]</strong> — entity info + <strong>scores</strong> (composite_score, velocity, platform_count) + <strong>sparkline_7d</strong> (daily scores)
    </div>
    <div class="params">
      <div class="param-group"><label>entity_type *</label><select id="ep-trending-get-entity_type"><option value="track">track</option><option value="artist">artist</option></select></div>
      <div class="param-group"><label>genre</label><input id="ep-trending-get-genre" value="" placeholder="e.g. pop" /></div>
      <div class="param-group"><label>platform</label><input id="ep-trending-get-platform" value="" placeholder="e.g. spotify" /></div>
      <div class="param-group"><label>time_range</label><select id="ep-trending-get-time_range"><option value="today">today</option><option value="7d">7d</option><option value="30d">30d</option></select></div>
      <div class="param-group"><label>limit</label><input id="ep-trending-get-limit" value="50" type="number" /></div>
      <div class="param-group"><label>offset</label><input id="ep-trending-get-offset" value="0" type="number" /></div>
      <div class="param-group"><label>sort</label><select id="ep-trending-get-sort"><option value="composite_score">composite_score</option><option value="velocity">velocity</option><option value="platform_rank">platform_rank</option></select></div>
      <div class="param-group"><label>min_platforms</label><input id="ep-trending-get-min_platforms" value="1" type="number" /></div>
    </div>
    <button class="btn-send" onclick="sendTrendingGet()">Send</button>
    <div class="response-area" id="ep-trending-get-resp">
      <div class="response-meta"><span class="status-badge" id="ep-trending-get-status"></span><span class="response-time" id="ep-trending-get-time"></span></div>
      <pre class="response-body" id="ep-trending-get-body"></pre>
    </div>
  </div>

  <div class="endpoint" id="ep-trending-post">
    <div class="ep-header">
      <span class="method-badge method-post">POST</span>
      <span class="ep-path">/api/v1/trending</span>
    </div>
    <div class="ep-desc-block">
      <strong>Ingest trending data.</strong> Admin auth required. Submit a single data point from a scraper/platform. Creates or updates the entity and records a trending snapshot.
      <br><strong>platform</strong>*: source (spotify, shazam, etc). <strong>entity_type</strong>*: track/artist. <strong>entity_identifier</strong>*: platform-specific IDs + name. <strong>rank</strong>: chart position. <strong>raw_score</strong>: platform-specific score. <strong>signals</strong>: additional metadata (genres, audio features).
      <br>Returns: <strong>entity_id</strong>, <strong>snapshot_id</strong>, <strong>status</strong> (created/updated)
    </div>
    <div class="params">
      <div class="param-group full-width">
        <label>Request Body (JSON)</label>
        <textarea id="ep-trending-post-body-input">{
  "platform": "spotify",
  "entity_type": "track",
  "entity_identifier": {
    "spotify_id": "4cOdK2wGLETKBW3PvgPWqT",
    "title": "Never Gonna Give You Up",
    "artist_name": "Rick Astley"
  },
  "snapshot_date": "2026-03-22",
  "raw_score": 85.5,
  "rank": 12,
  "signals": {}
}</textarea>
      </div>
    </div>
    <button class="btn-send" onclick="sendTrendingPost()">Send</button>
    <div class="response-area" id="ep-trending-post-resp">
      <div class="response-meta"><span class="status-badge" id="ep-trending-post-status"></span><span class="response-time" id="ep-trending-post-time"></span></div>
      <pre class="response-body" id="ep-trending-post-body"></pre>
    </div>
  </div>
</div>

<!-- ===== SEARCH ===== -->
<div class="section">
  <div class="section-title">Search</div>

  <div class="endpoint" id="ep-search">
    <div class="ep-header">
      <span class="method-badge method-get">GET</span>
      <span class="ep-path">/api/v1/search</span>
    </div>
    <div class="ep-desc-block">
      <strong>Search artists and tracks.</strong> Full-text search across entity names. Returns matching entities with their latest scores and relevance ranking.
      <br><strong>q</strong>*: search query (min 2 chars). <strong>type</strong>: filter by "artist", "track", or "all". <strong>limit</strong>: max results.
      <br>Returns: <strong>data[]</strong> — entity + <strong>latest_scores</strong> (composite, velocity, platform_count) + <strong>relevance_score</strong> (0-1)
    </div>
    <div class="params">
      <div class="param-group"><label>q *</label><input id="ep-search-q" value="Drake" /></div>
      <div class="param-group"><label>type</label><select id="ep-search-type"><option value="all">all</option><option value="artist">artist</option><option value="track">track</option></select></div>
      <div class="param-group"><label>limit</label><input id="ep-search-limit" value="20" type="number" /></div>
    </div>
    <button class="btn-send" onclick="sendSearch()">Send</button>
    <div class="response-area" id="ep-search-resp">
      <div class="response-meta"><span class="status-badge" id="ep-search-status"></span><span class="response-time" id="ep-search-time"></span></div>
      <pre class="response-body" id="ep-search-body"></pre>
    </div>
  </div>
</div>

<!-- ===== PREDICTIONS ===== -->
<div class="section">
  <div class="section-title">Predictions</div>

  <div class="endpoint" id="ep-predictions-get">
    <div class="ep-header">
      <span class="method-badge method-get">GET</span>
      <span class="ep-path">/api/v1/predictions</span>
    </div>
    <div class="ep-desc-block">
      <strong>Get US-market breakout predictions.</strong> Returns ML-predicted entities likely to trend in the US market, ranked by predicted score change. Uses ensemble model (LightGBM + LSTM + XGBoost) with rule-based fallback when model isn't trained yet. All predictions are US-market specific.
      <br><strong>entity_type</strong>: filter predictions. <strong>horizon</strong>: prediction window (7d/30d/90d). <strong>min_confidence</strong>: filter low-confidence predictions (0-1). <strong>prediction_target</strong>: filter by US target (billboard_hot_100, spotify_top_50_us, shazam_top_200_us, cross_platform_breakout). <strong>sort</strong>: ranking method.
      <br>Returns: <strong>data[]</strong> — entity + <strong>predictions</strong> (4 US-market targets with probabilities) + <strong>top_signals</strong> (features driving the prediction)
    </div>
    <div class="params">
      <div class="param-group"><label>entity_type</label><select id="ep-predictions-get-entity_type"><option value="all">all</option><option value="artist">artist</option><option value="track">track</option><option value="genre">genre</option></select></div>
      <div class="param-group"><label>horizon</label><select id="ep-predictions-get-horizon"><option value="7d">7d</option><option value="30d">30d</option><option value="90d">90d</option></select></div>
      <div class="param-group"><label>genre</label><input id="ep-predictions-get-genre" value="" placeholder="e.g. hip-hop" /></div>
      <div class="param-group"><label>prediction_target</label><select id="ep-predictions-get-prediction_target"><option value="">all targets</option><option value="billboard_hot_100">billboard_hot_100</option><option value="spotify_top_50_us">spotify_top_50_us</option><option value="shazam_top_200_us">shazam_top_200_us</option><option value="cross_platform_breakout">cross_platform_breakout</option></select></div>
      <div class="param-group"><label>min_confidence</label><input id="ep-predictions-get-min_confidence" value="0.0" /></div>
      <div class="param-group"><label>limit</label><input id="ep-predictions-get-limit" value="50" type="number" /></div>
      <div class="param-group"><label>offset</label><input id="ep-predictions-get-offset" value="0" type="number" /></div>
      <div class="param-group"><label>sort</label><select id="ep-predictions-get-sort"><option value="predicted_change">predicted_change</option><option value="confidence">confidence</option><option value="predicted_score">predicted_score</option></select></div>
    </div>
    <button class="btn-send" onclick="sendPredictionsGet()">Send</button>
    <div class="response-area" id="ep-predictions-get-resp">
      <div class="response-meta"><span class="status-badge" id="ep-predictions-get-status"></span><span class="response-time" id="ep-predictions-get-time"></span></div>
      <pre class="response-body" id="ep-predictions-get-body"></pre>
    </div>
  </div>

  <div class="endpoint" id="ep-predictions-entity">
    <div class="ep-header">
      <span class="method-badge method-get">GET</span>
      <span class="ep-path">/api/v1/predictions/{entity_id}</span>
    </div>
    <div class="ep-desc-block">
      <strong>Get US-market predictions for a single entity.</strong> Generates live predictions for 4 US-market targets using the ML ensemble or rule-based fallback. Pass an entity UUID from a search or trending result.
      <br><strong>entity_id</strong>*: UUID of the track or artist. <strong>entity_type</strong>: "track" or "artist". <strong>horizon</strong>: prediction window.
      <br>Returns: <strong>entity</strong> info + <strong>predictions</strong> (billboard_hot_100, spotify_top_50_us, shazam_top_200_us, cross_platform_breakout — each with probability, horizon, label) + <strong>prediction_summary</strong> + <strong>features</strong> (raw feature vector used)
    </div>
    <div class="params">
      <div class="param-group"><label>entity_id *</label><input id="ep-predictions-entity-id" value="" placeholder="UUID from search/trending" style="min-width:280px;" /></div>
      <div class="param-group"><label>entity_type</label><select id="ep-predictions-entity-type"><option value="track">track</option><option value="artist">artist</option></select></div>
      <div class="param-group"><label>horizon</label><select id="ep-predictions-entity-horizon"><option value="7d">7d</option><option value="30d">30d</option><option value="90d">90d</option></select></div>
    </div>
    <button class="btn-send" onclick="sendPredictionEntity()">Send</button>
    <div class="response-area" id="ep-predictions-entity-resp">
      <div class="response-meta"><span class="status-badge" id="ep-predictions-entity-status"></span><span class="response-time" id="ep-predictions-entity-time"></span></div>
      <pre class="response-body" id="ep-predictions-entity-body"></pre>
    </div>
  </div>

  <div class="endpoint" id="ep-predictions-feedback">
    <div class="ep-header">
      <span class="method-badge method-post">POST</span>
      <span class="ep-path">/api/v1/predictions/feedback</span>
    </div>
    <div class="ep-desc-block">
      <strong>Submit prediction feedback.</strong> Admin auth required. Report the actual outcome so the model can learn from its predictions. Used for model evaluation and retraining.
      <br><strong>prediction_id</strong>*: UUID of the prediction. <strong>actual_score</strong>*: the real score the entity achieved.
      <br>Returns: <strong>status</strong> (recorded), <strong>accuracy_delta</strong> (how far off the prediction was)
    </div>
    <div class="params">
      <div class="param-group full-width">
        <label>Request Body (JSON)</label>
        <textarea id="ep-predictions-feedback-body-input">{
  "prediction_id": "00000000-0000-0000-0000-000000000000",
  "actual_score": 72.5
}</textarea>
      </div>
    </div>
    <button class="btn-send" onclick="sendPredictionsFeedback()">Send</button>
    <div class="response-area" id="ep-predictions-feedback-resp">
      <div class="response-meta"><span class="status-badge" id="ep-predictions-feedback-status"></span><span class="response-time" id="ep-predictions-feedback-time"></span></div>
      <pre class="response-body" id="ep-predictions-feedback-body"></pre>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const toastEl = document.getElementById('toast');

function getKey() { return localStorage.getItem('sp_admin_key') || ''; }
if (!getKey()) {
  const notice = document.createElement('div');
  notice.style.cssText = 'background:#4c1d1d;color:#f87171;padding:.75rem 1rem;border-radius:6px;margin-bottom:1.5rem;font-size:.85rem;';
  notice.innerHTML = 'No admin key set. <a href="/admin/credentials" style="color:#60a5fa;text-decoration:underline;">Set it in Credentials</a> first.';
  document.querySelector('nav').after(notice);
}

function toast(msg, type) {
  toastEl.textContent = msg;
  toastEl.className = 'toast show ' + (type === 'ok' ? 'toast-ok' : 'toast-err');
  setTimeout(() => { toastEl.className = 'toast'; }, 3000);
}

function statusClass(code) {
  if (code >= 200 && code < 300) return 'status-2xx';
  if (code >= 400 && code < 500) return 'status-4xx';
  return 'status-5xx';
}

async function send(epId, method, url, opts, useAuth) {
  const respArea = document.getElementById(epId + '-resp');
  const statusEl = document.getElementById(epId + '-status');
  const timeEl  = document.getElementById(epId + '-time');
  const bodyEl  = document.getElementById(epId + '-body');

  respArea.style.display = 'block';
  statusEl.textContent = '...';
  statusEl.className = 'status-badge';
  timeEl.textContent = '';
  bodyEl.textContent = 'Loading...';

  const headers = { 'Content-Type': 'application/json' };
  if (useAuth) headers['X-API-Key'] = getKey();

  const fetchOpts = { method, headers };
  if (opts.body) fetchOpts.body = opts.body;

  const t0 = performance.now();
  try {
    const res = await fetch(url, fetchOpts);
    const elapsed = Math.round(performance.now() - t0);
    const data = await res.json().catch(() => res.text());
    statusEl.textContent = res.status;
    statusEl.className = 'status-badge ' + statusClass(res.status);
    timeEl.textContent = elapsed + ' ms';
    bodyEl.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  } catch (e) {
    const elapsed = Math.round(performance.now() - t0);
    statusEl.textContent = 'ERR';
    statusEl.className = 'status-badge status-err';
    timeEl.textContent = elapsed + ' ms';
    bodyEl.textContent = e.message;
  }
}

function val(id) { return document.getElementById(id).value.trim(); }

function buildQs(params) {
  const parts = [];
  for (const [k, v] of Object.entries(params)) {
    if (v !== '' && v != null) parts.push(encodeURIComponent(k) + '=' + encodeURIComponent(v));
  }
  return parts.length ? '?' + parts.join('&') : '';
}

function sendGenres() {
  const qs = buildQs({ root: val('ep-genres-root'), depth: val('ep-genres-depth'), status: val('ep-genres-status'), flat: val('ep-genres-flat') });
  send('ep-genres', 'GET', '/api/v1/genres' + qs, {}, true);
}

function sendGenreDetail() {
  const id = val('ep-genre-detail-id') || 'electronic';
  send('ep-genre-detail', 'GET', '/api/v1/genres/' + encodeURIComponent(id), {}, true);
}

function sendTrendingGet() {
  const qs = buildQs({
    entity_type: val('ep-trending-get-entity_type'), genre: val('ep-trending-get-genre'),
    platform: val('ep-trending-get-platform'), time_range: val('ep-trending-get-time_range'),
    limit: val('ep-trending-get-limit'), offset: val('ep-trending-get-offset'),
    sort: val('ep-trending-get-sort'), min_platforms: val('ep-trending-get-min_platforms'),
  });
  send('ep-trending-get', 'GET', '/api/v1/trending' + qs, {}, true);
}

function sendTrendingPost() {
  const raw = val('ep-trending-post-body-input');
  try { JSON.parse(raw); } catch(e) { toast('Invalid JSON: ' + e.message, 'err'); return; }
  send('ep-trending-post', 'POST', '/api/v1/trending', { body: raw }, true);
}

function sendSearch() {
  const qs = buildQs({ q: val('ep-search-q'), type: val('ep-search-type'), limit: val('ep-search-limit') });
  send('ep-search', 'GET', '/api/v1/search' + qs, {}, true);
}

function sendPredictionsGet() {
  const qs = buildQs({
    entity_type: val('ep-predictions-get-entity_type'), horizon: val('ep-predictions-get-horizon'),
    genre: val('ep-predictions-get-genre'), prediction_target: val('ep-predictions-get-prediction_target'),
    min_confidence: val('ep-predictions-get-min_confidence'),
    limit: val('ep-predictions-get-limit'), offset: val('ep-predictions-get-offset'),
    sort: val('ep-predictions-get-sort'),
  });
  send('ep-predictions-get', 'GET', '/api/v1/predictions' + qs, {}, true);
}

function sendPredictionEntity() {
  const id = val('ep-predictions-entity-id');
  if (!id) { toast('Enter an entity UUID', 'err'); return; }
  const qs = buildQs({
    entity_type: val('ep-predictions-entity-type'),
    horizon: val('ep-predictions-entity-horizon'),
  });
  send('ep-predictions-entity', 'GET', '/api/v1/predictions/' + encodeURIComponent(id) + qs, {}, true);
}

function sendPredictionsFeedback() {
  const raw = val('ep-predictions-feedback-body-input');
  try { JSON.parse(raw); } catch(e) { toast('Invalid JSON: ' + e.message, 'err'); return; }
  send('ep-predictions-feedback', 'POST', '/api/v1/predictions/feedback', { body: raw }, true);
}
</script>
</body>
</html>"""


@router.get("/admin/api-test", response_class=HTMLResponse)
async def api_test_page():
    """Serve the API test console page."""
    return HTMLResponse(content=API_TEST_HTML)


# ---------------------------------------------------------------------------
# JSON API endpoints (admin auth required)
# ---------------------------------------------------------------------------

@router.get("/api/v1/admin/scraper-config", response_model=list[ScraperConfigOut])
async def list_scraper_configs(
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Return all scraper configuration rows."""
    result = await db.execute(select(ScraperConfig).order_by(ScraperConfig.id))
    configs = result.scalars().all()
    return configs


@router.put("/api/v1/admin/scraper-config/{scraper_id}", response_model=ScraperConfigOut)
async def update_scraper_config(
    scraper_id: str,
    body: ScraperConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Update enabled and/or interval_hours for a scraper."""
    result = await db.execute(select(ScraperConfig).where(ScraperConfig.id == scraper_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail=f"Scraper '{scraper_id}' not found")

    if body.enabled is not None:
        config.enabled = body.enabled
    if body.interval_hours is not None:
        if body.interval_hours < 0.5:
            raise HTTPException(status_code=422, detail="interval_hours must be >= 0.5")
        config.interval_hours = body.interval_hours

    config.updated_at = datetime.now(timezone.utc)
    await db.flush()

    # Update the APScheduler job to match
    update_job(
        scraper_id=config.id,
        interval_hours=config.interval_hours,
        enabled=config.enabled,
    )

    return config


@router.post("/api/v1/admin/scraper-config/{scraper_id}/run-now", status_code=202)
async def run_scraper_now(
    scraper_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Trigger an immediate scraper run in the background."""
    result = await db.execute(select(ScraperConfig).where(ScraperConfig.id == scraper_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail=f"Scraper '{scraper_id}' not found")

    asyncio.create_task(trigger_now(scraper_id))
    return {"detail": f"Scraper '{scraper_id}' triggered"}


# ---------------------------------------------------------------------------
# Backfill endpoint
# ---------------------------------------------------------------------------


class BackfillRequest(BaseModel):
    days: int = 730
    start_date: str | None = None
    end_date: str | None = None


@router.post("/api/v1/admin/backfill", status_code=202)
async def start_backfill(
    request: BackfillRequest,
    _admin: ApiKey = Depends(require_admin),
):
    """Start a deep historical backfill from Chartmetric in the background.

    Routes to the new `backfill_chartmetric_deep_us.py` script which pulls the
    full ENDPOINT_MATRIX (32 confirmed endpoints, ~250 expanded calls per
    snapshot date) via the bulk ingest endpoint. Defaults to --confirmed-only
    so only endpoints verified against the user's Chartmetric tier are
    pulled. Runs as a detached subprocess on the Railway API container;
    logs stream to /tmp/soundpulse_backfill.log.
    """
    import os
    import subprocess
    import sys

    # AUD-003: use absolute path so this works regardless of CWD in the Railway
    # container. Same fix pattern as the train_model task.
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script_path = os.path.join(project_root, "scripts", "backfill_chartmetric_deep_us.py")
    cmd = [sys.executable, script_path, "--confirmed-only", "--days", str(request.days)]
    if request.start_date:
        cmd.extend(["--start", request.start_date])
    if request.end_date:
        cmd.extend(["--end", request.end_date])

    # AUD-003: previously this leaked the log file handle on every call
    # (`open("/tmp/backfill.log", "w")` inline → never closed → after ~1024
    # backfill calls the OS file descriptor table exhausts). Use a context
    # manager and dup the FD into the child so we can close ours immediately.
    #
    # Generality principle: use tempfile.gettempdir() instead of hardcoded
    # "/tmp" so this works on Windows, macOS, and Linux containers. On
    # Railway's Linux container it resolves to /tmp; on a Windows dev
    # machine it resolves to %LOCALAPPDATA%\Temp or similar.
    import tempfile
    log_path = os.path.join(tempfile.gettempdir(), "soundpulse_backfill.log")
    log_file = open(log_path, "w")
    try:
        subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=project_root,
            close_fds=True,
        )
    finally:
        # The child has dup'd the FD; we close our copy so we don't leak.
        log_file.close()

    return {
        "detail": f"Backfill started: {request.days} days",
        "log_file": log_path,
        "command": " ".join(cmd),
    }


# ---------------------------------------------------------------------------
# Model config endpoint
# ---------------------------------------------------------------------------

_MODEL_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "model.json"


@router.get("/api/v1/admin/model-config")
async def get_model_config(_admin: ApiKey = Depends(require_admin)):
    """Return the current model configuration."""
    try:
        with open(_MODEL_CONFIG_PATH) as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}


@router.put("/api/v1/admin/model-config")
async def put_model_config(
    body: dict,
    _admin: ApiKey = Depends(require_admin),
):
    """Update model configuration (partial update — merges with existing)."""
    try:
        with open(_MODEL_CONFIG_PATH) as f:
            config = json.load(f)
    except Exception:
        config = {}

    # Deep merge
    for key, value in body.items():
        if isinstance(value, dict) and isinstance(config.get(key), dict):
            config[key].update(value)
        else:
            config[key] = value

    with open(_MODEL_CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

    return {"detail": "Model config updated", "config": config}


# ---------------------------------------------------------------------------
# LLM usage aggregates (Batch B — CLAUDE.md "every LLM call must be logged")
# ---------------------------------------------------------------------------

@router.get("/api/v1/admin/llm-usage")
async def get_llm_usage(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Aggregated LLM usage stats for the last N days.

    Returns totals by action_type (e.g. "assistant_chat") and by model,
    with call counts, total tokens, total cost in cents, and median
    latency. Powers a cost/usage dashboard section the frontend can
    surface later.
    """
    from sqlalchemy import text as sa_text
    days = max(1, min(days, 365))

    by_action = (await db.execute(sa_text("""
        SELECT
            action_type,
            COUNT(*) AS call_count,
            SUM(input_tokens)  AS total_input_tokens,
            SUM(output_tokens) AS total_output_tokens,
            SUM(cost_cents)    AS total_cost_cents,
            SUM(CASE WHEN success THEN 0 ELSE 1 END) AS error_count,
            ROUND(AVG(latency_ms)) AS avg_latency_ms
        FROM llm_calls
        WHERE created_at >= NOW() - make_interval(days => :days)
        GROUP BY action_type
        ORDER BY total_cost_cents DESC NULLS LAST
    """), {"days": days})).mappings().all()

    by_model = (await db.execute(sa_text("""
        SELECT
            model,
            provider,
            COUNT(*) AS call_count,
            SUM(input_tokens)  AS total_input_tokens,
            SUM(output_tokens) AS total_output_tokens,
            SUM(cost_cents)    AS total_cost_cents
        FROM llm_calls
        WHERE created_at >= NOW() - make_interval(days => :days)
        GROUP BY model, provider
        ORDER BY total_cost_cents DESC NULLS LAST
    """), {"days": days})).mappings().all()

    totals = (await db.execute(sa_text("""
        SELECT
            COUNT(*) AS total_calls,
            SUM(cost_cents) AS total_cost_cents,
            SUM(CASE WHEN success THEN 0 ELSE 1 END) AS error_count
        FROM llm_calls
        WHERE created_at >= NOW() - make_interval(days => :days)
    """), {"days": days})).mappings().one()

    return {
        "days": days,
        "totals": {
            "total_calls": int(totals["total_calls"] or 0),
            "total_cost_cents": int(totals["total_cost_cents"] or 0),
            "total_cost_usd": round((int(totals["total_cost_cents"] or 0)) / 100, 2),
            "error_count": int(totals["error_count"] or 0),
        },
        "by_action": [dict(r) for r in by_action],
        "by_model": [dict(r) for r in by_model],
    }


# ---------------------------------------------------------------------------
# Artists with chartmetric_id (feed for Phase 2b artist-tracks crawler)
# ---------------------------------------------------------------------------
#
# Returns artists that have a chartmetric_id set — these are the ones the
# playlist + chart backfill identified and for which we can call
# /api/artist/{id}/tracks to harvest their full catalog from Chartmetric.

@router.post("/api/v1/admin/artists/{artist_id}/merge-metadata")
async def merge_artist_metadata(
    artist_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Merge a patch into an artist's metadata_json. Used by the Phase 4
    artist-enrichment scraper to upsert per-platform stats without needing
    a dedicated time-series table. Shallow merge at the top level.
    """
    from api.models.artist import Artist
    import uuid as uuid_mod
    try:
        aid = uuid_mod.UUID(artist_id)
    except ValueError:
        raise HTTPException(400, detail={"error": {"code": "BAD_UUID", "message": "invalid UUID"}})

    result = await db.execute(select(Artist).where(Artist.id == aid))
    artist = result.scalar_one_or_none()
    if artist is None:
        raise HTTPException(404, detail={"error": {"code": "NOT_FOUND", "message": "artist not found"}})

    existing = artist.metadata_json or {}
    artist.metadata_json = {**existing, **body}
    await db.commit()
    return {"artist_id": artist_id, "merged_keys": list(body.keys())}


@router.post("/api/v1/admin/artists/backfill-chartmetric-id")
async def backfill_artists_chartmetric_id(
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    One-shot: backfill artists.chartmetric_id from signals_json.cm_artist_id
    in existing trending_snapshots rows.

    Joins snapshots to tracks to artists and patches the first non-null
    cm_artist_id found per artist. Idempotent — only updates artists
    whose chartmetric_id is still NULL.

    Needed because before the forward-fix, the bulk endpoint never
    propagated cm_artist_id from track-level signals onto the artist row,
    leaving Phase 2b/4 scrapers with zero input.
    """
    from sqlalchemy import text as sa_text
    result = await db.execute(sa_text("""
        WITH artist_cm_ids AS (
            SELECT DISTINCT ON (t.artist_id)
                t.artist_id,
                (ts.signals_json->>'cm_artist_id')::bigint AS cm_artist_id
            FROM trending_snapshots ts
            JOIN tracks t ON t.id = ts.entity_id
            WHERE ts.entity_type = 'track'
              AND ts.signals_json->>'cm_artist_id' IS NOT NULL
              AND ts.signals_json->>'cm_artist_id' ~ '^[0-9]+$'
            ORDER BY t.artist_id, ts.created_at DESC
        )
        UPDATE artists a
        SET chartmetric_id = aci.cm_artist_id
        FROM artist_cm_ids aci
        WHERE a.id = aci.artist_id
          AND a.chartmetric_id IS NULL
        RETURNING a.id
    """))
    updated_ids = result.fetchall()
    await db.commit()
    return {
        "artists_updated": len(updated_ids),
        "detail": "Backfilled chartmetric_id on artists from signals_json.cm_artist_id",
    }


@router.get("/api/v1/admin/artists/with-chartmetric-id")
async def get_artists_with_chartmetric_id(
    limit: int = 500,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Artists with a known chartmetric_id, for per-artist /tracks crawls."""
    from api.models.artist import Artist

    limit = max(1, min(limit, 1000))
    offset = max(0, offset)

    result = await db.execute(
        select(Artist.id, Artist.name, Artist.chartmetric_id, Artist.spotify_id)
        .where(Artist.chartmetric_id.isnot(None))
        .order_by(Artist.chartmetric_id)
        .limit(limit)
        .offset(offset)
    )
    rows = result.all()

    return {
        "data": [
            {
                "artist_id": str(r.id),
                "name": r.name,
                "chartmetric_id": r.chartmetric_id,
                "spotify_id": r.spotify_id,
            }
            for r in rows
        ],
        "limit": limit,
        "offset": offset,
        "returned": len(rows),
    }


# ---------------------------------------------------------------------------
# Tracks needing audio feature enrichment (AUD-011 fix)
# ---------------------------------------------------------------------------
#
# Returns tracks that have a spotify_id but no audio_features yet. Consumed
# by `scrapers/spotify_audio.py` to find work to do. Previously the scraper
# tried to parse the /trending response for this — that endpoint has a
# different shape and doesn't include audio_features, so the scraper always
# got 0 results and silently exited. See L001 / AUD-011 / P1-004.

@router.get("/api/v1/admin/tracks/needing-audio-features")
async def get_tracks_needing_audio_features(
    limit: int = 500,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Return tracks with a spotify_id but no audio_features.

    Cap limit at 1000 to prevent runaway queries.
    """
    from sqlalchemy import or_, text as sa_text

    from api.models.track import Track

    limit = max(1, min(limit, 1000))
    offset = max(0, offset)

    result = await db.execute(
        select(Track.id, Track.spotify_id, Track.title, Track.artist_id, Track.isrc)
        .where(
            Track.spotify_id.isnot(None),
            or_(
                Track.audio_features.is_(None),
                sa_text("tracks.audio_features::text = '{}'::text"),
            ),
        )
        .order_by(Track.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = result.all()

    return {
        "data": [
            {
                "track_id": str(r.id),
                "spotify_id": r.spotify_id,
                "title": r.title,
                "isrc": r.isrc,
                "artist_id": str(r.artist_id) if r.artist_id else None,
            }
            for r in rows
        ],
        "limit": limit,
        "offset": offset,
        "returned": len(rows),
    }


# ---------------------------------------------------------------------------
# DB Stats — diagnostic view (P2.I, PRD §22.2)
# ---------------------------------------------------------------------------
#
# Two endpoints answer "what's in the database, and how is it growing?":
#   - GET /api/v1/admin/db-stats             — current totals + sub-counts
#   - GET /api/v1/admin/db-stats/history     — daily new-row counts (last N days)
#
# Powers the new DbStats frontend page. Without this view the only way to
# answer "did the deep US backfill land?" is to shell into Neon.

@router.get("/api/v1/admin/db-stats")
async def get_db_stats(
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Current totals + sub-counts across every operational table."""
    from api.services.db_stats import get_current_stats
    return await get_current_stats(db)


@router.get("/api/v1/admin/db-stats/history")
async def get_db_stats_history(
    days: int = 90,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Daily new-row counts per table for the last N days (cap 365)."""
    from api.services.db_stats import get_history
    return await get_history(db, days=days)


@router.get("/api/v1/admin/db-stats/hydration")
async def get_db_stats_hydration(
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Hydration dashboard — current snapshot of cross-source coverage.

    Returns per-source track counts (distinct tracks that have ≥1 snapshot
    from that source_platform), totals, and derived KPIs (orphan count,
    multi-source count, deep-source count). Powers the top bar chart in
    the hydration dashboard page.
    """
    from api.services.db_stats import get_hydration_snapshot
    return await get_hydration_snapshot(db)


@router.get("/api/v1/admin/db-stats/hydration/history")
async def get_db_stats_hydration_history(
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Hydration dashboard — live time series of total tracks + per-source %.

    Bucketed by hour (or 6h / 1d for longer ranges). Each bucket is a
    point-in-time cumulative snapshot of the corpus. Powers the dual-axis
    live chart at the top of the hydration dashboard.
    """
    from api.services.db_stats import get_hydration_history
    return await get_hydration_history(db, hours=hours)


# ---------------------------------------------------------------------------
# Deferred sweep endpoints (classification + composite recalc)
# ---------------------------------------------------------------------------
#
# The bulk ingest endpoint defers genre classification and composite scoring
# to keep ingest fast. These endpoints let you (a) check the queue depth and
# (b) trigger a sweep manually. The same functions are also wired into the
# Celery beat schedule (see scrapers/tasks.py) and APScheduler (see
# scrapers/scheduler.py).

@router.get("/api/v1/admin/sweeps/status")
async def sweep_status(
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Queue depth for the deferred sweeps."""
    from api.services.classification_sweep import count_pending_classification
    from api.services.composite_sweep import count_pending_normalization

    classification = await count_pending_classification(db)
    normalization = await count_pending_normalization(db)
    return {
        "classification": classification,
        "normalization": normalization,
    }


@router.post("/api/v1/admin/sweeps/classification", status_code=202)
async def trigger_classification_sweep(
    batch_size: int = 500,
    force_reclassify: bool = False,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Run one classification sweep batch synchronously and return stats."""
    from api.services.classification_sweep import sweep_unclassified_entities

    stats = await sweep_unclassified_entities(
        db, batch_size=batch_size, force_reclassify=force_reclassify
    )
    return {"detail": "classification sweep complete", "stats": stats}


@router.post("/api/v1/admin/sweeps/composite", status_code=202)
async def trigger_composite_sweep(
    batch_size: int = 1000,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Run one composite-recalc sweep batch synchronously and return stats."""
    from api.services.composite_sweep import sweep_zero_normalized_snapshots

    stats = await sweep_zero_normalized_snapshots(db, batch_size=batch_size)
    return {"detail": "composite sweep complete", "stats": stats}


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

@router.get("/api/v1/admin/health")
async def get_health(_admin: ApiKey = Depends(require_admin)):
    """Return health status of all scrapers."""
    try:
        from scrapers.health import check_all_scrapers
        return await check_all_scrapers()
    except ImportError:
        return {"overall": "unknown", "scrapers": {}, "error": "Health module not available"}


# ---------------------------------------------------------------------------
# Credentials management
# ---------------------------------------------------------------------------

def _read_env_file() -> dict[str, str]:
    """Read the .env file and return key-value pairs."""
    import os
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
    values = {}
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    values[key.strip()] = value.strip()
    return values


def _write_env_file(updates: dict[str, str]):
    """Update specific keys in the .env file, preserving other values."""
    import os
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")

    # Read existing
    lines = []
    existing_keys = set()
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.readlines()

    # Update existing lines
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                existing_keys.add(key)
                continue
        new_lines.append(line)

    # Append new keys
    for key, value in updates.items():
        if key not in existing_keys:
            new_lines.append(f"{key}={value}\n")

    with open(env_path, "w") as f:
        f.writelines(new_lines)


def _mask_value(value: str) -> str:
    """Mask a credential value for display."""
    if not value or len(value) < 8:
        return value
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


@router.get("/admin/credentials", response_class=HTMLResponse)
async def credentials_page():
    """Serve the credentials management page."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SoundPulse - Credentials</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f1117; color: #e0e0e0; padding: 20px; }
h1 { color: #fff; margin-bottom: 8px; font-size: 1.5rem; }
.subtitle { color: #888; margin-bottom: 24px; font-size: 0.9rem; }
.nav { margin-bottom: 24px; }
.nav a { color: #7c5cff; text-decoration: none; margin-right: 16px; }
.nav a:hover { text-decoration: underline; }
.api-key-bar { background: #1a1d27; border: 1px solid #2a2d3a; border-radius: 8px; padding: 12px 16px; margin-bottom: 24px; display: flex; align-items: center; gap: 12px; }
.api-key-bar label { color: #aaa; font-size: 0.85rem; white-space: nowrap; }
.api-key-bar input { flex: 1; background: #0f1117; border: 1px solid #3a3d4a; border-radius: 4px; padding: 8px; color: #fff; font-family: monospace; }
.card { background: #1a1d27; border: 1px solid #2a2d3a; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
.field { margin-bottom: 16px; }
.field label { display: block; color: #aaa; font-size: 0.85rem; margin-bottom: 4px; }
.field input { width: 100%; background: #0f1117; border: 1px solid #3a3d4a; border-radius: 4px; padding: 8px 12px; color: #fff; font-family: monospace; font-size: 0.9rem; }
.field input:focus { outline: none; border-color: #7c5cff; }
.field .hint { color: #666; font-size: 0.75rem; margin-top: 2px; }
.section-title { color: #7c5cff; font-size: 1rem; font-weight: 600; margin-bottom: 16px; border-bottom: 1px solid #2a2d3a; padding-bottom: 8px; }
.btn { background: #7c5cff; color: #fff; border: none; padding: 10px 24px; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
.btn:hover { background: #6a4de0; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.status { margin-top: 12px; padding: 8px 12px; border-radius: 4px; font-size: 0.85rem; display: none; }
.status.success { display: block; background: #1a3a2a; color: #4ade80; border: 1px solid #2a5a3a; }
.status.error { display: block; background: #3a1a1a; color: #f87171; border: 1px solid #5a2a2a; }
.actions { display: flex; gap: 12px; align-items: center; }
</style>
</head>
<body>
<h1>Credential Management</h1>
<p class="subtitle">API keys and secrets for platform scrapers. Saved to .env file.</p>
<div class="nav"><a href="/admin/scrapers">Scrapers</a><a href="/admin/credentials">Credentials</a><a href="/admin/api-test">API Test</a><a href="/admin/dashboard">Dashboard</a><a href="/admin/scoring">Scoring</a><a href="/docs">API Docs</a></div>

<div class="api-key-bar">
    <label>Admin API Key:</label>
    <input type="password" id="adminKey" placeholder="Enter admin key to save changes" />
</div>

<div id="credentials-form">
    <div class="card">
        <div class="section-title">Spotify</div>
        <div class="field"><label>SPOTIFY_CLIENT_ID</label><input type="text" data-key="SPOTIFY_CLIENT_ID" /><div class="hint">From developer.spotify.com</div></div>
        <div class="field"><label>SPOTIFY_CLIENT_SECRET</label><input type="password" data-key="SPOTIFY_CLIENT_SECRET" /><div class="hint">Keep secret</div></div>
    </div>
    <div class="card">
        <div class="section-title">Chartmetric</div>
        <div class="field"><label>CHARTMETRIC_API_KEY</label><input type="password" data-key="CHARTMETRIC_API_KEY" /><div class="hint">Refresh token from api.chartmetric.com</div></div>
    </div>
    <div class="card">
        <div class="section-title">Shazam (RapidAPI)</div>
        <div class="field"><label>SHAZAM_RAPIDAPI_KEY</label><input type="password" data-key="SHAZAM_RAPIDAPI_KEY" /><div class="hint">From rapidapi.com/apidojo/api/shazam</div></div>
    </div>
    <div class="card">
        <div class="section-title">Apple Music</div>
        <div class="field"><label>APPLE_MUSIC_TEAM_ID</label><input type="text" data-key="APPLE_MUSIC_TEAM_ID" /><div class="hint">10-char team ID from developer.apple.com</div></div>
        <div class="field"><label>APPLE_MUSIC_KEY_ID</label><input type="text" data-key="APPLE_MUSIC_KEY_ID" /><div class="hint">MusicKit key ID</div></div>
        <div class="field"><label>APPLE_MUSIC_PRIVATE_KEY_PATH</label><input type="text" data-key="APPLE_MUSIC_PRIVATE_KEY_PATH" /><div class="hint">Path to .p8 private key file</div></div>
    </div>
    <div class="card">
        <div class="section-title">TikTok</div>
        <div class="field"><label>TIKTOK_CLIENT_KEY</label><input type="text" data-key="TIKTOK_CLIENT_KEY" /><div class="hint">From developers.tiktok.com</div></div>
        <div class="field"><label>TIKTOK_CLIENT_SECRET</label><input type="password" data-key="TIKTOK_CLIENT_SECRET" /><div class="hint">Keep secret</div></div>
    </div>
    <div class="actions">
        <button class="btn" onclick="saveCredentials()">Save All Credentials</button>
        <div id="status" class="status"></div>
    </div>
</div>

<script>
const adminKeyInput = document.getElementById('adminKey');
adminKeyInput.value = localStorage.getItem('sp_admin_key') || '';
adminKeyInput.addEventListener('change', () => localStorage.setItem('sp_admin_key', adminKeyInput.value));

async function loadCredentials() {
    const key = adminKeyInput.value;
    if (!key) return;
    try {
        const resp = await fetch('/api/v1/admin/credentials', {headers: {'X-API-Key': key}});
        if (resp.ok) {
            const data = await resp.json();
            document.querySelectorAll('[data-key]').forEach(input => {
                const val = data[input.dataset.key] || '';
                input.value = val;
                input.placeholder = val ? '(set)' : '(not set)';
            });
        }
    } catch(e) { console.error(e); }
}

async function saveCredentials() {
    const key = adminKeyInput.value;
    if (!key) { showStatus('Enter admin key first', 'error'); return; }
    const updates = {};
    document.querySelectorAll('[data-key]').forEach(input => {
        if (input.value) updates[input.dataset.key] = input.value;
    });
    try {
        const resp = await fetch('/api/v1/admin/credentials', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json', 'X-API-Key': key},
            body: JSON.stringify(updates),
        });
        if (resp.ok) {
            showStatus('Credentials saved to .env', 'success');
        } else {
            const err = await resp.json();
            showStatus(err.detail || 'Save failed', 'error');
        }
    } catch(e) { showStatus('Network error', 'error'); }
}

function showStatus(msg, type) {
    const el = document.getElementById('status');
    el.textContent = msg;
    el.className = 'status ' + type;
    setTimeout(() => el.className = 'status', 5000);
}

loadCredentials();
</script>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.get("/api/v1/admin/credentials")
async def get_credentials(_admin: ApiKey = Depends(require_admin)):
    """Return current credential values (masked)."""
    env_values = _read_env_file()
    masked = {}
    for key in CREDENTIAL_KEYS:
        val = env_values.get(key, "")
        masked[key] = _mask_value(val) if val else ""
    return masked


@router.put("/api/v1/admin/credentials")
async def update_credentials(
    body: dict[str, str],
    _admin: ApiKey = Depends(require_admin),
):
    """Update credential values in the .env file."""
    # Only allow known credential keys
    updates = {k: v for k, v in body.items() if k in CREDENTIAL_KEYS}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid credential keys provided")

    _write_env_file(updates)
    return {"detail": f"Updated {len(updates)} credentials", "keys": list(updates.keys())}


# ---------------------------------------------------------------------------
# Monitoring Dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SoundPulse — Dashboard</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    background: #0f1117;
    color: #e0e0e0;
    min-height: 100vh;
    padding: 2rem;
  }
  h1 { font-size: 1.6rem; font-weight: 600; margin-bottom: 1.5rem; color: #fff; }
  nav { margin-bottom: 1.5rem; display: flex; gap: 1.5rem; font-size: .9rem; }
  nav a { color: #6366f1; text-decoration: none; }
  nav a.active { font-weight: 600; }
  nav a:hover { text-decoration: underline; }

  .key-bar {
    display: flex; gap: .75rem; align-items: center;
    margin-bottom: 2rem; flex-wrap: wrap;
  }
  .key-bar label { font-size: .85rem; color: #999; }
  .key-bar input {
    background: #1a1d27; border: 1px solid #2a2d37; border-radius: 6px;
    padding: .5rem .75rem; color: #e0e0e0; width: 320px; font-size: .9rem;
  }
  .key-bar input:focus { outline: none; border-color: #6366f1; }
  .key-bar button {
    background: #6366f1; color: #fff; border: none; border-radius: 6px;
    padding: .5rem 1rem; cursor: pointer; font-size: .85rem; font-weight: 500;
  }
  .key-bar button:hover { background: #4f46e5; }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
  }
  .stat-card {
    background: #1a1d27; border: 1px solid #2a2d37; border-radius: 8px;
    padding: 1.25rem; text-align: center;
  }
  .stat-value {
    font-size: 2rem; font-weight: 700; color: #fff;
    margin-bottom: .25rem;
  }
  .stat-label {
    font-size: .8rem; color: #888; text-transform: uppercase;
    letter-spacing: .05em;
  }

  .section {
    background: #1a1d27; border: 1px solid #2a2d37; border-radius: 8px;
    padding: 1.25rem 1.5rem; margin-bottom: 1.5rem;
  }
  .section-title {
    font-size: 1rem; font-weight: 600; color: #6366f1;
    border-bottom: 1px solid #2a2d37; padding-bottom: .5rem; margin-bottom: 1rem;
  }

  table { width: 100%; border-collapse: collapse; }
  th {
    text-align: left; padding: .65rem 1rem; font-size: .75rem;
    text-transform: uppercase; letter-spacing: .05em; color: #888;
    border-bottom: 1px solid #1e2130;
  }
  td { padding: .75rem 1rem; border-bottom: 1px solid #1a1d27; font-size: .9rem; }
  tr:hover td { background: #161824; }

  .bar-container {
    display: flex; align-items: center; gap: .75rem;
  }
  .bar-fill {
    height: 8px; border-radius: 4px; background: #6366f1;
    transition: width .3s;
  }
  .bar-bg {
    flex: 1; height: 8px; border-radius: 4px; background: #2a2d37;
    overflow: hidden;
  }
  .bar-label { font-size: .8rem; color: #888; min-width: 40px; text-align: right; }

  .meta { margin-top: 1rem; font-size: .75rem; color: #555; }

  .toast {
    position: fixed; bottom: 1.5rem; right: 1.5rem; padding: .75rem 1.25rem;
    border-radius: 8px; font-size: .85rem; color: #fff; opacity: 0;
    transition: opacity .3s; pointer-events: none; z-index: 999;
  }
  .toast.show { opacity: 1; }
  .toast-ok  { background: #065f46; }
  .toast-err { background: #7f1d1d; }

  .loading { color: #555; font-style: italic; }
</style>
</head>
<body>

<h1>Monitoring Dashboard</h1>
<nav>
  <a href="/admin/scrapers">Scrapers</a>
  <a href="/admin/credentials">Credentials</a>
  <a href="/admin/api-test">API Test</a>
  <a href="/admin/dashboard" class="active">Dashboard</a>
  <a href="/admin/scoring">Scoring</a>
  <a href="/docs">API Docs</a>
</nav>

<div class="key-bar">
  <label for="apiKey">Admin Key:</label>
  <input id="apiKey" type="password" placeholder="Enter admin API key" />
  <button onclick="saveKey()">Save</button>
</div>

<!-- Summary cards -->
<div class="stats-grid" id="statsGrid">
  <div class="stat-card"><div class="stat-value" id="totalTracks">--</div><div class="stat-label">Total Tracks</div></div>
  <div class="stat-card"><div class="stat-value" id="totalArtists">--</div><div class="stat-label">Total Artists</div></div>
  <div class="stat-card"><div class="stat-value" id="ingestedToday">--</div><div class="stat-label">Ingested Today</div></div>
  <div class="stat-card"><div class="stat-value" id="ingestedWeek">--</div><div class="stat-label">Ingested This Week</div></div>
</div>

<!-- Platform breakdown -->
<div class="section">
  <div class="section-title">Platform Breakdown</div>
  <table>
    <thead><tr><th>Platform</th><th>Snapshots</th><th>Share</th></tr></thead>
    <tbody id="platformBody"><tr><td colspan="3" class="loading">Loading...</td></tr></tbody>
  </table>
</div>

<!-- Genre distribution -->
<div class="section">
  <div class="section-title">Genre Distribution (Top 15)</div>
  <table>
    <thead><tr><th>Genre</th><th>Tracks</th><th>Distribution</th></tr></thead>
    <tbody id="genreBody"><tr><td colspan="3" class="loading">Loading...</td></tr></tbody>
  </table>
</div>

<p class="meta" id="refreshMeta"></p>
<div class="toast" id="toast"></div>

<script>
const API = '/api/v1/admin/dashboard-stats';
const keyInput = document.getElementById('apiKey');
const toastEl = document.getElementById('toast');
const metaEl = document.getElementById('refreshMeta');

function saveKey() {
  localStorage.setItem('sp_admin_key', keyInput.value.trim());
  toast('Key saved', 'ok');
  loadDashboard();
}
function getKey() { return localStorage.getItem('sp_admin_key') || ''; }
keyInput.value = getKey();

function headers() {
  return { 'Content-Type': 'application/json', 'X-API-Key': getKey() };
}

function toast(msg, type) {
  toastEl.textContent = msg;
  toastEl.className = 'toast show ' + (type === 'ok' ? 'toast-ok' : 'toast-err');
  setTimeout(() => { toastEl.className = 'toast'; }, 3000);
}

function fmt(n) {
  if (n == null) return '--';
  return Number(n).toLocaleString();
}

async function loadDashboard() {
  try {
    const res = await fetch(API, { headers: headers() });
    if (!res.ok) { toast('Failed to load: ' + res.status, 'err'); return; }
    const d = await res.json();

    document.getElementById('totalTracks').textContent = fmt(d.total_tracks);
    document.getElementById('totalArtists').textContent = fmt(d.total_artists);
    document.getElementById('ingestedToday').textContent = fmt(d.ingested_today);
    document.getElementById('ingestedWeek').textContent = fmt(d.ingested_this_week);

    // Platform breakdown
    const pb = document.getElementById('platformBody');
    pb.innerHTML = '';
    const totalSnaps = Object.values(d.platform_breakdown).reduce((a, b) => a + b, 0) || 1;
    const sorted = Object.entries(d.platform_breakdown).sort((a, b) => b[1] - a[1]);
    sorted.forEach(([platform, count]) => {
      const pct = Math.round(count / totalSnaps * 100);
      const tr = document.createElement('tr');
      tr.innerHTML = '<td><strong>' + platform + '</strong></td>'
        + '<td>' + fmt(count) + '</td>'
        + '<td><div class="bar-container"><div class="bar-bg"><div class="bar-fill" style="width:' + pct + '%"></div></div><span class="bar-label">' + pct + '%</span></div></td>';
      pb.appendChild(tr);
    });

    // Genre distribution
    const gb = document.getElementById('genreBody');
    gb.innerHTML = '';
    const totalGenreTracks = Object.values(d.genre_distribution).reduce((a, b) => a + b, 0) || 1;
    const genreSorted = Object.entries(d.genre_distribution).sort((a, b) => b[1] - a[1]).slice(0, 15);
    genreSorted.forEach(([genre, count]) => {
      const pct = Math.round(count / totalGenreTracks * 100);
      const tr = document.createElement('tr');
      tr.innerHTML = '<td><strong>' + genre + '</strong></td>'
        + '<td>' + fmt(count) + '</td>'
        + '<td><div class="bar-container"><div class="bar-bg"><div class="bar-fill" style="width:' + pct + '%"></div></div><span class="bar-label">' + pct + '%</span></div></td>';
      gb.appendChild(tr);
    });

    metaEl.textContent = 'Last refreshed: ' + new Date().toLocaleTimeString() + '  (auto-refresh every 60s)';
  } catch (e) {
    toast('Network error: ' + e.message, 'err');
  }
}

// Initial load + auto-refresh every 60 seconds
loadDashboard();
setInterval(loadDashboard, 60000);
</script>
</body>
</html>"""


@router.get("/admin/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    """Serve the monitoring dashboard HTML page."""
    return HTMLResponse(content=DASHBOARD_HTML)


@router.get("/api/v1/admin/dashboard-stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Return aggregate statistics for the monitoring dashboard."""
    from datetime import date as date_type, timedelta as td

    from sqlalchemy import func as sqlfunc

    from api.models.artist import Artist
    from api.models.track import Track
    from api.models.trending_snapshot import TrendingSnapshot

    today = date_type.today()
    week_ago = today - td(days=7)

    # Total counts
    total_tracks = (await db.execute(select(sqlfunc.count(Track.id)))).scalar() or 0
    total_artists = (await db.execute(select(sqlfunc.count(Artist.id)))).scalar() or 0

    # Ingested today / this week (count of snapshot rows)
    ingested_today = (
        await db.execute(
            select(sqlfunc.count(TrendingSnapshot.id)).where(
                TrendingSnapshot.snapshot_date == today,
            )
        )
    ).scalar() or 0

    ingested_this_week = (
        await db.execute(
            select(sqlfunc.count(TrendingSnapshot.id)).where(
                TrendingSnapshot.snapshot_date >= week_ago,
            )
        )
    ).scalar() or 0

    # Platform breakdown (snapshot count per platform)
    platform_rows = (
        await db.execute(
            select(
                TrendingSnapshot.platform,
                sqlfunc.count(TrendingSnapshot.id),
            ).group_by(TrendingSnapshot.platform)
        )
    ).all()
    platform_breakdown = {row[0]: row[1] for row in platform_rows}

    # Genre distribution from tracks
    genre_rows = (
        await db.execute(
            select(
                sqlfunc.unnest(Track.genres).label("genre"),
                sqlfunc.count().label("cnt"),
            ).group_by("genre").order_by(sqlfunc.count().desc()).limit(25)
        )
    ).all()
    genre_distribution = {row[0]: row[1] for row in genre_rows}

    return {
        "total_tracks": total_tracks,
        "total_artists": total_artists,
        "ingested_today": ingested_today,
        "ingested_this_week": ingested_this_week,
        "platform_breakdown": platform_breakdown,
        "genre_distribution": genre_distribution,
    }


# ---------------------------------------------------------------------------
# Scoring Config — Admin page + API
# ---------------------------------------------------------------------------

_SCORING_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "scoring.json"


def _read_scoring_config() -> dict[str, float]:
    """Read current platform weights from scoring.json."""
    from shared.constants import PLATFORM_WEIGHTS, _DEFAULT_PLATFORM_WEIGHTS

    try:
        if _SCORING_CONFIG_PATH.exists():
            with open(_SCORING_CONFIG_PATH) as f:
                data = json.load(f)
            weights = data.get("platform_weights")
            if weights and isinstance(weights, dict):
                return {k: float(v) for k, v in weights.items()}
    except Exception:
        logger.warning("Failed to read scoring config, returning in-memory weights")
    return dict(PLATFORM_WEIGHTS)


def _write_scoring_config(weights: dict[str, float]) -> None:
    """Write platform weights to scoring.json and reload in-memory constants."""
    _SCORING_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_SCORING_CONFIG_PATH, "w") as f:
        json.dump({"platform_weights": weights}, f, indent=2)
        f.write("\n")
    # Reload in-memory weights
    from shared.constants import reload_platform_weights
    reload_platform_weights()


class ScoringConfigUpdate(BaseModel):
    platform_weights: dict[str, float]


@router.get("/api/v1/admin/scoring-config")
async def get_scoring_config(
    _admin: ApiKey = Depends(require_admin),
):
    """Return current platform weights."""
    return {"platform_weights": _read_scoring_config()}


@router.put("/api/v1/admin/scoring-config")
async def put_scoring_config(
    body: ScoringConfigUpdate,
    _admin: ApiKey = Depends(require_admin),
):
    """Update platform weights. Weights must sum to ~1.0 (within 0.01 tolerance)."""
    weights = body.platform_weights
    total = sum(weights.values())
    if abs(total - 1.0) > 0.01:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"Weights must sum to 1.0 (got {total:.4f})",
                    "details": {"total": round(total, 4)},
                }
            },
        )
    # Ensure all values are non-negative
    for k, v in weights.items():
        if v < 0:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": f"Weight for '{k}' cannot be negative",
                        "details": {},
                    }
                },
            )
    _write_scoring_config(weights)
    return {"platform_weights": weights, "status": "saved"}


SCORING_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SoundPulse — Scoring Config</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    background: #0f1117;
    color: #e0e0e0;
    min-height: 100vh;
    padding: 2rem;
  }
  h1 { font-size: 1.6rem; font-weight: 600; margin-bottom: 1.5rem; color: #fff; }
  h2 { font-size: 1.15rem; font-weight: 600; color: #fff; margin: 1.5rem 0 1rem; }
  nav { margin-bottom: 1.5rem; display: flex; gap: 1.5rem; font-size: .9rem; }
  nav a { color: #6366f1; text-decoration: none; }
  nav a.active { font-weight: 600; }
  nav a:hover { text-decoration: underline; }

  .key-bar {
    display: flex; gap: .75rem; align-items: center;
    margin-bottom: 2rem; flex-wrap: wrap;
  }
  .key-bar label { font-size: .85rem; color: #999; }
  .key-bar input {
    background: #1a1d27; border: 1px solid #2a2d37; border-radius: 6px;
    padding: .5rem .75rem; color: #e0e0e0; width: 320px; font-size: .9rem;
  }
  .key-bar input:focus { outline: none; border-color: #6366f1; }
  .key-bar button {
    background: #6366f1; color: #fff; border: none; border-radius: 6px;
    padding: .5rem 1rem; cursor: pointer; font-size: .85rem; font-weight: 500;
  }
  .key-bar button:hover { background: #4f46e5; }

  .section {
    background: #1a1d27; border: 1px solid #2a2d37; border-radius: 8px;
    padding: 1.25rem 1.5rem; margin-bottom: 1.5rem;
  }
  .section-title {
    font-size: 1rem; font-weight: 600; color: #6366f1;
    border-bottom: 1px solid #2a2d37; padding-bottom: .5rem; margin-bottom: 1rem;
  }

  .weight-row {
    display: flex; align-items: center; gap: 1rem;
    padding: .75rem 0; border-bottom: 1px solid #22253a;
  }
  .weight-row:last-child { border-bottom: none; }
  .weight-label {
    min-width: 120px; font-weight: 500; font-size: .9rem; text-transform: capitalize;
  }
  .weight-slider {
    flex: 1; -webkit-appearance: none; appearance: none;
    height: 6px; border-radius: 3px; background: #2a2d37; outline: none;
  }
  .weight-slider::-webkit-slider-thumb {
    -webkit-appearance: none; appearance: none;
    width: 18px; height: 18px; border-radius: 50%;
    background: #6366f1; cursor: pointer; border: 2px solid #0f1117;
  }
  .weight-slider::-moz-range-thumb {
    width: 18px; height: 18px; border-radius: 50%;
    background: #6366f1; cursor: pointer; border: 2px solid #0f1117;
  }
  .weight-number {
    width: 70px; background: #0f1117; border: 1px solid #2a2d37;
    border-radius: 4px; padding: .4rem .5rem; color: #e0e0e0;
    font-size: .85rem; text-align: center; font-family: monospace;
  }
  .weight-number:focus { outline: none; border-color: #6366f1; }
  .weight-pct {
    min-width: 42px; font-size: .8rem; color: #888; text-align: right;
  }

  .total-bar {
    display: flex; align-items: center; gap: 1rem;
    margin-top: 1rem; padding: 1rem; border-radius: 6px;
    background: #0f1117; border: 1px solid #2a2d37;
  }
  .total-label { font-weight: 600; font-size: .9rem; }
  .total-value { font-family: monospace; font-size: 1.1rem; font-weight: 700; }
  .total-ok { color: #34d399; }
  .total-bad { color: #f87171; }
  .total-fill {
    flex: 1; height: 8px; border-radius: 4px; background: #2a2d37; overflow: hidden;
  }
  .total-fill-inner {
    height: 100%; border-radius: 4px; transition: width .2s, background .2s;
  }

  .btn-save {
    background: #6366f1; color: #fff; border: none; border-radius: 6px;
    padding: .6rem 2rem; cursor: pointer; font-size: .9rem; font-weight: 600;
    margin-top: 1rem;
  }
  .btn-save:hover { background: #4f46e5; }
  .btn-save:disabled { opacity: .5; cursor: not-allowed; }
  .btn-reset {
    background: #374151; color: #e0e0e0; border: none; border-radius: 6px;
    padding: .6rem 1.5rem; cursor: pointer; font-size: .85rem; font-weight: 500;
    margin-top: 1rem; margin-left: .5rem;
  }
  .btn-reset:hover { background: #4b5563; }

  .formula-box {
    background: #0f1117; border: 1px solid #2a2d37; border-radius: 6px;
    padding: 1rem 1.25rem; font-size: .85rem; line-height: 1.6; color: #c8d6e5;
  }
  .formula-box code {
    background: #1e2130; padding: .15rem .4rem; border-radius: 3px;
    font-family: 'Menlo', 'Consolas', monospace; font-size: .82rem; color: #a5b4fc;
  }

  .toast {
    position: fixed; bottom: 1.5rem; right: 1.5rem; padding: .75rem 1.25rem;
    border-radius: 8px; font-size: .85rem; color: #fff; opacity: 0;
    transition: opacity .3s; pointer-events: none; z-index: 999;
  }
  .toast.show { opacity: 1; }
  .toast-ok  { background: #065f46; }
  .toast-err { background: #7f1d1d; }
</style>
</head>
<body>

<h1>Scoring Configuration</h1>
<nav>
  <a href="/admin/scrapers">Scrapers</a>
  <a href="/admin/credentials">Credentials</a>
  <a href="/admin/api-test">API Test</a>
  <a href="/admin/dashboard">Dashboard</a>
  <a href="/admin/scoring" class="active">Scoring</a>
  <a href="/docs">API Docs</a>
</nav>

<div class="key-bar">
  <label for="apiKey">Admin Key:</label>
  <input id="apiKey" type="password" placeholder="Enter admin API key" />
  <button onclick="saveKey()">Save</button>
</div>

<!-- Formula explanation -->
<div class="section">
  <div class="section-title">Composite Scoring Formula</div>
  <div class="formula-box">
    <p>The composite score is a <strong>weighted average</strong> of normalized platform scores (0-100 scale).</p>
    <br>
    <p><code>composite = SUM(weight[p] * score[p]) / SUM(weight[p])</code> &mdash; for all platforms <em>p</em> with available data.</p>
    <br>
    <p>Each platform's raw score is first normalized to a 0-100 scale using rolling 90-day percentiles
    (5th and 99th). The weights below control how much each platform contributes to the final composite score.
    Only platforms with data are included; their weights are re-normalized so the composite always uses the
    full available signal.</p>
  </div>
</div>

<!-- Weights editor -->
<div class="section">
  <div class="section-title">Platform Weights</div>
  <div id="weightsContainer"></div>

  <div class="total-bar">
    <span class="total-label">Total:</span>
    <span class="total-value" id="totalValue">0.00</span>
    <div class="total-fill"><div class="total-fill-inner" id="totalFill"></div></div>
  </div>

  <div style="display:flex;gap:.5rem;flex-wrap:wrap;">
    <button class="btn-save" id="btnSave" onclick="saveWeights()" disabled>Save Weights</button>
    <button class="btn-reset" onclick="resetDefaults()">Reset to Defaults</button>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const API = '/api/v1/admin/scoring-config';
const keyInput = document.getElementById('apiKey');
const toastEl = document.getElementById('toast');
const container = document.getElementById('weightsContainer');
const totalValueEl = document.getElementById('totalValue');
const totalFillEl = document.getElementById('totalFill');
const btnSave = document.getElementById('btnSave');

const DEFAULTS = {
  spotify: 0.25, tiktok: 0.25, shazam: 0.15,
  apple_music: 0.15, chartmetric: 0.10, radio: 0.10, kworb: 0.05
};

let weights = {};

function saveKey() {
  localStorage.setItem('sp_admin_key', keyInput.value.trim());
  toast('Key saved', 'ok');
  loadConfig();
}
function getKey() { return localStorage.getItem('sp_admin_key') || ''; }
keyInput.value = getKey();

function headers() {
  return { 'Content-Type': 'application/json', 'X-API-Key': getKey() };
}

function toast(msg, type) {
  toastEl.textContent = msg;
  toastEl.className = 'toast show ' + (type === 'ok' ? 'toast-ok' : 'toast-err');
  setTimeout(() => { toastEl.className = 'toast'; }, 3000);
}

function formatLabel(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function renderWeights() {
  container.innerHTML = '';
  const platforms = Object.keys(weights);
  platforms.forEach(p => {
    const val = weights[p];
    const row = document.createElement('div');
    row.className = 'weight-row';
    row.innerHTML = `
      <span class="weight-label">${formatLabel(p)}</span>
      <input type="range" class="weight-slider" id="slider_${p}"
             min="0" max="0.5" step="0.01" value="${val}"
             oninput="onSlider('${p}', this.value)">
      <input type="number" class="weight-number" id="num_${p}"
             min="0" max="1" step="0.01" value="${val}"
             onchange="onNumber('${p}', this.value)">
      <span class="weight-pct" id="pct_${p}">${(val * 100).toFixed(0)}%</span>
    `;
    container.appendChild(row);
  });
  updateTotal();
}

function onSlider(platform, val) {
  val = parseFloat(val) || 0;
  weights[platform] = val;
  document.getElementById('num_' + platform).value = val;
  document.getElementById('pct_' + platform).textContent = (val * 100).toFixed(0) + '%';
  updateTotal();
}

function onNumber(platform, val) {
  val = Math.max(0, Math.min(1, parseFloat(val) || 0));
  weights[platform] = val;
  document.getElementById('slider_' + platform).value = val;
  document.getElementById('num_' + platform).value = val;
  document.getElementById('pct_' + platform).textContent = (val * 100).toFixed(0) + '%';
  updateTotal();
}

function updateTotal() {
  const total = Object.values(weights).reduce((s, v) => s + v, 0);
  const rounded = Math.round(total * 10000) / 10000;
  totalValueEl.textContent = rounded.toFixed(4);
  const ok = Math.abs(rounded - 1.0) <= 0.01;
  totalValueEl.className = 'total-value ' + (ok ? 'total-ok' : 'total-bad');
  const pct = Math.min(100, rounded * 100);
  totalFillEl.style.width = pct + '%';
  totalFillEl.style.background = ok ? '#34d399' : '#f87171';
  btnSave.disabled = !ok;
}

async function loadConfig() {
  try {
    const res = await fetch(API, { headers: headers() });
    if (!res.ok) { toast('Failed to load config: ' + res.status, 'err'); return; }
    const data = await res.json();
    weights = data.platform_weights || {};
    renderWeights();
  } catch (e) {
    toast('Network error: ' + e.message, 'err');
  }
}

async function saveWeights() {
  const total = Object.values(weights).reduce((s, v) => s + v, 0);
  if (Math.abs(total - 1.0) > 0.01) {
    toast('Weights must sum to 1.0 (currently ' + total.toFixed(4) + ')', 'err');
    return;
  }
  try {
    const res = await fetch(API, {
      method: 'PUT', headers: headers(),
      body: JSON.stringify({ platform_weights: weights })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      toast('Save failed: ' + (err.detail?.error?.message || res.status), 'err');
      return;
    }
    toast('Weights saved successfully', 'ok');
  } catch (e) {
    toast('Error: ' + e.message, 'err');
  }
}

function resetDefaults() {
  weights = { ...DEFAULTS };
  renderWeights();
  toast('Reset to defaults (not saved yet)', 'ok');
}

// Initial load
loadConfig();
</script>
</body>
</html>"""


@router.get("/admin/scoring", response_class=HTMLResponse)
async def scoring_page():
    """Serve the scoring configuration admin page."""
    return HTMLResponse(content=SCORING_HTML)


# ---------------------------------------------------------------------------
# Data Flow / Architecture Stats endpoint
# ---------------------------------------------------------------------------

@router.get("/admin/data-flow")
async def get_data_flow(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """
    Returns live pipeline statistics for the architecture diagram:
    scraper statuses, table row counts, coverage metrics, and data freshness.
    """
    from datetime import datetime, timezone
    from sqlalchemy import func, text, distinct
    from api.models.scraper_config import ScraperConfig
    from api.models.trending_snapshot import TrendingSnapshot
    from api.models.track import Track
    from api.models.prediction import Prediction
    from api.models.backtest_result import BacktestResult

    # --- Scrapers ---
    scraper_rows = (await db.execute(select(ScraperConfig))).scalars().all()
    scrapers = [
        {
            "id": s.id,
            "enabled": s.enabled,
            "last_status": s.last_status,
            "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
            "last_record_count": s.last_record_count,
            "last_error": s.last_error,
        }
        for s in scraper_rows
    ]

    # --- trending_snapshots ---
    snap_total = (await db.execute(select(func.count()).select_from(TrendingSnapshot))).scalar() or 0
    snap_latest = (await db.execute(select(func.max(TrendingSnapshot.snapshot_date)))).scalar()
    snap_distinct_dates = (
        await db.execute(select(func.count(distinct(TrendingSnapshot.snapshot_date))))
    ).scalar() or 0

    # Platform breakdown (top 8)
    platform_rows = (
        await db.execute(
            select(TrendingSnapshot.platform, func.count().label("cnt"))
            .group_by(TrendingSnapshot.platform)
            .order_by(func.count().desc())
            .limit(8)
        )
    ).all()
    platforms_breakdown = {r.platform: r.cnt for r in platform_rows}

    # --- tracks ---
    track_total = (await db.execute(select(func.count()).select_from(Track))).scalar() or 0
    with_spotify_id = (
        await db.execute(
            select(func.count()).select_from(Track).where(Track.spotify_id.isnot(None))
        )
    ).scalar() or 0
    with_audio_features = (
        await db.execute(
            select(func.count()).select_from(Track).where(Track.audio_features.isnot(None))
        )
    ).scalar() or 0

    # --- predictions ---
    pred_total = (await db.execute(select(func.count()).select_from(Prediction))).scalar() or 0

    # --- backtest_results ---
    bt_total = (await db.execute(select(func.count()).select_from(BacktestResult))).scalar() or 0

    # --- scraper_configs count ---
    cfg_total = len(scraper_rows)
    cfg_enabled = sum(1 for s in scraper_rows if s.enabled)

    return {
        "data": {
            "scrapers": scrapers,
            "tables": {
                "trending_snapshots": {
                    "total_rows": snap_total,
                    "latest_date": snap_latest.isoformat() if snap_latest else None,
                    "distinct_dates": snap_distinct_dates,
                    "platforms": platforms_breakdown,
                },
                "tracks": {
                    "total_rows": track_total,
                    "with_spotify_id": with_spotify_id,
                    "with_audio_features": with_audio_features,
                },
                "predictions": {"total_rows": pred_total},
                "backtest_results": {"total_rows": bt_total},
                "scraper_configs": {"total_rows": cfg_total, "enabled": cfg_enabled},
            },
            "coverage": {
                "audio_features_pct": round(with_audio_features / track_total * 100, 1) if track_total else 0,
                "prediction_coverage_pct": round(pred_total / track_total * 100, 1) if track_total else 0,
                "model_trained": pred_total > 0,
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    }
