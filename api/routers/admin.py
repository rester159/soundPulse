from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
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


@router.get("/api/v1/admin/deploy-check")
async def deploy_check():
    """Returns the deploy timestamp. If this changes, the code is fresh."""
    return {"deployed_code": "2026-04-12T00:15:00Z", "routes_file": "admin.py"}


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


@router.post("/api/v1/admin/artists/backfill-spotify-ids-from-chartmetric")
async def backfill_spotify_ids_from_chartmetric(
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Backfill artists.spotify_id using Chartmetric's /api/artist/{id}
    endpoint as the source. Chartmetric stores the Spotify artist ID
    as part of artist metadata, so we can pull it without touching
    Spotify's API at all — zero rate-limit risk.

    Target rows: artists WHERE chartmetric_id IS NOT NULL AND spotify_id IS NULL
    (only artists we already have a Chartmetric handle for).

    Called iteratively — pass `limit` up to 500 per call. The 1,732
    artists currently missing a spotify_id can be processed in ~4 calls.
    """
    import os
    import httpx
    from api.models.artist import Artist

    api_key = os.environ.get("CHARTMETRIC_API_KEY", "")
    if not api_key:
        return {"error": "CHARTMETRIC_API_KEY not set"}

    limit = max(1, min(limit, 500))

    result = await db.execute(
        select(Artist)
        .where(Artist.chartmetric_id.isnot(None))
        .where(Artist.spotify_id.is_(None))
        .order_by(Artist.id)
        .limit(limit)
    )
    candidates = result.scalars().all()
    if not candidates:
        return {"checked": 0, "matched": 0, "skipped": 0, "detail": "no artists need backfill"}

    matched = 0
    skipped = 0
    errors = 0
    status_counts: dict[int, int] = {}
    last_error_sample: str | None = None

    async with httpx.AsyncClient(timeout=30) as client:
        # Refresh-token -> bearer token exchange (same as Chartmetric scrapers).
        try:
            auth_resp = await client.post(
                "https://api.chartmetric.com/api/token",
                json={"refreshtoken": api_key},
            )
            auth_resp.raise_for_status()
            token = auth_resp.json().get("token") or auth_resp.json().get("access_token")
            if not token:
                return {"error": f"Chartmetric auth response missing token: {list(auth_resp.json().keys())}"}
        except Exception as exc:
            return {"error": f"Chartmetric auth failed: {exc}"}

        headers = {"Authorization": f"Bearer {token}"}

        for artist in candidates:
            cm_id = artist.chartmetric_id
            try:
                resp = await client.get(
                    f"https://api.chartmetric.com/api/artist/{cm_id}",
                    headers=headers,
                )
                if resp.status_code != 200:
                    errors += 1
                    status_counts[resp.status_code] = status_counts.get(resp.status_code, 0) + 1
                    if last_error_sample is None:
                        last_error_sample = f"HTTP {resp.status_code}: {(resp.text or '')[:200]}"
                    continue
                payload = resp.json()
                # Chartmetric wraps artist data under `obj`. The spotify
                # artist ID has been observed as both `sp_artist_id` and
                # `spotify_artist_id` depending on the tier / endpoint.
                obj = payload.get("obj") if isinstance(payload, dict) else None
                if not isinstance(obj, dict):
                    skipped += 1
                    continue
                sp_id = (
                    obj.get("sp_artist_id")
                    or obj.get("spotify_artist_id")
                    or obj.get("spotify_id")
                )
                if not sp_id:
                    skipped += 1
                    continue
                artist.spotify_id = str(sp_id)
                # Chartmetric also often carries genre tags here — pull
                # them in as a free classifier signal.
                cm_genres = obj.get("genres") or obj.get("tags") or []
                if cm_genres:
                    existing = artist.metadata_json or {}
                    artist.metadata_json = {
                        **existing,
                        "chartmetric_genres": cm_genres,
                        "needs_classification": True,
                    }
                matched += 1
            except httpx.HTTPError as exc:
                errors += 1
                if last_error_sample is None:
                    last_error_sample = f"network: {exc}"
            # Chartmetric rate limit is 2 req/s; we run at ~1.8/s to be safe.
            await asyncio.sleep(0.55)

        await db.commit()

    return {
        "checked": len(candidates),
        "matched": matched,
        "skipped": skipped,
        "errors": errors,
        "status_counts": status_counts,
        "last_error_sample": last_error_sample,
        "detail": "paged: call again until matched=0 (Artist.chartmetric_id IS NOT NULL AND spotify_id IS NULL)",
    }


@router.get("/api/v1/admin/chartmetric/probe-sub-endpoints")
async def chartmetric_probe_sub_endpoints(
    cm_track_id: int = 118981138,  # Espresso by default — known-good popular track
    _admin: ApiKey = Depends(require_admin),
):
    """
    Probe several candidate Chartmetric sub-endpoints for audio features.
    Built after /api/track/{id} was shown to return only `tempo` and
    `duration_ms` — we need to know whether a sub-path carries the full
    Spotify audio features set before rewriting the scraper.

    Tries in order:
      /api/track/{id}/audio-features
      /api/track/{id}/sp-audio-features
      /api/track/{id}/spotify-audio-features
      /api/track/{id}/audio-analysis
      /api/track/{id}?embed=audio_features
      /api/v2/track/{id}  (in case there's a v2 with richer data)
    """
    import os
    import time as time_mod
    import httpx

    api_key = os.environ.get("CHARTMETRIC_API_KEY", "")
    if not api_key:
        return {"error": "CHARTMETRIC_API_KEY not set"}

    async with httpx.AsyncClient(timeout=15) as client:
        auth_resp = await client.post(
            "https://api.chartmetric.com/api/token",
            json={"refreshtoken": api_key},
        )
        if auth_resp.status_code != 200:
            return {"auth_error": auth_resp.status_code}
        token = auth_resp.json().get("token") or auth_resp.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}

        candidates = [
            ("sub_audio_features", f"https://api.chartmetric.com/api/track/{cm_track_id}/audio-features"),
            ("sub_sp_audio_features", f"https://api.chartmetric.com/api/track/{cm_track_id}/sp-audio-features"),
            ("sub_spotify_audio_features", f"https://api.chartmetric.com/api/track/{cm_track_id}/spotify-audio-features"),
            ("sub_audio_analysis", f"https://api.chartmetric.com/api/track/{cm_track_id}/audio-analysis"),
            ("track_with_embed", f"https://api.chartmetric.com/api/track/{cm_track_id}?embed=audio_features"),
            ("v2_track", f"https://api.chartmetric.com/api/v2/track/{cm_track_id}"),
        ]

        results: dict[str, dict] = {}
        for name, url in candidates:
            t0 = time_mod.time()
            try:
                resp = await client.get(url, headers=headers)
                elapsed = int((time_mod.time() - t0) * 1000)
                entry: dict[str, Any] = {
                    "status_code": resp.status_code,
                    "elapsed_ms": elapsed,
                    "content_length": len(resp.content or b""),
                }
                if resp.status_code == 200:
                    try:
                        payload = resp.json()
                        entry["top_level_keys"] = list(payload.keys()) if isinstance(payload, dict) else "not-a-dict"
                        # If it has an obj wrapper, enumerate the inner keys
                        obj = payload.get("obj") if isinstance(payload, dict) else None
                        if isinstance(obj, dict):
                            entry["obj_keys"] = list(obj.keys())[:50]
                        # Feed the whole payload through the extractor
                        from scrapers.chartmetric_audio_features import _extract_audio_features
                        extracted = _extract_audio_features(payload)
                        entry["extracted"] = extracted
                    except Exception as exc:
                        entry["parse_error"] = str(exc)[:200]
                elif resp.status_code < 500:
                    entry["body_sample"] = (resp.text or "")[:200]
                results[name] = entry
            except Exception as exc:
                results[name] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
            # Small delay to avoid tripping Chartmetric's rate limit
            # within a single probe burst
            await asyncio.sleep(1.5)

    return {"cm_track_id": cm_track_id, "results": results}


@router.get("/api/v1/admin/chartmetric/probe")
async def chartmetric_probe(
    cm_track_id: int = 1,
    _admin: ApiKey = Depends(require_admin),
):
    """
    Synchronous diagnostic: authenticate with Chartmetric, call
    /api/track/{cm_track_id}, and return a structured report. Tells us
    in one ~5-second call whether:
      - our Chartmetric token still works
      - /api/track/{id} responds and how fast
      - what response shape Chartmetric returns (top-level keys)
      - whether audio features are present (and in which shape)
      - whether sp_artist_id / spotify_id fields are present
      - what Retry-After header (if any) is returned

    Built 2026-04-12 to diagnose why chartmetric_audio_features and
    chartmetric_artist_tracks both hang after their first flush with
    no interim progress and no log signal we can access.
    """
    import os
    import time as time_mod
    import httpx

    api_key = os.environ.get("CHARTMETRIC_API_KEY", "")
    if not api_key:
        return {"error": "CHARTMETRIC_API_KEY not set"}

    report: dict[str, Any] = {
        "cm_track_id": cm_track_id,
        "auth": {},
        "track_call": {},
    }

    async with httpx.AsyncClient(timeout=15) as client:
        # ---- Auth probe ----
        t0 = time_mod.time()
        try:
            auth_resp = await client.post(
                "https://api.chartmetric.com/api/token",
                json={"refreshtoken": api_key},
            )
            report["auth"] = {
                "elapsed_ms": int((time_mod.time() - t0) * 1000),
                "status_code": auth_resp.status_code,
                "retry_after": auth_resp.headers.get("Retry-After"),
            }
            if auth_resp.status_code != 200:
                report["auth"]["body_sample"] = (auth_resp.text or "")[:300]
                return report
            token = auth_resp.json().get("token") or auth_resp.json().get("access_token")
            if not token:
                report["auth"]["error"] = f"no token key in response: {list(auth_resp.json().keys())}"
                return report
            report["auth"]["success"] = True
        except Exception as exc:
            report["auth"]["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
            report["auth"]["elapsed_ms"] = int((time_mod.time() - t0) * 1000)
            return report

        # ---- Track endpoint probe ----
        t1 = time_mod.time()
        try:
            track_resp = await client.get(
                f"https://api.chartmetric.com/api/track/{cm_track_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            elapsed_track = int((time_mod.time() - t1) * 1000)
            report["track_call"] = {
                "elapsed_ms": elapsed_track,
                "status_code": track_resp.status_code,
                "retry_after": track_resp.headers.get("Retry-After"),
                "content_length": len(track_resp.content or b""),
            }
            if track_resp.status_code != 200:
                report["track_call"]["body_sample"] = (track_resp.text or "")[:400]
                return report

            try:
                payload = track_resp.json()
            except Exception as exc:
                report["track_call"]["parse_error"] = str(exc)[:200]
                return report

            report["track_call"]["top_level_keys"] = list(payload.keys()) if isinstance(payload, dict) else []
            if isinstance(payload, dict) and isinstance(payload.get("obj"), dict):
                obj = payload["obj"]
                report["track_call"]["obj_keys"] = list(obj.keys())
                # Look for audio feature fields in likely shapes
                af_keys = [
                    "tempo", "energy", "danceability", "valence",
                    "acousticness", "instrumentalness", "liveness",
                    "speechiness", "loudness", "key", "mode",
                    "duration_ms", "time_signature",
                ]
                flat_present = {k: obj.get(k) for k in af_keys if obj.get(k) is not None}
                nested_af = obj.get("audio_features") if isinstance(obj.get("audio_features"), dict) else None
                nested_sp = obj.get("sp_audio_features") if isinstance(obj.get("sp_audio_features"), dict) else None
                report["track_call"]["audio_features_flat"] = flat_present or None
                report["track_call"]["audio_features_nested_audio_features"] = nested_af
                report["track_call"]["audio_features_nested_sp_audio_features"] = nested_sp
                # Use the scraper's own extractor to see what it would return
                from scrapers.chartmetric_audio_features import _extract_audio_features
                report["track_call"]["extracted_by_scraper"] = _extract_audio_features(payload)
                # Spotify ID fields of interest
                report["track_call"]["sp_track_id"] = (
                    obj.get("spotify_track_id") or obj.get("spotify_id") or obj.get("sp_track_id")
                )
                report["track_call"]["sp_artist_id"] = (
                    obj.get("spotify_artist_id") or obj.get("sp_artist_id")
                )
                report["track_call"]["isrc"] = obj.get("isrc")
                report["track_call"]["title"] = obj.get("name") or obj.get("title")

        except Exception as exc:
            report["track_call"]["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
            report["track_call"]["elapsed_ms"] = int((time_mod.time() - t1) * 1000)

    return report


# Breakout Analysis Engine — Layer 6 (breakoutengine_prd.md)
@router.post("/api/v1/admin/sweeps/lyrical-analysis", status_code=202)
async def trigger_lyrical_analysis(
    only_genre: str | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Trigger LLM-powered lyrical analysis. Optionally limit to one genre."""
    from api.services.lyrical_analysis import analyze_all_genres
    stats = await analyze_all_genres(db, only_genre=only_genre)
    return {"detail": "lyrical analysis complete", "stats": stats}


@router.get("/api/v1/admin/lyrical-analyses")
async def get_lyrical_analyses(
    genre: str | None = None,
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Browse cached lyrical analyses."""
    from api.models.genre_lyrical_analysis import GenreLyricalAnalysis
    stmt = (
        select(GenreLyricalAnalysis)
        .order_by(GenreLyricalAnalysis.window_end.desc())
        .limit(min(limit, 100))
    )
    if genre:
        stmt = stmt.where(GenreLyricalAnalysis.genre_id == genre)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {
        "analyses": [
            {
                "genre": r.genre_id,
                "window_end": r.window_end.isoformat(),
                "breakout_count": r.breakout_count,
                "baseline_count": r.baseline_count,
                "analysis": r.analysis_json,
            }
            for r in rows
        ],
        "count": len(rows),
    }


# Breakout Analysis Engine — Layer 5 (breakoutengine_prd.md)
@router.get("/api/v1/admin/tracks/needing-lyrics")
async def get_tracks_needing_lyrics(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Return tracks that don't have lyrics in track_lyrics yet.
    Prioritizes tracks that have appeared in breakout events
    (since those are the ones we'll feed to LLM lyrical analysis).
    """
    from sqlalchemy import text as sa_text
    limit = max(1, min(limit, 200))
    result = await db.execute(sa_text("""
        SELECT t.id AS track_id, t.title, t.spotify_id, t.isrc, a.name AS artist_name,
               EXISTS(SELECT 1 FROM breakout_events be WHERE be.track_id = t.id) AS is_breakout
        FROM tracks t
        LEFT JOIN artists a ON a.id = t.artist_id
        WHERE NOT EXISTS (SELECT 1 FROM track_lyrics tl WHERE tl.track_id = t.id)
          AND t.title IS NOT NULL
        ORDER BY is_breakout DESC, t.created_at DESC
        LIMIT :lim OFFSET :off
    """), {"lim": limit, "off": offset})
    return {
        "data": [
            {
                "track_id": str(r[0]),
                "title": r[1],
                "spotify_id": r[2],
                "isrc": r[3],
                "artist_name": r[4],
                "is_breakout": bool(r[5]),
            }
            for r in result.fetchall()
        ],
    }


@router.post("/api/v1/admin/lyrics/bulk", status_code=201)
async def bulk_ingest_lyrics(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Bulk-ingest lyrics rows. Body shape:
      {"items": [{"track_id": "...", "lyrics_text": "...", ...features...}]}
    """
    from api.models.track_lyrics import TrackLyrics
    import uuid as uuid_mod
    items = body.get("items") or []
    inserted = 0
    skipped = 0
    errors = 0
    for item in items:
        track_id = item.get("track_id")
        lyrics_text = item.get("lyrics_text")
        if not track_id or not lyrics_text:
            errors += 1
            continue
        # Skip if already exists
        from sqlalchemy import select as sa_select
        existing = await db.execute(
            sa_select(TrackLyrics.id).where(TrackLyrics.track_id == track_id)
        )
        if existing.scalar_one_or_none() is not None:
            skipped += 1
            continue
        try:
            row = TrackLyrics(
                id=uuid_mod.uuid4(),
                track_id=uuid_mod.UUID(track_id),
                lyrics_text=lyrics_text,
                word_count=item.get("word_count"),
                line_count=item.get("line_count"),
                vocabulary_richness=item.get("vocabulary_richness"),
                section_structure=item.get("section_structure"),
                themes=item.get("themes"),
                primary_theme=item.get("primary_theme"),
                language=item.get("language"),
                genius_url=item.get("genius_url"),
                genius_song_id=item.get("genius_song_id"),
                features_json=item.get("features_json"),
            )
            db.add(row)
            inserted += 1
        except Exception:
            errors += 1
    if inserted:
        await db.commit()
    return {"data": {"received": len(items), "inserted": inserted, "skipped": skipped, "errors": errors}}


# Breakout Analysis Engine — Layer 4 (breakoutengine_prd.md)
@router.get("/api/v1/admin/gap-finder")
async def find_genre_gaps(
    genre: str,
    n_clusters: int | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Find underserved sonic zones in a genre via K-means clustering of
    audio features. Returns clusters sorted by gap_score (highest =
    biggest opportunity).
    """
    from api.services.gap_finder import find_gaps
    return await find_gaps(db, genre, n_clusters=n_clusters)


# Breakout Analysis Engine — Layer 2 (breakoutengine_prd.md)
@router.post("/api/v1/admin/sweeps/feature-delta-analysis", status_code=202)
async def trigger_feature_delta_analysis(
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Trigger feature delta analysis for all genres with breakouts."""
    from api.services.feature_delta_analysis import compute_all_feature_deltas
    stats = await compute_all_feature_deltas(db)
    return {"detail": "feature delta analysis complete", "stats": stats}


@router.get("/api/v1/admin/feature-deltas")
async def get_feature_deltas(
    genre: str | None = None,
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Return cached genre feature delta analyses, optionally filtered."""
    from api.models.genre_feature_delta import GenreFeatureDelta
    stmt = (
        select(GenreFeatureDelta)
        .order_by(GenreFeatureDelta.window_end.desc(), GenreFeatureDelta.breakout_count.desc())
        .limit(min(limit, 100))
    )
    if genre:
        stmt = stmt.where(GenreFeatureDelta.genre_id == genre)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {
        "deltas": [
            {
                "genre": r.genre_id,
                "window": [r.window_start.isoformat(), r.window_end.isoformat()],
                "breakout_count": r.breakout_count,
                "baseline_count": r.baseline_count,
                "deltas": r.deltas_json,
                "significance": r.significance_json,
                "top_differentiators": r.top_differentiators or [],
            }
            for r in rows
        ],
        "count": len(rows),
    }


# ─── Settings → Agents + Tools registry ──────────────────────────────────

@router.get("/api/v1/admin/agents")
async def list_agents(
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """List all agents in the registry."""
    from api.models.agents_tools import AgentRegistry
    result = await db.execute(
        select(AgentRegistry).order_by(AgentRegistry.code_letter, AgentRegistry.name)
    )
    agents = result.scalars().all()
    return {
        "agents": [
            {
                "id": a.id,
                "name": a.name,
                "code_letter": a.code_letter,
                "purpose": a.purpose,
                "instructions": a.instructions,
                "skills": a.skills or [],
                "actions": a.actions or [],
                "interdependencies": a.interdependencies or [],
                "enabled": a.enabled,
            }
            for a in agents
        ],
        "count": len(agents),
    }


@router.get("/api/v1/admin/tools")
async def list_tools(
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    List all tools in the registry, with credential availability detected
    by checking if all required env vars are set on this process.
    """
    import os
    from api.models.agents_tools import ToolsRegistry
    result = await db.execute(
        select(ToolsRegistry).order_by(ToolsRegistry.category, ToolsRegistry.display_name)
    )
    tools = result.scalars().all()
    out = []
    for t in tools:
        env_vars = t.credential_env_vars or []
        missing = [v for v in env_vars if not os.environ.get(v)]
        out.append({
            "id": t.id,
            "display_name": t.display_name,
            "category": t.category,
            "description": t.description,
            "api_kind": t.api_kind,
            "auth_kind": t.auth_kind,
            "credential_env_vars": env_vars,
            "credentials_configured": len(missing) == 0 if env_vars else True,
            "missing_env_vars": missing,
            "documentation_url": t.documentation_url,
            "cost_model": t.cost_model,
            "automation_class": t.automation_class,
            "status": t.status,
            "capabilities": t.capabilities or [],
            "notes": t.notes,
        })
    return {"tools": out, "count": len(out)}


@router.get("/api/v1/admin/agent-tool-grants")
async def list_grants(
    pivot: str = "by_tool",
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Return the agent↔tool grants in two pivots:
      - pivot=by_tool  → for each tool, the list of agents granted access
      - pivot=by_agent → for each agent, the list of tools granted access
    Same data, two views.
    """
    from sqlalchemy import text as sa_text
    result = await db.execute(sa_text("""
        SELECT
            atg.agent_id,
            ar.name AS agent_name,
            ar.code_letter,
            atg.tool_id,
            tr.display_name AS tool_name,
            tr.category AS tool_category,
            tr.status AS tool_status,
            tr.automation_class
        FROM agent_tool_grants atg
        JOIN agent_registry ar ON ar.id = atg.agent_id
        JOIN tools_registry tr ON tr.id = atg.tool_id
        ORDER BY ar.code_letter, tr.category, tr.display_name
    """))
    rows = result.fetchall()

    if pivot == "by_agent":
        by_agent: dict[str, dict] = {}
        for r in rows:
            if r[0] not in by_agent:
                by_agent[r[0]] = {
                    "agent_id": r[0],
                    "agent_name": r[1],
                    "code_letter": r[2],
                    "tools": [],
                }
            by_agent[r[0]]["tools"].append({
                "tool_id": r[3],
                "tool_name": r[4],
                "category": r[5],
                "status": r[6],
                "automation_class": r[7],
            })
        return {"pivot": "by_agent", "data": list(by_agent.values())}

    by_tool: dict[str, dict] = {}
    for r in rows:
        if r[3] not in by_tool:
            by_tool[r[3]] = {
                "tool_id": r[3],
                "tool_name": r[4],
                "category": r[5],
                "status": r[6],
                "automation_class": r[7],
                "agents": [],
            }
        by_tool[r[3]]["agents"].append({
            "agent_id": r[0],
            "agent_name": r[1],
            "code_letter": r[2],
        })
    return {"pivot": "by_tool", "data": list(by_tool.values())}


@router.post("/api/v1/admin/agent-tool-grants")
async def create_grant(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Grant a tool to an agent. Body: {agent_id, tool_id, scope?}."""
    from api.models.agents_tools import AgentToolGrant
    import uuid as uuid_mod
    agent_id = body.get("agent_id")
    tool_id = body.get("tool_id")
    if not agent_id or not tool_id:
        raise HTTPException(400, "agent_id and tool_id are required")
    grant = AgentToolGrant(
        id=uuid_mod.uuid4(),
        agent_id=agent_id,
        tool_id=tool_id,
        scope=body.get("scope"),
        granted_by="admin_ui",
    )
    db.add(grant)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(409, f"grant exists or invalid: {exc}")
    return {"detail": "granted", "id": str(grant.id)}


@router.delete("/api/v1/admin/agent-tool-grants")
async def delete_grant(
    agent_id: str,
    tool_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Revoke a tool from an agent."""
    from sqlalchemy import text as sa_text
    result = await db.execute(
        sa_text("DELETE FROM agent_tool_grants WHERE agent_id = :a AND tool_id = :t RETURNING id"),
        {"a": agent_id, "t": tool_id},
    )
    deleted = result.fetchall()
    await db.commit()
    return {"detail": "revoked", "count": len(deleted)}


@router.get("/api/v1/admin/ceo-profile")
async def get_ceo_profile(
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Return the CEO profile (single row)."""
    from api.models.ceo_profile import CeoProfile
    result = await db.execute(select(CeoProfile).where(CeoProfile.id == 1))
    profile = result.scalar_one_or_none()
    if not profile:
        return {"error": "ceo_profile not initialized"}
    return {
        "id": profile.id,
        "name": profile.name,
        "email": profile.email,
        "phone": profile.phone,
        "telegram_handle": profile.telegram_handle,
        "telegram_chat_id": profile.telegram_chat_id,
        "slack_channel": profile.slack_channel,
        "preferred_channel": profile.preferred_channel,
        "escalation_severity_threshold": profile.escalation_severity_threshold,
        "quiet_hours_start": profile.quiet_hours_start.isoformat() if profile.quiet_hours_start else None,
        "quiet_hours_end": profile.quiet_hours_end.isoformat() if profile.quiet_hours_end else None,
        "timezone": profile.timezone,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


@router.put("/api/v1/admin/ceo-profile")
async def update_ceo_profile(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Update the CEO profile. Body fields are merged into the single row.
    Only known fields are accepted; unknown fields are ignored.
    """
    from api.models.ceo_profile import CeoProfile
    result = await db.execute(select(CeoProfile).where(CeoProfile.id == 1))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = CeoProfile(id=1)
        db.add(profile)

    allowed = {
        "name", "email", "phone", "telegram_handle", "telegram_chat_id",
        "slack_channel", "preferred_channel", "escalation_severity_threshold",
        "quiet_hours_start", "quiet_hours_end", "timezone",
    }
    for k, v in body.items():
        if k in allowed:
            setattr(profile, k, v)

    await db.commit()
    return {"detail": "ceo_profile updated", "id": 1}


@router.post("/api/v1/admin/sweeps/breakout-detection/backfill", status_code=202)
async def trigger_breakout_backfill(
    weeks_back: int = 78,
    step_days: int = 7,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Run historical backfill of breakout detection. Walks reference dates
    backward and detects breakouts AS IF each date were today, then
    resolves outcomes from the data we already have. Bootstrap for ML
    training (no need to wait 30 days from launch).
    """
    from api.services.breakout_detection import backfill_historical_breakouts
    stats = await backfill_historical_breakouts(
        db, weeks_back=weeks_back, step_days=step_days
    )
    return {"detail": "historical backfill complete", "stats": stats}


# Breakout Analysis Engine — Layer 1 (breakoutengine_prd.md)
@router.post("/api/v1/admin/sweeps/breakout-detection", status_code=202)
async def trigger_breakout_detection(
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Trigger an immediate breakout detection sweep."""
    from api.services.breakout_detection import sweep_breakout_detection
    stats = await sweep_breakout_detection(db)
    return {"detail": "breakout detection sweep complete", "stats": stats}


@router.get("/api/v1/admin/breakouts")
async def get_recent_breakouts(
    genre: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Return recent breakout events, optionally filtered by genre."""
    from api.models.breakout_event import BreakoutEvent
    from api.models.track import Track

    stmt = (
        select(
            BreakoutEvent.genre_id,
            BreakoutEvent.detection_date,
            BreakoutEvent.breakout_score,
            BreakoutEvent.composite_ratio,
            BreakoutEvent.velocity_ratio,
            BreakoutEvent.peak_composite,
            BreakoutEvent.platform_count,
            BreakoutEvent.outcome_label,
            Track.title,
            Track.spotify_id,
        )
        .join(Track, Track.id == BreakoutEvent.track_id)
        .order_by(BreakoutEvent.detection_date.desc(), BreakoutEvent.breakout_score.desc())
        .limit(min(limit, 200))
    )
    if genre:
        stmt = stmt.where(BreakoutEvent.genre_id == genre)

    result = await db.execute(stmt)
    rows = result.all()

    return {
        "breakouts": [
            {
                "genre": r[0],
                "detection_date": r[1].isoformat() if r[1] else None,
                "breakout_score": round(r[2], 3),
                "composite_ratio": round(r[3], 2),
                "velocity_ratio": round(r[4], 2),
                "peak_composite": round(r[5], 1),
                "platform_count": r[6],
                "outcome": r[7],
                "title": r[8],
                "spotify_id": r[9],
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.get("/api/v1/admin/spotify/cooldown")
async def get_spotify_cooldown(
    _admin: ApiKey = Depends(require_admin),
):
    """
    Report the shared Spotify rate-limit governor's state. Tells you:
      - whether the process is currently in cooldown
      - how many seconds remain
    Use before kicking off any Spotify-heavy operation.
    """
    from api.services.spotify_throttle import is_cooldown_active
    active, remaining = is_cooldown_active()
    return {
        "cooldown_active": active,
        "seconds_remaining": int(remaining),
    }


@router.post("/api/v1/admin/spotify/cooldown/clear")
async def clear_spotify_cooldown(
    _admin: ApiKey = Depends(require_admin),
):
    """Force-clear the Spotify cooldown window. Use sparingly — if it
    was set for a reason, the next call will likely re-set it."""
    from api.services.spotify_throttle import clear_cooldown
    clear_cooldown()
    return {"cleared": True}


@router.post("/api/v1/admin/artists/backfill-spotify-ids")
async def backfill_artists_spotify_ids(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Backfill artists.spotify_id via Spotify /v1/search (name match).

    Rate-limit safe: all calls go through api.services.spotify_throttle,
    which enforces a process-wide semaphore of 3, a 2 req/s delay, and
    a shared cooldown window set by any prior 429. Default `limit=50`
    (down from 300) so a single call produces a short, predictable
    burst. Call repeatedly at least a minute apart to work through the
    backlog.

    Prior incident (2026-04-11): running this endpoint 5 times in a
    row at 10 req/s triggered a 12.5h Spotify cooldown. The governor
    now caps cooldowns at 600s and blocks subsequent bursts.

    Only persists the Spotify ID when the name match is >=0.85
    Levenshtein ratio — never guesses.
    """
    import base64
    import os
    import httpx
    from Levenshtein import ratio as levenshtein_ratio
    from api.models.artist import Artist
    from api.services.entity_resolution import _normalize_name
    from api.services.spotify_throttle import (
        SpotifyCooldownActive,
        is_cooldown_active,
        throttled_request,
    )

    # Fail fast if a prior 429 cooldown is still in effect — no point
    # burning through a batch when every call will be refused.
    active, remaining = is_cooldown_active()
    if active:
        return {
            "checked": 0, "matched": 0, "skipped": 0, "errors": 0,
            "cooldown_active": True,
            "cooldown_remaining_seconds": int(remaining),
            "detail": f"Spotify cooldown active, retry in {int(remaining)}s",
        }

    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return {
            "checked": 0, "matched": 0, "skipped": 0,
            "error": "SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET not set",
        }

    # Lowered cap: short bursts paginate through the backlog safely.
    limit = max(1, min(limit, 200))

    result = await db.execute(
        select(Artist)
        .where(Artist.spotify_id.is_(None))
        .where(Artist.name.isnot(None))
        .order_by(Artist.created_at.desc())
        .limit(limit)
    )
    candidates = result.scalars().all()
    if not candidates:
        return {"checked": 0, "matched": 0, "skipped": 0, "detail": "no artists need backfill"}

    encoded = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient(timeout=30) as client:
        # Auth
        try:
            auth_resp = await client.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                headers={
                    "Authorization": f"Basic {encoded}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            auth_resp.raise_for_status()
        except Exception as exc:
            return {
                "checked": 0, "matched": 0, "skipped": 0,
                "error": f"Spotify auth failed: {exc}",
            }

        access_token = auth_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        matched = 0
        skipped = 0
        errors = 0
        status_counts: dict[int, int] = {}
        last_error_sample: str | None = None
        stopped_on_cooldown = False

        for artist in candidates:
            try:
                search_resp = await throttled_request(
                    client, "GET", "https://api.spotify.com/v1/search",
                    params={"q": artist.name, "type": "artist", "limit": 1},
                    headers=headers,
                )
            except SpotifyCooldownActive as exc:
                # First 429 sets the module-level cooldown; every subsequent
                # call in this loop raises immediately. Stop cleanly.
                stopped_on_cooldown = True
                last_error_sample = str(exc)
                break
            except Exception as exc:
                errors += 1
                if last_error_sample is None:
                    last_error_sample = f"exception: {type(exc).__name__}: {str(exc)[:200]}"
                continue

            sc = search_resp.status_code
            if sc != 200:
                errors += 1
                status_counts[sc] = status_counts.get(sc, 0) + 1
                if last_error_sample is None:
                    last_error_sample = f"HTTP {sc}: {(search_resp.text or '')[:200]}"
                continue

            items = (search_resp.json().get("artists") or {}).get("items") or []
            if not items:
                skipped += 1
                continue
            top = items[0]
            top_name = top.get("name", "")
            top_id = top.get("id")
            if not top_id:
                skipped += 1
                continue
            score = levenshtein_ratio(_normalize_name(artist.name), _normalize_name(top_name))
            if score < 0.85:
                skipped += 1
                continue
            artist.spotify_id = top_id
            sp_genres = top.get("genres") or []
            if sp_genres:
                artist.metadata_json = {
                    **(artist.metadata_json or {}),
                    "spotify_genres": sp_genres,
                    "needs_classification": True,
                }
            matched += 1

        await db.commit()

    return {
        "checked": len(candidates),
        "matched": matched,
        "skipped": skipped,
        "errors": errors,
        "status_counts": status_counts,
        "last_error_sample": last_error_sample,
        "stopped_on_cooldown": stopped_on_cooldown,
        "detail": "paged: call again at least 60s apart (Artist.spotify_id IS NULL ordered by created_at DESC)",
    }


@router.post("/api/v1/admin/artists/flag-for-classification")
async def flag_artists_for_classification(
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    One-shot: mark every artist without classification as
    `needs_classification = true` so the next sweep picks them up.

    Needed because resolve_artist used to create artists with no
    metadata_json at all, leaving them invisible to the sweep's
    pending-work query. Paired with the track_rollup signal, this
    unblocks artist genre classification for all pre-existing artists.
    """
    from sqlalchemy import text as sa_text
    result = await db.execute(sa_text("""
        UPDATE artists
        SET metadata_json =
            COALESCE(metadata_json::jsonb, '{}'::jsonb) || '{"needs_classification": true}'::jsonb
        WHERE (genres IS NULL OR array_length(genres, 1) IS NULL)
          AND (
            metadata_json IS NULL
            OR NOT ((metadata_json::jsonb) ? 'needs_classification')
            OR (metadata_json::jsonb)->>'needs_classification' NOT IN ('true', 'skipped')
          )
        RETURNING 1
    """))
    flagged = len(result.fetchall())
    await db.commit()
    return {
        "artists_flagged": flagged,
        "detail": "Flagged artists for classification sweep",
    }


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
    # Chartmetric returns cm_artist as a list for multi-artist tracks, so
    # signals_json->'cm_artist_id' can be a scalar, a number, or a JSON
    # array. Handle all three shapes and take the primary (first) ID.
    from sqlalchemy import text as sa_text
    result = await db.execute(sa_text("""
        WITH artist_cm_ids AS (
            SELECT DISTINCT ON (t.artist_id)
                t.artist_id,
                CASE
                    WHEN jsonb_typeof((ts.signals_json::jsonb)->'cm_artist_id') = 'array'
                        THEN ((ts.signals_json::jsonb)->'cm_artist_id'->>0)::bigint
                    WHEN jsonb_typeof((ts.signals_json::jsonb)->'cm_artist_id') = 'number'
                        THEN ((ts.signals_json::jsonb)->>'cm_artist_id')::bigint
                    WHEN jsonb_typeof((ts.signals_json::jsonb)->'cm_artist_id') = 'string'
                         AND ((ts.signals_json::jsonb)->>'cm_artist_id') ~ '^[0-9]+$'
                        THEN ((ts.signals_json::jsonb)->>'cm_artist_id')::bigint
                    ELSE NULL
                END AS cm_artist_id
            FROM trending_snapshots ts
            JOIN tracks t ON t.id = ts.entity_id
            WHERE ts.entity_type = 'track'
              AND (ts.signals_json::jsonb) ? 'cm_artist_id'
              AND t.artist_id IS NOT NULL
            ORDER BY t.artist_id, ts.created_at DESC
        )
        UPDATE artists a
        SET chartmetric_id = aci.cm_artist_id
        FROM artist_cm_ids aci
        WHERE a.id = aci.artist_id
          AND a.chartmetric_id IS NULL
          AND aci.cm_artist_id IS NOT NULL
        RETURNING 1
    """))
    updated_count = len(result.fetchall())
    await db.commit()
    return {
        "artists_updated": updated_count,
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

@router.get("/api/v1/admin/tracks/needing-audio-features-cm")
async def get_tracks_needing_audio_features_cm(
    limit: int = 500,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Return tracks with a chartmetric_id but no audio_features.

    Paired with the chartmetric_audio_features scraper — after the
    Spotify audio-features endpoint was confirmed 403 for this app,
    we pivoted to pulling features from Chartmetric's /api/track/{cm_id}
    response, which includes the same Spotify features inline.
    """
    from sqlalchemy import or_, text as sa_text
    from api.models.track import Track

    limit = max(1, min(limit, 1000))
    offset = max(0, offset)

    result = await db.execute(
        select(Track.id, Track.chartmetric_id, Track.title, Track.artist_id, Track.isrc)
        .where(
            Track.chartmetric_id.isnot(None),
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
                "chartmetric_id": r.chartmetric_id,
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


# ---------------------------------------------------------------------------
# Music generation providers — §24, §61
# ---------------------------------------------------------------------------

class MusicGenerateRequest(BaseModel):
    provider: str
    prompt: str
    duration_seconds: int = 30
    genre_hint: str | None = None
    tempo_bpm: float | None = None
    key_hint: str | None = None
    mood_tags: list[str] = []
    reference_audio_url: str | None = None
    seed: int | None = None
    model_variant: str | None = None


@router.get("/api/v1/admin/music/providers")
async def list_music_providers(_admin: ApiKey = Depends(require_admin)):
    """List every registered music-gen provider and whether it's live."""
    from api.services.music_providers import list_providers
    return {"providers": list_providers()}


@router.post("/api/v1/admin/music/generate")
async def music_generate(
    body: MusicGenerateRequest,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Submit a music generation request. Returns a task handle to poll."""
    from api.models.music_generation_call import MusicGenerationCall
    from api.services.music_providers import (
        GenerateParams,
        ProviderError,
        get_provider,
    )
    try:
        adapter = get_provider(body.provider)
    except KeyError as e:
        raise HTTPException(404, detail=str(e))

    params = GenerateParams(
        prompt=body.prompt,
        duration_seconds=body.duration_seconds,
        genre_hint=body.genre_hint,
        tempo_bpm=body.tempo_bpm,
        key_hint=body.key_hint,
        mood_tags=body.mood_tags,
        reference_audio_url=body.reference_audio_url,
        seed=body.seed,
        model_variant=body.model_variant,
    )
    try:
        task = await adapter.generate(params)
    except ProviderError as e:
        raise HTTPException(503, detail=str(e))
    except Exception as e:
        logger.exception("[music] %s generate failed", body.provider)
        raise HTTPException(502, detail=f"provider call failed: {e}")

    # Persist the call. A UNIQUE (provider, task_id) conflict means we
    # already logged this one — rare but possible on retry, so upsert.
    row = MusicGenerationCall(
        provider=task.provider,
        task_id=task.task_id,
        status="pending",
        prompt=body.prompt,
        params_json=task.params_echo,
        model_variant=body.model_variant,
        duration_seconds_requested=body.duration_seconds,
        genre_hint=body.genre_hint,
        estimated_cost_usd=task.estimated_cost_usd,
        submitted_at=task.submitted_at,
    )
    db.add(row)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("[music] failed to persist generation call %s", task.task_id)
        # Don't fail the request — the task is live at the provider even
        # if persistence is broken. Surface in logs and move on.

    return {
        "provider": task.provider,
        "task_id": task.task_id,
        "submitted_at": task.submitted_at.isoformat(),
        "estimated_cost_usd": task.estimated_cost_usd,
        "params_echo": task.params_echo,
    }


async def _download_and_persist_audio(
    db: AsyncSession, call_id, audio_url: str
) -> bool:
    """
    Download an audio file from a provider delivery URL and stash it in
    music_generation_audio. Idempotent — no-op if the row already exists.

    Returns True if bytes are now available (either freshly downloaded or
    already stored), False on failure.
    """
    from sqlalchemy import text as _text
    import httpx

    exists = await db.execute(
        _text("SELECT 1 FROM music_generation_audio WHERE music_generation_call_id = :cid"),
        {"cid": call_id},
    )
    if exists.scalar() is not None:
        return True

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(audio_url)
            if r.status_code != 200:
                logger.warning(
                    "[music] download failed %s: %s", r.status_code, audio_url[:120]
                )
                return False
            data = r.content
            content_type = r.headers.get("content-type", "audio/mpeg")
    except Exception:
        logger.exception("[music] download threw for %s", audio_url[:120])
        return False

    try:
        await db.execute(
            _text("""
                INSERT INTO music_generation_audio
                  (music_generation_call_id, content_type, size_bytes, mp3_bytes, source_url)
                VALUES (:cid, :ct, :sz, :bytes, :url)
                ON CONFLICT (music_generation_call_id) DO NOTHING
            """),
            {
                "cid": call_id,
                "ct": content_type,
                "sz": len(data),
                "bytes": data,
                "url": audio_url,
            },
        )
        await db.commit()
        logger.info("[music] persisted %d bytes for call %s", len(data), call_id)
        return True
    except Exception:
        await db.rollback()
        logger.exception("[music] insert failed for call %s", call_id)
        return False


def _audio_stream_url(request_base: str, provider: str, task_id: str) -> str:
    """URL the frontend should use to play a self-hosted generation."""
    return f"{request_base}/admin/music/audio/{provider}/{task_id}.mp3"


@router.get("/api/v1/admin/music/generate/{provider}/{task_id}")
async def music_poll(
    provider: str,
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Poll a generation task. Returns the latest status + audio URL on success."""
    from api.models.music_generation_call import MusicGenerationCall
    from api.services.music_providers import ProviderError, get_provider
    try:
        adapter = get_provider(provider)
    except KeyError as e:
        raise HTTPException(404, detail=str(e))

    try:
        result = await adapter.poll(task_id)
    except ProviderError as e:
        raise HTTPException(503, detail=str(e))
    except Exception as e:
        logger.exception("[music] %s poll failed for %s", provider, task_id)
        raise HTTPException(502, detail=f"provider poll failed: {e}")

    # Update the persisted row if it exists.
    row_result = await db.execute(
        select(MusicGenerationCall).where(
            MusicGenerationCall.provider == provider,
            MusicGenerationCall.task_id == task_id,
        )
    )
    row = row_result.scalar_one_or_none()
    persisted_locally = False
    if row is not None:
        row.status = result.status.value
        if result.audio_url is not None:
            row.audio_url = result.audio_url
        if result.duration_seconds is not None:
            row.audio_duration_seconds = result.duration_seconds
        if result.actual_cost_usd is not None:
            row.actual_cost_usd = result.actual_cost_usd
        if result.error:
            row.error_message = result.error
        row.raw_response = result.raw_payload
        if result.status.value in ("succeeded", "failed") and row.completed_at is None:
            row.completed_at = datetime.now(timezone.utc)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("[music] failed to update persisted call %s", task_id)

        # Self-host the audio on first terminal success so we survive
        # the provider's data_removed window.
        if result.status.value == "succeeded" and result.audio_url:
            persisted_locally = await _download_and_persist_audio(
                db, row.id, result.audio_url
            )
            # If this call is linked to a song (T-160 orchestrator), flip
            # songs_master.status draft → qa_pending and create the
            # audio_assets row pointing at the self-hosted stream URL.
            # Pass the full result so we can harvest lyrics/title/cover
            # from rich-metadata providers (Udio).
            if persisted_locally and row.song_id is not None:
                await _materialize_song_audio(db, row, provider, task_id, result=result)

    # Prefer the self-hosted URL when bytes are available.
    response_audio_url = result.audio_url
    if persisted_locally or (row is not None and await _has_stored_audio(db, row.id)):
        response_audio_url = f"/api/v1/admin/music/audio/{provider}/{task_id}.mp3"

    return {
        "provider": result.provider,
        "task_id": result.task_id,
        "status": result.status.value,
        "audio_url": response_audio_url,
        "duration_seconds": result.duration_seconds,
        "error": result.error,
        "actual_cost_usd": result.actual_cost_usd,
    }


async def _materialize_song_audio(
    db: AsyncSession, call_row, provider: str, task_id: str,
    result=None,  # optional GenerationResult with clips list + metadata
) -> None:
    """
    Post-success bookkeeping for a T-160 generation.

    If `result.clips` is populated (Udio returns 2, Suno may return 2):
      - Creates ONE audio_assets row for the master candidate (clip 0)
      - Extracts lyrics + title from clip 0 into songs_master
      - Uses clip 0's image_url as the cover if present

    Otherwise falls back to the single-clip path (MusicGen).

    Flips songs_master.status from 'draft' to 'qa_pending'. Idempotent.
    """
    from sqlalchemy import text as _text
    exists = await db.execute(
        _text("SELECT 1 FROM audio_assets WHERE music_generation_call_id = :cid"),
        {"cid": call_row.id},
    )
    if exists.scalar() is not None:
        return

    stream_url = f"/api/v1/admin/music/audio/{provider}/{task_id}.mp3"
    await db.execute(
        _text("""
            INSERT INTO audio_assets (
                song_id, provider, provider_job_id, music_generation_call_id,
                format, duration_seconds, storage_url, storage_backend,
                is_master_candidate
            ) VALUES (
                :song_id, :provider, :job_id, :cid,
                'mp3', :dur, :url, 'neon_bytea', TRUE
            )
        """),
        {
            "song_id": call_row.song_id,
            "provider": provider,
            "job_id": task_id,
            "cid": call_row.id,
            "dur": call_row.audio_duration_seconds,
            "url": stream_url,
        },
    )

    # Rich-metadata providers (Udio): harvest clip 0's title/lyrics/cover
    # into the linked songs_master row.
    rich_updates: dict[str, object] = {}
    if result is not None and result.clips:
        master_clip = result.clips[0]
        if master_clip.lyrics:
            rich_updates["lyric_text"] = master_clip.lyrics
        if master_clip.title:
            rich_updates["title"] = master_clip.title
        if master_clip.tags:
            rich_updates["mood_tags"] = master_clip.tags[:10]

        # If the provider gave us a cover image, download + persist it
        # as an artist_visual_asset linked to songs_master.primary_artwork_asset_id.
        if master_clip.image_url:
            provider_cover = await _download_and_persist_provider_cover(
                db,
                song_id=call_row.song_id,
                provider=provider,
                image_url=master_clip.image_url,
            )
            if provider_cover:
                rich_updates["primary_artwork_asset_id"] = provider_cover

    # Build UPDATE clause
    set_parts = ["status = 'qa_pending'", "updated_at = NOW()"]
    params: dict[str, object] = {"sid": call_row.song_id}
    for k, v in rich_updates.items():
        set_parts.append(f"{k} = :{k}")
        params[k] = v
    update_sql = (
        f"UPDATE songs_master SET {', '.join(set_parts)} "
        f"WHERE song_id = :sid AND status IN ('draft', 'qa_pending')"
    )
    await db.execute(_text(update_sql), params)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("[orchestrator] materialize failed for call %s", call_row.id)


async def _download_and_persist_provider_cover(
    db: AsyncSession,
    *,
    song_id,
    provider: str,
    image_url: str,
):
    """
    Download a provider-furnished cover image (Udio gives us one per clip)
    and store it in the same visual_asset_blobs sidecar that DALL-E covers
    use. Returns the new asset_id, or None on failure.
    """
    import uuid as _uuid
    import httpx
    from sqlalchemy import text as _text

    # Song needs an artist_id for artist_visual_assets.artist_id FK
    art_row = (await db.execute(
        _text("SELECT primary_artist_id FROM songs_master WHERE song_id = :sid"),
        {"sid": song_id},
    )).fetchone()
    if not art_row:
        return None
    artist_id = art_row[0]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(image_url)
            if r.status_code != 200:
                logger.warning("[cover-download] %s returned %s", image_url[:80], r.status_code)
                return None
            image_bytes = r.content
            content_type = r.headers.get("content-type", "image/jpeg")
    except Exception:
        logger.exception("[cover-download] fetch failed for %s", image_url[:80])
        return None

    asset_id = _uuid.uuid4()
    await db.execute(
        _text("""
            INSERT INTO artist_visual_assets (
                asset_id, artist_id, asset_type, storage_url,
                generation_provider, source_prompt, is_canonical_sheet
            ) VALUES (
                :asset_id, :artist_id, 'song_artwork', :storage_url,
                :provider, :prompt, FALSE
            )
        """),
        {
            "asset_id": asset_id,
            "artist_id": artist_id,
            "storage_url": f"/api/v1/admin/visual/{asset_id}.png",
            "provider": f"{provider}_provider",
            "prompt": f"Provider-supplied cover from {provider}",
        },
    )
    await db.execute(
        _text("""
            INSERT INTO visual_asset_blobs
              (asset_id, content_type, size_bytes, image_bytes, source_url)
            VALUES (:asset_id, :ct, :sz, :bytes, :url)
        """),
        {
            "asset_id": asset_id,
            "ct": content_type,
            "sz": len(image_bytes),
            "bytes": image_bytes,
            "url": image_url,
        },
    )
    logger.info(
        "[cover-download] persisted %d bytes for song %s (provider %s)",
        len(image_bytes), str(song_id)[:8], provider,
    )
    return asset_id


async def _has_stored_audio(db: AsyncSession, call_id) -> bool:
    from sqlalchemy import text as _text
    r = await db.execute(
        _text("SELECT 1 FROM music_generation_audio WHERE music_generation_call_id = :cid"),
        {"cid": call_id},
    )
    return r.scalar() is not None


@router.get("/api/v1/admin/visual/{asset_id}.png")
async def visual_asset_stream(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Stream a self-hosted visual asset (artist portrait, song cover) by
    asset_id. Open endpoint — HTML5 <img> can load it directly. Cached
    aggressively since the bytes never change.
    """
    import uuid as _uuid
    from fastapi.responses import Response
    from sqlalchemy import text as _text

    try:
        aid = _uuid.UUID(asset_id)
    except ValueError:
        raise HTTPException(400, detail="invalid asset_id")

    r = await db.execute(
        _text("""
            SELECT image_bytes, content_type, size_bytes
            FROM visual_asset_blobs
            WHERE asset_id = :aid
            LIMIT 1
        """),
        {"aid": aid},
    )
    row = r.fetchone()
    if row is None:
        raise HTTPException(404, detail="image not found")

    return Response(
        content=bytes(row[0]),
        media_type=row[1] or "image/png",
        headers={
            "Content-Length": str(row[2]),
            "Cache-Control": "public, max-age=31536000, immutable",
        },
    )


@router.get("/api/v1/admin/music/audio/{provider}/{task_id}.mp3")
async def music_audio_stream(
    provider: str,
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Stream a self-hosted generation by provider + task_id. Open endpoint
    (no X-API-Key) so HTML5 <audio> can load it without custom headers.
    Cache aggressively — the bytes never change.
    """
    from fastapi.responses import Response
    from sqlalchemy import text as _text

    r = await db.execute(
        _text("""
            SELECT a.mp3_bytes, a.content_type, a.size_bytes
            FROM music_generation_audio a
            JOIN music_generation_calls c ON c.id = a.music_generation_call_id
            WHERE c.provider = :provider AND c.task_id = :task_id
            LIMIT 1
        """),
        {"provider": provider, "task_id": task_id},
    )
    row = r.fetchone()
    if row is None:
        raise HTTPException(404, detail="audio not found")

    return Response(
        content=bytes(row[0]),
        media_type=row[1] or "audio/mpeg",
        headers={
            "Content-Length": str(row[2]),
            "Cache-Control": "public, max-age=31536000, immutable",
            "Accept-Ranges": "bytes",
        },
    )


@router.get("/api/v1/admin/music/generations")
async def list_music_generations(
    limit: int = 50,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """List recent music generation calls, newest first."""
    from sqlalchemy import text as _text
    from api.models.music_generation_call import MusicGenerationCall
    stmt = select(MusicGenerationCall).order_by(
        MusicGenerationCall.submitted_at.desc()
    ).limit(min(limit, 200))
    if status:
        stmt = stmt.where(MusicGenerationCall.status == status)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    # One round trip to find which rows have self-hosted bytes, so each
    # card can render the durable URL instead of a maybe-expired provider URL.
    row_ids = [row.id for row in rows]
    stored_set: set = set()
    if row_ids:
        r = await db.execute(
            _text("SELECT music_generation_call_id FROM music_generation_audio WHERE music_generation_call_id = ANY(:ids)"),
            {"ids": row_ids},
        )
        stored_set = {x[0] for x in r.fetchall()}

    def _resolve_url(row):
        if row.id in stored_set:
            return f"/api/v1/admin/music/audio/{row.provider}/{row.task_id}.mp3"
        return row.audio_url  # may be expired, frontend shows an "expired" badge

    return {
        "generations": [
            {
                "id": str(row.id),
                "provider": row.provider,
                "task_id": row.task_id,
                "status": row.status,
                "prompt": row.prompt,
                "genre_hint": row.genre_hint,
                "duration_seconds_requested": row.duration_seconds_requested,
                "audio_url": _resolve_url(row),
                "audio_self_hosted": row.id in stored_set,
                "audio_duration_seconds": row.audio_duration_seconds,
                "estimated_cost_usd": row.estimated_cost_usd,
                "actual_cost_usd": row.actual_cost_usd,
                "error_message": row.error_message,
                "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            }
            for row in rows
        ],
        "count": len(rows),
    }


# ---------------------------------------------------------------------------
# Artist spine — §18-23 (blueprints, ai_artists, assignment, CEO gate)
# ---------------------------------------------------------------------------

class BlueprintFromOpportunityRequest(BaseModel):
    genre_id: str
    primary_genre: str | None = None
    adjacent_genres: list[str] = []
    target_themes: list[str] = []
    vocabulary_tone: str | None = None
    target_audience_tags: list[str] = []
    voice_requirements: dict | None = None
    target_tempo: float | None = None
    target_key: int | None = None
    target_mode: int | None = None
    target_energy: float | None = None
    smart_prompt_text: str
    smart_prompt_rationale: dict | None = None
    predicted_success_score: float | None = None
    quantification_snapshot: dict | None = None
    breakout_event_ids: list[str] = []


class AIArtistCreateRequest(BaseModel):
    stage_name: str
    legal_name: str
    primary_genre: str
    adjacent_genres: list[str] = []
    voice_dna: dict
    visual_dna: dict
    lyrical_dna: dict | None = None
    persona_dna: dict | None = None
    social_dna: dict | None = None
    audience_tags: list[str] = []
    influences: list[str] = []
    content_rating: str = "mild"


@router.post("/api/v1/admin/blueprints")
async def create_blueprint(
    body: BlueprintFromOpportunityRequest,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Persist a blueprint produced by the breakout + smart-prompt pipeline."""
    import uuid as _uuid
    from api.models.song_blueprint import SongBlueprint

    row = SongBlueprint(
        genre_id=body.genre_id,
        primary_genre=body.primary_genre or body.genre_id,
        adjacent_genres=body.adjacent_genres or None,
        target_themes=body.target_themes or None,
        vocabulary_tone=body.vocabulary_tone,
        target_audience_tags=body.target_audience_tags or None,
        voice_requirements=body.voice_requirements,
        target_tempo=body.target_tempo,
        target_key=body.target_key,
        target_mode=body.target_mode,
        target_energy=body.target_energy,
        smart_prompt_text=body.smart_prompt_text,
        smart_prompt_rationale=body.smart_prompt_rationale,
        predicted_success_score=body.predicted_success_score,
        quantification_snapshot=body.quantification_snapshot,
        breakout_event_ids=[_uuid.UUID(x) for x in body.breakout_event_ids] or None,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {
        "id": str(row.id),
        "genre_id": row.genre_id,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
    }


@router.get("/api/v1/admin/blueprints")
async def list_blueprints(
    limit: int = 50,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    from api.models.song_blueprint import SongBlueprint
    stmt = select(SongBlueprint).order_by(SongBlueprint.created_at.desc()).limit(min(limit, 200))
    if status:
        stmt = stmt.where(SongBlueprint.status == status)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {
        "blueprints": [
            {
                "id": str(r.id),
                "genre_id": r.genre_id,
                "primary_genre": r.primary_genre,
                "status": r.status,
                "assigned_artist_id": str(r.assigned_artist_id) if r.assigned_artist_id else None,
                "target_themes": r.target_themes,
                "target_audience_tags": r.target_audience_tags,
                "predicted_success_score": r.predicted_success_score,
                "smart_prompt_text": r.smart_prompt_text,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.post("/api/v1/admin/artists")
async def create_ai_artist(
    body: AIArtistCreateRequest,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Manually create an AI artist. Full persona pipeline lands later."""
    from api.models.ai_artist import AIArtist
    row = AIArtist(
        stage_name=body.stage_name,
        legal_name=body.legal_name,
        primary_genre=body.primary_genre,
        adjacent_genres=body.adjacent_genres or None,
        voice_dna=body.voice_dna,
        visual_dna=body.visual_dna,
        lyrical_dna=body.lyrical_dna,
        persona_dna=body.persona_dna,
        social_dna=body.social_dna,
        audience_tags=body.audience_tags or None,
        influences=body.influences or None,
        content_rating=body.content_rating,
    )
    db.add(row)
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(409, detail=f"artist creation failed: {e}")
    await db.refresh(row)
    return {
        "artist_id": str(row.artist_id),
        "stage_name": row.stage_name,
        "primary_genre": row.primary_genre,
        "roster_status": row.roster_status,
        "created_at": row.created_at.isoformat(),
    }


class ArtistFromDescriptionRequest(BaseModel):
    description: str
    target_genre: str
    content_rating: str = "mild"
    auto_approve: bool = False  # skip CEO gate for testing; default keeps gate


class ArtistPreviewRequest(BaseModel):
    description: str
    target_genre: str


class ArtistCreateFromPersonaRequest(BaseModel):
    persona: dict            # the persona dict from /preview-persona
    chosen_stage_name: str   # which of the 5 alternatives to use
    target_genre: str        # echo of target_genre for the authoritative field
    content_rating: str = "mild"
    auto_approve: bool = False


@router.post("/api/v1/admin/artists/preview-persona")
async def preview_persona(
    body: ArtistPreviewRequest,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Generate a persona preview WITHOUT creating a DB row. Returns the
    full persona JSON including 5 stage_name_alternatives + the set of
    real reference artists from the Chartmetric-scraped roster that
    grounded the LLM output. CEO reviews, picks one stage name, then
    calls POST /admin/artists/create-from-persona to finalize.

    No portrait is generated here — portraits happen at create-from-persona
    time once the name is locked in.
    """
    from sqlalchemy import text as _text
    from api.services.persona_blender import blend_persona
    from api.services.reference_artist_lookup import (
        format_references_for_prompt,
        get_top_reference_artists,
    )

    existing_names_result = await db.execute(
        _text("SELECT stage_name FROM ai_artists WHERE roster_status = 'active'")
    )
    existing_names = [r[0] for r in existing_names_result.fetchall() if r[0]]

    references = await get_top_reference_artists(
        db, target_genre=body.target_genre, limit=5,
    )
    reference_block = format_references_for_prompt(references) if references else None
    reference_names = [r.name for r in references]

    try:
        persona = await blend_persona(
            db=db,
            description=body.description,
            target_genre=body.target_genre,
            caller="admin.preview_persona",
            avoid_stage_names=existing_names,
            reference_artists_block=reference_block,
            reference_artist_names=reference_names,
        )
    except ValueError as e:
        raise HTTPException(502, detail=f"persona generation failed: {e}")
    except Exception as e:
        logger.exception("[persona_blender] unexpected failure")
        raise HTTPException(502, detail=f"persona generation failed: {e}")

    return {
        "persona": persona,
        "stage_name_alternatives": persona.get("stage_name_alternatives") or [persona["stage_name"]],
        "default_choice": persona["stage_name"],
        "references_used": [
            {"name": r.name, "genres": r.genres, "momentum": r.recent_trending_count}
            for r in references
        ],
        "target_genre": body.target_genre,
    }


@router.post("/api/v1/admin/artists/create-from-persona")
async def create_artist_from_persona(
    body: ArtistCreateFromPersonaRequest,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Finalize an artist from a previewed persona. The CEO has picked
    one of the 5 stage_name_alternatives. We:
      1. Persist the ai_artists row with the chosen name
      2. Generate the portrait via gpt-image-1 high-quality
      3. Return the created row + portrait info
    """
    from sqlalchemy import text as _text
    from api.models.ai_artist import AIArtist
    from api.services.image_generator import (
        build_artist_portrait_prompt,
        generate_and_store_image,
    )

    persona = body.persona
    # Allow the CEO's pick to override whatever was in persona.stage_name
    chosen = body.chosen_stage_name.strip()
    if not chosen:
        raise HTTPException(400, detail="chosen_stage_name is required")
    alternatives = persona.get("stage_name_alternatives") or []
    if chosen not in alternatives and chosen != persona.get("stage_name"):
        # Allow free-text override but log — CEO can rename entirely
        logger.info("[create-from-persona] CEO picked custom name '%s' not in alternatives", chosen)

    row = AIArtist(
        stage_name=chosen,
        legal_name=persona.get("legal_name") or chosen,
        primary_genre=body.target_genre,
        adjacent_genres=persona.get("adjacent_genres") or None,
        influences=persona.get("influences") or None,
        anti_influences=persona.get("anti_influences") or None,
        age=persona.get("age"),
        gender_presentation=persona.get("gender_presentation"),
        ethnicity_heritage=persona.get("ethnicity_heritage"),
        edge_profile=persona.get("edge_profile"),
        voice_dna=persona["voice_dna"],
        visual_dna=persona["visual_dna"],
        fashion_dna=persona.get("fashion_dna"),
        lyrical_dna=persona.get("lyrical_dna"),
        persona_dna=persona.get("persona_dna"),
        social_dna=persona.get("social_dna"),
        audience_tags=persona.get("audience_tags") or None,
        content_rating=persona.get("content_rating") or body.content_rating,
        ceo_approved=body.auto_approve,
    )
    db.add(row)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        import random as _random, string as _string
        suffix = ''.join(_random.choices(_string.ascii_uppercase + _string.digits, k=4))
        row.stage_name = f"{chosen} {suffix}"
        row.legal_name = f"{row.legal_name} {suffix}"
        db.add(row)
        try:
            await db.commit()
        except Exception as e2:
            await db.rollback()
            raise HTTPException(409, detail=f"artist creation failed after retry: {e2}")
    await db.refresh(row)

    # Generate + store portrait (single view — user can click
    # "Generate 8-view sheet" separately if they want the full PRD §20)
    portrait_prompt = build_artist_portrait_prompt(persona, primary_genre=body.target_genre)
    portrait_error: str | None = None
    portrait = None
    try:
        portrait = await generate_and_store_image(
            db,
            artist_id=row.artist_id,
            asset_type="reference_sheet",
            prompt=portrait_prompt,
            quality="high",
        )
        if portrait is None:
            portrait_error = (
                "image_generator returned None — likely OpenAI API error, "
                "content-policy rejection, or misconfigured env. Check logs "
                "and call POST /admin/artists/{id}/regenerate-portrait to retry."
            )
            logger.warning("[create-from-persona] portrait None for %s", row.stage_name)
    except Exception as e:
        portrait_error = f"portrait gen raised: {type(e).__name__}: {e}"
        logger.exception("[create-from-persona] portrait raised for %s", row.stage_name)

    portrait_info = None
    if portrait is not None:
        updated_visual = dict(row.visual_dna or {})
        updated_visual["reference_sheet_asset_id"] = str(portrait.asset_id)
        await db.execute(
            _text(
                "UPDATE ai_artists SET visual_dna = CAST(:vdna AS jsonb), updated_at = NOW() "
                "WHERE artist_id = :aid"
            ),
            {"vdna": json.dumps(updated_visual), "aid": row.artist_id},
        )
        await db.commit()
        portrait_info = {
            "asset_id": str(portrait.asset_id),
            "storage_url": portrait.storage_url,
            "provider": portrait.provider,
            "bytes": portrait.bytes_len,
        }

    return {
        "artist_id": str(row.artist_id),
        "stage_name": row.stage_name,
        "primary_genre": row.primary_genre,
        "portrait": portrait_info,
        "portrait_error": portrait_error,
        "derived_from": persona.get("derived_from"),
        "created_at": row.created_at.isoformat(),
    }


@router.post("/api/v1/admin/artists/from-description")
async def create_artist_from_description(
    body: ArtistFromDescriptionRequest,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    T-127-lite: LLM-driven artist creation shortcut.

    Takes a natural-language description + target genre and produces a
    full ai_artists row via Groq. Bypasses the §18-19 reference-artist
    scraping pipeline until that's built.
    """
    from api.models.ai_artist import AIArtist
    from api.services.persona_blender import blend_persona

    # Pull existing stage names so the LLM doesn't re-pick one
    from sqlalchemy import text as _text
    existing_names_result = await db.execute(
        _text("SELECT stage_name FROM ai_artists WHERE roster_status = 'active'")
    )
    existing_names = [r[0] for r in existing_names_result.fetchall() if r[0]]

    # Pull real reference artists from the Chartmetric-scraped `artists`
    # table so the LLM grounds the persona in actual current-momentum
    # data vs pre-training confabulation.
    from api.services.reference_artist_lookup import (
        format_references_for_prompt,
        get_top_reference_artists,
    )
    references = await get_top_reference_artists(
        db, target_genre=body.target_genre, limit=5,
    )
    reference_block = format_references_for_prompt(references) if references else None
    reference_names = [r.name for r in references]

    try:
        persona = await blend_persona(
            db=db,
            description=body.description,
            target_genre=body.target_genre,
            caller="admin.from_description",
            avoid_stage_names=existing_names,
            reference_artists_block=reference_block,
            reference_artist_names=reference_names,
        )
    except ValueError as e:
        raise HTTPException(502, detail=f"persona generation failed: {e}")
    except Exception as e:
        logger.exception("[persona_blender] unexpected failure")
        raise HTTPException(502, detail=f"persona generation failed: {e}")

    row = AIArtist(
        stage_name=persona.get("stage_name"),
        legal_name=persona.get("legal_name") or persona.get("stage_name"),
        # The caller's target_genre is authoritative — the LLM tends to
        # simplify ugly genre ids (e.g. "pop__e2e_abc123" -> "pop") which
        # breaks the assignment engine's exact-match score.
        primary_genre=body.target_genre,
        adjacent_genres=persona.get("adjacent_genres") or None,
        influences=persona.get("influences") or None,
        anti_influences=persona.get("anti_influences") or None,
        age=persona.get("age"),
        gender_presentation=persona.get("gender_presentation"),
        ethnicity_heritage=persona.get("ethnicity_heritage"),
        edge_profile=persona.get("edge_profile"),
        voice_dna=persona["voice_dna"],
        visual_dna=persona["visual_dna"],
        fashion_dna=persona.get("fashion_dna"),
        lyrical_dna=persona.get("lyrical_dna"),
        persona_dna=persona.get("persona_dna"),
        social_dna=persona.get("social_dna"),
        audience_tags=persona.get("audience_tags") or None,
        content_rating=persona.get("content_rating") or body.content_rating,
        ceo_approved=body.auto_approve,
    )
    db.add(row)
    try:
        await db.commit()
    except Exception:
        # Stage name collision — last-ditch retry with a short random
        # suffix. The LLM saw the avoid list but occasionally still picks
        # a collision because its output is non-deterministic.
        await db.rollback()
        import random as _random, string as _string
        suffix = ''.join(_random.choices(_string.ascii_uppercase + _string.digits, k=4))
        row.stage_name = f"{row.stage_name} {suffix}"
        row.legal_name = f"{row.legal_name} {suffix}"
        db.add(row)
        try:
            await db.commit()
        except Exception as e2:
            await db.rollback()
            raise HTTPException(409, detail=f"artist creation failed after retry: {e2}")
    await db.refresh(row)

    # Generate + store a portrait via openai_cli_proxy (or OpenAI direct fallback)
    from sqlalchemy import text as _text
    from api.services.image_generator import (
        build_artist_portrait_prompt,
        generate_and_store_image,
    )
    portrait_prompt = build_artist_portrait_prompt(persona, primary_genre=body.target_genre)
    portrait = await generate_and_store_image(
        db,
        artist_id=row.artist_id,
        asset_type="reference_sheet",
        prompt=portrait_prompt,
    )
    portrait_info = None
    if portrait is not None:
        # Stamp visual_dna.reference_sheet_asset_id on the artist row
        updated_visual = dict(row.visual_dna or {})
        updated_visual["reference_sheet_asset_id"] = str(portrait.asset_id)
        await db.execute(
            _text("""
                UPDATE ai_artists
                SET visual_dna = CAST(:vdna AS jsonb), updated_at = NOW()
                WHERE artist_id = :aid
            """),
            {"vdna": json.dumps(updated_visual), "aid": row.artist_id},
        )
        await db.commit()
        portrait_info = {
            "asset_id": str(portrait.asset_id),
            "storage_url": portrait.storage_url,
            "provider": portrait.provider,
            "bytes": portrait.bytes_len,
        }
    else:
        logger.warning("[artists] portrait generation skipped for %s", row.stage_name)

    return {
        "artist_id": str(row.artist_id),
        "stage_name": row.stage_name,
        "primary_genre": row.primary_genre,
        "roster_status": row.roster_status,
        "ceo_approved": row.ceo_approved,
        "persona": persona,
        "portrait": portrait_info,
        "derived_from": {
            "reference_artists": reference_names,
            "reference_count": len(references),
        },
        "created_at": row.created_at.isoformat(),
    }


@router.post("/api/v1/admin/artists/{artist_id}/generate-reference-sheet")
async def generate_reference_sheet(
    artist_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    PRD §20 — 8-view photographic reference sheet with FACE-LOCKED
    consistency via gpt-image-1's /v1/images/edits endpoint.

    Flow:
      1. Generate the FRONT view via text-to-image (/v1/images/generations)
      2. Load its bytes from visual_asset_blobs
      3. Generate views 2-8 via reference-to-image (/v1/images/edits)
         passing the front view's PNG as the reference — gpt-image-1
         locks the face/hair/clothing across all 7 subsequent views.

    Cost: ~$0.167 × 1 (front, high quality) + $0.042 × 7 (edits, medium) ≈ $0.46 per sheet
    """
    import uuid as _uuid
    from sqlalchemy import text as _text
    from api.models.ai_artist import AIArtist
    from api.services.image_generator import (
        build_8_view_prompts,
        composite_8_view_sheet,
        generate_and_store_image,
    )

    try:
        aid = _uuid.UUID(artist_id)
    except ValueError:
        raise HTTPException(400, detail="invalid artist_id")

    artist = (await db.execute(
        select(AIArtist).where(AIArtist.artist_id == aid)
    )).scalar_one_or_none()
    if artist is None:
        raise HTTPException(404, detail="artist not found")

    persona = {
        "age": artist.age,
        "gender_presentation": artist.gender_presentation,
        "ethnicity_heritage": artist.ethnicity_heritage,
        "visual_dna": artist.visual_dna or {},
        "fashion_dna": artist.fashion_dna or {},
    }
    view_prompts = build_8_view_prompts(persona, primary_genre=artist.primary_genre)

    results: list[dict] = []
    front_asset_id: _uuid.UUID | None = None
    front_bytes: bytes | None = None
    # Collect every view's bytes so we can composite at the end
    view_bytes_by_angle: dict[str, bytes] = {}

    for view_angle, prompt in view_prompts:
        # Front view: high-quality text-to-image.
        # Other views: reference-conditioned to the front view bytes.
        if view_angle == "front":
            portrait = await generate_and_store_image(
                db,
                artist_id=aid,
                asset_type="sheet_view",
                prompt=prompt,
                view_angle=view_angle,
                quality="high",
            )
        else:
            if front_bytes is None:
                logger.warning("[sheet-gen] %s skipped — no front bytes yet", view_angle)
                results.append({
                    "view_angle": view_angle,
                    "asset_id": None,
                    "error": "front view bytes missing",
                })
                continue
            portrait = await generate_and_store_image(
                db,
                artist_id=aid,
                asset_type="sheet_view",
                prompt=prompt,
                view_angle=view_angle,
                parent_sheet_id=front_asset_id,
                quality="medium",
                reference_image_bytes=front_bytes,
            )

        if portrait is None:
            logger.warning("[sheet-gen] %s view failed for %s", view_angle, artist.stage_name)
            results.append({
                "view_angle": view_angle,
                "asset_id": None,
                "error": "generation returned None",
            })
            continue

        # Pull the freshly-persisted bytes back for:
        # 1. front view → passed as reference to the 7 follow-up calls
        # 2. every view → collected for the final composite sheet
        blob_row = await db.execute(
            _text("SELECT image_bytes FROM visual_asset_blobs WHERE asset_id = :aid"),
            {"aid": portrait.asset_id},
        )
        blob = blob_row.fetchone()
        if blob:
            view_bytes_by_angle[view_angle] = bytes(blob[0])
            if view_angle == "front":
                front_bytes = bytes(blob[0])

        if view_angle == "front":
            front_asset_id = portrait.asset_id
            # Individual 'front' row stays as a sheet_view child —
            # the canonical reference_sheet row will be the composite,
            # created below after all 8 views land.

        results.append({
            "view_angle": view_angle,
            "asset_id": str(portrait.asset_id),
            "storage_url": portrait.storage_url,
            "bytes": portrait.bytes_len,
        })

    # --- Composite the 8 views into ONE PNG per PRD §20 step 4 --------
    composite_asset_id: _uuid.UUID | None = None
    if len(view_bytes_by_angle) >= 4:  # need at least half the views
        composite_bytes = composite_8_view_sheet(view_bytes_by_angle)
        if composite_bytes:
            composite_asset_id = _uuid.uuid4()
            await db.execute(
                _text("""
                    INSERT INTO artist_visual_assets (
                        asset_id, artist_id, asset_type, view_angle,
                        storage_url, generation_provider, source_prompt,
                        is_canonical_sheet
                    ) VALUES (
                        :asset_id, :artist_id, 'reference_sheet', 'composite',
                        :storage_url, :provider, :prompt, TRUE
                    )
                """),
                {
                    "asset_id": composite_asset_id,
                    "artist_id": aid,
                    "storage_url": f"/api/v1/admin/visual/{composite_asset_id}.png",
                    "provider": "pil_composite",
                    "prompt": f"8-view composite from {len(view_bytes_by_angle)} gpt-image-1 views",
                },
            )
            await db.execute(
                _text("""
                    INSERT INTO visual_asset_blobs
                      (asset_id, content_type, size_bytes, image_bytes)
                    VALUES (:asset_id, 'image/png', :sz, :bytes)
                """),
                {
                    "asset_id": composite_asset_id,
                    "sz": len(composite_bytes),
                    "bytes": composite_bytes,
                },
            )

    # Stamp visual_dna.reference_sheet_asset_id → composite (or front if no composite)
    canonical_id = composite_asset_id or front_asset_id
    if canonical_id is not None:
        updated_visual = dict(artist.visual_dna or {})
        updated_visual["reference_sheet_asset_id"] = str(canonical_id)
        updated_visual["reference_sheet_is_composite"] = composite_asset_id is not None
        await db.execute(
            _text("UPDATE ai_artists SET visual_dna = CAST(:vdna AS jsonb), updated_at = NOW() WHERE artist_id = :aid"),
            {"vdna": json.dumps(updated_visual), "aid": aid},
        )

    await db.commit()

    # Cost: front (high) ≈ $0.167 + 7 × edits (medium) ≈ $0.042 = $0.461
    successful = [r for r in results if r.get("asset_id")]
    approx_cost = (0.167 if any(r["view_angle"] == "front" for r in successful) else 0) + \
                  0.042 * sum(1 for r in successful if r["view_angle"] != "front")

    return {
        "artist_id": str(aid),
        "stage_name": artist.stage_name,
        "views": results,
        "front_asset_id": str(front_asset_id) if front_asset_id else None,
        "composite_asset_id": str(composite_asset_id) if composite_asset_id else None,
        "composite_storage_url": (
            f"/api/v1/admin/visual/{composite_asset_id}.png"
            if composite_asset_id else None
        ),
        "total_cost_usd": round(approx_cost, 3),
        "model": "gpt-image-1",
        "face_locked": front_bytes is not None,
    }


@router.get("/api/v1/admin/artists/{artist_id}/reference-sheet")
async def get_artist_reference_sheet(
    artist_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Return every artist_visual_assets row for this artist that belongs
    to a reference sheet (asset_type in reference_sheet | sheet_view),
    ordered by view_angle. The UI uses this to render the 8-view grid.
    """
    import uuid as _uuid
    from sqlalchemy import text as _text
    try:
        aid = _uuid.UUID(artist_id)
    except ValueError:
        raise HTTPException(400, detail="invalid artist_id")

    # Canonical order for the 8 views
    VIEW_ORDER = [
        "front", "side_l", "side_r", "back",
        "top_l", "top_r", "bottom_l", "bottom_r",
    ]

    r = await db.execute(
        _text("""
            SELECT asset_id, view_angle, storage_url, is_canonical_sheet, created_at
            FROM artist_visual_assets
            WHERE artist_id = :aid
              AND asset_type IN ('reference_sheet', 'sheet_view')
            ORDER BY created_at DESC
        """),
        {"aid": aid},
    )
    rows = r.fetchall()

    # Group by view_angle, keeping the newest per angle
    latest_by_angle: dict = {}
    for row in rows:
        angle = row[1] or "front"
        if angle not in latest_by_angle:
            latest_by_angle[angle] = {
                "asset_id": str(row[0]),
                "view_angle": angle,
                "storage_url": row[2],
                "is_canonical_sheet": row[3],
                "created_at": row[4].isoformat() if row[4] else None,
            }

    ordered = []
    for angle in VIEW_ORDER:
        if angle in latest_by_angle:
            ordered.append(latest_by_angle[angle])

    return {
        "artist_id": str(aid),
        "views": ordered,
        "count": len(ordered),
    }


@router.post("/api/v1/admin/artists/{artist_id}/regenerate-portrait")
async def regenerate_artist_portrait(
    artist_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Re-run portrait generation for an existing artist using the current
    image_generator prompt logic. Used after photorealism improvements
    to refresh existing artists without re-doing the persona blend.
    """
    import uuid as _uuid
    from sqlalchemy import text as _text
    from api.models.ai_artist import AIArtist
    from api.services.image_generator import (
        build_artist_portrait_prompt,
        generate_and_store_image,
    )

    try:
        aid = _uuid.UUID(artist_id)
    except ValueError:
        raise HTTPException(400, detail="invalid artist_id")

    artist = (await db.execute(
        select(AIArtist).where(AIArtist.artist_id == aid)
    )).scalar_one_or_none()
    if artist is None:
        raise HTTPException(404, detail="artist not found")

    # Rebuild persona dict from the artist's columns
    persona = {
        "age": artist.age,
        "gender_presentation": artist.gender_presentation,
        "ethnicity_heritage": artist.ethnicity_heritage,
        "visual_dna": artist.visual_dna or {},
        "fashion_dna": artist.fashion_dna or {},
    }
    prompt = build_artist_portrait_prompt(persona, primary_genre=artist.primary_genre)
    portrait = await generate_and_store_image(
        db,
        artist_id=aid,
        asset_type="reference_sheet",
        prompt=prompt,
    )
    if portrait is None:
        raise HTTPException(
            502,
            detail="portrait generation returned None — check OPENAI_API_KEY env and logs",
        )

    # Update visual_dna.reference_sheet_asset_id on the artist
    updated_visual = dict(artist.visual_dna or {})
    updated_visual["reference_sheet_asset_id"] = str(portrait.asset_id)
    await db.execute(
        _text("UPDATE ai_artists SET visual_dna = CAST(:vdna AS jsonb), updated_at = NOW() WHERE artist_id = :aid"),
        {"vdna": json.dumps(updated_visual), "aid": aid},
    )
    await db.commit()

    return {
        "artist_id": str(aid),
        "stage_name": artist.stage_name,
        "portrait": {
            "asset_id": str(portrait.asset_id),
            "storage_url": portrait.storage_url,
            "provider": portrait.provider,
            "bytes": portrait.bytes_len,
        },
        "prompt": prompt[:500],
    }


@router.get("/api/v1/admin/artists")
async def list_ai_artists(
    roster_status: str = "active",
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    from api.models.ai_artist import AIArtist
    from sqlalchemy import text as _text
    stmt = select(AIArtist).where(AIArtist.roster_status == roster_status).order_by(
        AIArtist.created_at.desc()
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    # Denormalized ai_artists.song_count is historically unmaintained —
    # the PRD called for a post-insert trigger that was never created,
    # so the column drifts to stale 0s. Compute live counts from
    # songs_master so the Artists page is always accurate regardless of
    # counter state. One aggregate query covers the whole roster.
    live_counts: dict[str, int] = {}
    if rows:
        count_rows = (await db.execute(
            _text("""
                SELECT primary_artist_id::text, COUNT(*)
                FROM songs_master
                WHERE status NOT IN ('draft','abandoned')
                  AND primary_artist_id = ANY(:ids::uuid[])
                GROUP BY primary_artist_id
            """),
            {"ids": [str(r.artist_id) for r in rows]},
        )).fetchall()
        live_counts = {cr[0]: int(cr[1]) for cr in count_rows}

    return {
        "artists": [
            {
                "artist_id": str(r.artist_id),
                "stage_name": r.stage_name,
                "legal_name": r.legal_name,
                "primary_genre": r.primary_genre,
                "adjacent_genres": r.adjacent_genres,
                "influences": r.influences,
                "anti_influences": r.anti_influences,
                "song_count": live_counts.get(str(r.artist_id), 0),
                "audience_tags": r.audience_tags,
                "content_rating": r.content_rating,
                "voice_dna": r.voice_dna,
                "visual_dna": r.visual_dna,
                "fashion_dna": r.fashion_dna,
                "lyrical_dna": r.lyrical_dna,
                "persona_dna": r.persona_dna,
                "social_dna": r.social_dna,
                "ceo_approved": r.ceo_approved,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
        "count": len(rows),
    }


class ReleaseCreateRequest(BaseModel):
    artist_id: str
    title: str
    release_type: str = "single"  # single | EP | album | compilation
    release_date: str | None = None  # ISO date
    pre_save_date: str | None = None
    distributor: str | None = None
    territory_rights: list[str] | None = None  # ISO country codes, default WORLD


class ReleaseAddTrackRequest(BaseModel):
    song_id: str
    track_number: int = 1
    is_lead_single: bool = False


@router.post("/api/v1/admin/releases")
async def create_release(
    body: ReleaseCreateRequest,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """T-183: create a release in 'planning' status. Tracks are added separately."""
    import uuid as _uuid
    from datetime import date as _date
    from sqlalchemy import text as _text

    try:
        artist_uuid = _uuid.UUID(body.artist_id)
    except ValueError:
        raise HTTPException(400, detail="invalid artist_id")

    valid_types = {"single", "EP", "album", "compilation"}
    if body.release_type not in valid_types:
        raise HTTPException(400, detail=f"release_type must be one of {valid_types}")

    rel_date = _date.fromisoformat(body.release_date) if body.release_date else None
    pre_save = _date.fromisoformat(body.pre_save_date) if body.pre_save_date else None

    r = await db.execute(
        _text("""
            INSERT INTO releases
              (artist_id, title, release_type, release_date, pre_save_date,
               distributor, territory_rights, status)
            VALUES (:aid, :title, :rtype, :rdate, :pdate, :dist, :tr, 'planning')
            RETURNING id, status, created_at
        """),
        {
            "aid": artist_uuid,
            "title": body.title,
            "rtype": body.release_type,
            "rdate": rel_date,
            "pdate": pre_save,
            "dist": body.distributor,
            "tr": body.territory_rights or ["WORLD"],
        },
    )
    row = r.fetchone()
    await db.commit()
    return {
        "id": str(row[0]),
        "artist_id": body.artist_id,
        "title": body.title,
        "release_type": body.release_type,
        "status": row[1],
        "created_at": row[2].isoformat(),
        "track_count": 0,
    }


@router.get("/api/v1/admin/releases")
async def list_releases(
    status: str | None = None,
    artist_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    from sqlalchemy import text as _text
    where = []
    params = {}
    if status:
        where.append("r.status = :status")
        params["status"] = status
    if artist_id:
        import uuid as _uuid
        try:
            params["aid"] = _uuid.UUID(artist_id)
        except ValueError:
            raise HTTPException(400, detail="invalid artist_id")
        where.append("r.artist_id = :aid")
    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    q = f"""
        SELECT r.id, r.artist_id, r.title, r.release_type, r.release_date,
               r.status, r.distributor, r.upc, r.created_at,
               COUNT(rtr.id) AS track_count,
               a.stage_name
        FROM releases r
        LEFT JOIN release_track_record rtr ON rtr.release_id = r.id
        LEFT JOIN ai_artists a ON a.artist_id = r.artist_id
        {where_clause}
        GROUP BY r.id, a.stage_name
        ORDER BY r.created_at DESC
        LIMIT 100
    """
    result = await db.execute(_text(q), params)
    rows = result.fetchall()
    return {
        "releases": [
            {
                "id": str(row[0]),
                "artist_id": str(row[1]),
                "artist_name": row[10],
                "title": row[2],
                "release_type": row[3],
                "release_date": row[4].isoformat() if row[4] else None,
                "status": row[5],
                "distributor": row[6],
                "upc": row[7],
                "created_at": row[8].isoformat(),
                "track_count": row[9],
            }
            for row in rows
        ],
        "count": len(rows),
    }


@router.get("/api/v1/admin/releases/{release_id}")
async def get_release(
    release_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    import uuid as _uuid
    from sqlalchemy import text as _text
    try:
        rid = _uuid.UUID(release_id)
    except ValueError:
        raise HTTPException(400, detail="invalid release_id")

    r = await db.execute(
        _text("""
            SELECT r.id, r.artist_id, r.title, r.release_type, r.release_date,
                   r.pre_save_date, r.status, r.distributor, r.distributor_release_id,
                   r.upc, r.territory_rights, r.created_at, a.stage_name
            FROM releases r
            LEFT JOIN ai_artists a ON a.artist_id = r.artist_id
            WHERE r.id = :rid
        """),
        {"rid": rid},
    )
    row = r.fetchone()
    if row is None:
        raise HTTPException(404, detail="release not found")

    t = await db.execute(
        _text("""
            SELECT rtr.song_id, rtr.track_number, rtr.is_lead_single,
                   s.title, s.status, s.duration_seconds, s.isrc, s.generation_provider
            FROM release_track_record rtr
            JOIN songs_master s ON s.song_id = rtr.song_id
            WHERE rtr.release_id = :rid
            ORDER BY rtr.track_number
        """),
        {"rid": rid},
    )
    tracks = [
        {
            "song_id": str(tr[0]),
            "track_number": tr[1],
            "is_lead_single": tr[2],
            "title": tr[3],
            "status": tr[4],
            "duration_seconds": tr[5],
            "isrc": tr[6],
            "generation_provider": tr[7],
        }
        for tr in t.fetchall()
    ]
    return {
        "id": str(row[0]),
        "artist_id": str(row[1]),
        "artist_name": row[12],
        "title": row[2],
        "release_type": row[3],
        "release_date": row[4].isoformat() if row[4] else None,
        "pre_save_date": row[5].isoformat() if row[5] else None,
        "status": row[6],
        "distributor": row[7],
        "distributor_release_id": row[8],
        "upc": row[9],
        "territory_rights": row[10],
        "created_at": row[11].isoformat(),
        "tracks": tracks,
        "track_count": len(tracks),
    }


# Statuses that a song can have and still be eligible for release binding.
# Tightens to {qa_passed} once T-162 audio QA is wired — for now we accept
# qa_pending and draft too so the orchestrator can be smoke-tested before
# the QA service lands.
_BINDABLE_SONG_STATUSES = {"draft", "qa_pending", "qa_passed"}


@router.post("/api/v1/admin/releases/{release_id}/tracks")
async def add_track_to_release(
    release_id: str,
    body: ReleaseAddTrackRequest,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Bind a song to a release. Creates release_track_record, sets
    songs_master.release_id and status='assigned_to_release'.

    Validates: release exists, song exists, song is in a bindable
    status, song is not already bound to a different release, song's
    artist matches the release's artist.
    """
    import uuid as _uuid
    from sqlalchemy import text as _text
    from sqlalchemy.exc import IntegrityError

    try:
        rid = _uuid.UUID(release_id)
        sid = _uuid.UUID(body.song_id)
    except ValueError:
        raise HTTPException(400, detail="invalid release_id or song_id")

    rel = (await db.execute(
        _text("SELECT id, artist_id, status FROM releases WHERE id = :rid"),
        {"rid": rid},
    )).fetchone()
    if rel is None:
        raise HTTPException(404, detail="release not found")

    song = (await db.execute(
        _text("""
            SELECT song_id, primary_artist_id, status, release_id
            FROM songs_master WHERE song_id = :sid
        """),
        {"sid": sid},
    )).fetchone()
    if song is None:
        raise HTTPException(404, detail="song not found")
    if song[3] is not None and song[3] != rid:
        raise HTTPException(409, detail=f"song already bound to release {song[3]}")
    if song[2] not in _BINDABLE_SONG_STATUSES:
        raise HTTPException(
            409,
            detail=f"song status '{song[2]}' is not bindable "
                   f"(must be one of {sorted(_BINDABLE_SONG_STATUSES)})",
        )
    if song[1] != rel[1]:
        raise HTTPException(
            409,
            detail="song.primary_artist_id does not match release.artist_id — "
                   "cross-artist releases are not supported yet",
        )

    try:
        await db.execute(
            _text("""
                INSERT INTO release_track_record (song_id, release_id, track_number, is_lead_single)
                VALUES (:sid, :rid, :tn, :lead)
                ON CONFLICT (release_id, track_number) DO NOTHING
            """),
            {"sid": sid, "rid": rid, "tn": body.track_number, "lead": body.is_lead_single},
        )
        await db.execute(
            _text("""
                UPDATE songs_master
                SET release_id = :rid,
                    status = 'assigned_to_release',
                    updated_at = NOW()
                WHERE song_id = :sid
            """),
            {"rid": rid, "sid": sid},
        )
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(409, detail=f"integrity constraint: {str(e.orig)[:200]}")

    return {
        "release_id": str(rid),
        "song_id": str(sid),
        "track_number": body.track_number,
        "is_lead_single": body.is_lead_single,
        "song_status": "assigned_to_release",
    }


@router.delete("/api/v1/admin/releases/{release_id}/tracks/{song_id}")
async def remove_track_from_release(
    release_id: str,
    song_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Unbind a song from a release (mistake correction). Reverts song to qa_pending."""
    import uuid as _uuid
    from sqlalchemy import text as _text

    try:
        rid = _uuid.UUID(release_id)
        sid = _uuid.UUID(song_id)
    except ValueError:
        raise HTTPException(400, detail="invalid ids")

    r = await db.execute(
        _text("DELETE FROM release_track_record WHERE release_id = :rid AND song_id = :sid RETURNING 1"),
        {"rid": rid, "sid": sid},
    )
    if r.scalar() is None:
        raise HTTPException(404, detail="track binding not found")

    await db.execute(
        _text("""
            UPDATE songs_master
            SET release_id = NULL, status = 'qa_pending', updated_at = NOW()
            WHERE song_id = :sid
        """),
        {"sid": sid},
    )
    await db.commit()
    return {"release_id": str(rid), "song_id": str(sid), "removed": True}


@router.post("/api/v1/admin/sweeps/submissions")
async def sweep_submissions_endpoint(
    include_optional: bool = False,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    T-225: run the Submissions Agent. Walks every assigned_to_release
    song, checks each lane's prereqs, and escalates missing items to
    the CEO gate.
    """
    from api.services.submissions_agent import sweep_submissions
    stats = await sweep_submissions(db, include_optional=include_optional)
    return {"detail": "submissions sweep complete", "stats": stats}


@router.get("/api/v1/admin/submissions/prerequisites/{artist_id}")
async def get_submission_prerequisites(
    artist_id: str,
    include_optional: bool = True,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Show every missing submission prerequisite for a given artist.
    Used by the Settings UI to display the lane-by-lane readiness grid.
    """
    import uuid as _uuid
    from api.services.submissions_agent import check_prerequisites_for_artist

    try:
        aid = _uuid.UUID(artist_id)
    except ValueError:
        raise HTTPException(400, detail="invalid artist_id")

    reports = await check_prerequisites_for_artist(
        db, aid, include_optional=include_optional
    )
    return {"artist_id": artist_id, "reports": reports, "count": len(reports)}


@router.post("/api/v1/admin/sweeps/audio-qa")
async def sweep_audio_qa_endpoint(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    T-162-lite: run the lightweight audio QA sweep across all
    songs in qa_pending. Returns stats dict.
    """
    from api.services.audio_qa_lite import sweep_audio_qa
    stats = await sweep_audio_qa(db, limit=limit)
    return {"detail": "audio qa sweep complete", "stats": stats}


@router.post("/api/v1/admin/songs/{song_id}/mark-qa-passed")
async def mark_song_qa_passed(
    song_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Manual bypass: flip a song from qa_pending to qa_passed without
    running real QA. Used for testing the release assembly path until
    T-162 Essentia/Librosa-based QA service lands.
    """
    import uuid as _uuid
    from sqlalchemy import text as _text

    try:
        sid = _uuid.UUID(song_id)
    except ValueError:
        raise HTTPException(400, detail="invalid song_id")

    r = await db.execute(
        _text("""
            UPDATE songs_master
            SET status = 'qa_passed', qa_pass = TRUE, updated_at = NOW()
            WHERE song_id = :sid AND status IN ('draft', 'qa_pending')
            RETURNING status
        """),
        {"sid": sid},
    )
    row = r.fetchone()
    if row is None:
        raise HTTPException(
            409,
            detail="song not found or not in a bypass-eligible status (draft|qa_pending)",
        )
    await db.commit()
    return {"song_id": str(sid), "status": row[0], "qa_pass": True, "bypass": True}


class GenerateSongRequest(BaseModel):
    provider: str = "musicgen"
    duration_seconds: int = 30
    model_variant: str | None = None
    title: str | None = None  # optional override of auto-derived working title


@router.post("/api/v1/admin/blueprints/{blueprint_id}/generate-song")
async def generate_song_for_blueprint(
    blueprint_id: str,
    body: GenerateSongRequest,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    T-160: Blueprint → song generation orchestrator (§24).

    Preconditions: blueprint exists, has assigned_artist_id (set by the
    CEO gate via approve), and the provider is live in the registry.

    Side effects:
      - songs_master row created with status='draft', release_id=NULL
      - music_generation_calls row created and linked via song_id
      - Provider call submitted asynchronously
      - On later successful poll: audio bytes self-hosted, songs_master
        flips to 'qa_pending', audio_assets row created.

    Release assembly is a SEPARATE step (T-183, §30) — never done here.
    """
    import uuid as _uuid
    from api.models.ai_artist import AIArtist
    from api.models.music_generation_call import MusicGenerationCall
    from api.models.song_blueprint import SongBlueprint
    from api.models.songs_master import SongMaster
    from api.services.generation_orchestrator import (
        assemble_generation_prompt,
        derive_song_title,
    )
    from api.services.music_providers import (
        GenerateParams,
        ProviderError,
        get_provider,
    )

    try:
        bp_uuid = _uuid.UUID(blueprint_id)
    except ValueError:
        raise HTTPException(400, detail="invalid blueprint_id")

    # Load blueprint
    blueprint = (await db.execute(
        select(SongBlueprint).where(SongBlueprint.id == bp_uuid)
    )).scalar_one_or_none()
    if blueprint is None:
        raise HTTPException(404, detail="blueprint not found")
    if blueprint.assigned_artist_id is None:
        raise HTTPException(
            409,
            detail="blueprint has no assigned_artist_id — run the assignment engine "
                   "and approve via the CEO gate first",
        )

    # Load artist
    artist = (await db.execute(
        select(AIArtist).where(AIArtist.artist_id == blueprint.assigned_artist_id)
    )).scalar_one_or_none()
    if artist is None:
        raise HTTPException(500, detail="assigned artist row missing")

    # Voice state — optional (None for first song)
    from sqlalchemy import text as _text
    voice_state_row = await db.execute(
        _text("SELECT * FROM artist_voice_state WHERE artist_id = :aid LIMIT 1"),
        {"aid": artist.artist_id},
    )
    vs = voice_state_row.fetchone()
    voice_state_dict: dict | None = None
    if vs is not None:
        # Convert SQLAlchemy Row to dict of named attributes
        voice_state_dict = {k: getattr(vs, k) for k in vs._mapping.keys()}

    # Assemble artist + blueprint dicts for the orchestrator service
    artist_dict = {
        "voice_dna": artist.voice_dna,
        "song_count": artist.song_count or 0,
        "content_rating": artist.content_rating or "mild",
    }

    # Regenerate the smart_prompt FRESH for this generation, passing the
    # artist's edge_profile so the edge rules + pop-culture references
    # match the persona. Part 1+2+3 of the edgy-themes pipeline: the
    # blueprint's stored smart_prompt_text was built genre-only at
    # blueprint-creation time and knows nothing about the artist or this
    # week's culture. We override it per-generation so every song gets
    # fresh references and voice-matched edge.
    #
    # If the fresh call fails (LLM outage, etc), fall back to the stored
    # blueprint text so a generation never blocks on the edge layer.
    from api.services.smart_prompt import generate_smart_prompt
    genre_for_prompt = blueprint.primary_genre or blueprint.genre_id
    fresh_smart_prompt_text: str | None = None
    try:
        fresh = await generate_smart_prompt(
            db,
            genre=genre_for_prompt,
            model="suno",
            edge_profile=getattr(artist, "edge_profile", None),
        )
        if fresh and fresh.get("prompt"):
            fresh_smart_prompt_text = fresh["prompt"]
            logger.info(
                "[orchestrator] fresh smart_prompt for %s — edge=%s refs_offered=%d",
                genre_for_prompt,
                fresh.get("edge_profile"),
                fresh.get("pop_culture_refs_offered", 0),
            )
    except Exception:
        logger.exception("[orchestrator] fresh smart_prompt failed, falling back")

    blueprint_dict = {
        "smart_prompt_text": fresh_smart_prompt_text or blueprint.smart_prompt_text,
        "primary_genre": blueprint.primary_genre or blueprint.genre_id,
        "genre_id": blueprint.genre_id,
        "target_themes": blueprint.target_themes or [],
    }
    final_prompt = assemble_generation_prompt(
        artist=artist_dict,
        blueprint=blueprint_dict,
        voice_state=voice_state_dict,
    )
    title = body.title or derive_song_title(blueprint_dict, artist_dict)

    # Call provider
    try:
        adapter = get_provider(body.provider)
    except KeyError as e:
        raise HTTPException(404, detail=str(e))

    gen_params = GenerateParams(
        prompt=final_prompt,
        duration_seconds=body.duration_seconds,
        genre_hint=blueprint.primary_genre or blueprint.genre_id,
        model_variant=body.model_variant,
    )
    try:
        task = await adapter.generate(gen_params)
    except ProviderError as e:
        raise HTTPException(503, detail=str(e))
    except Exception as e:
        logger.exception("[orchestrator] %s generate failed", body.provider)
        raise HTTPException(502, detail=f"provider call failed: {e}")

    # Create the songs_master row in draft status
    song = SongMaster(
        title=title,
        primary_artist_id=artist.artist_id,
        blueprint_id=blueprint.id,
        primary_genre=blueprint.primary_genre or blueprint.genre_id,
        content_rating=artist.content_rating or "mild",
        status="draft",
        generation_provider=body.provider,
        generation_provider_job_id=task.task_id,
        generation_prompt=final_prompt,
        generation_params=task.params_echo,
        generation_cost_usd=task.estimated_cost_usd,
    )
    db.add(song)
    await db.flush()  # assign song.song_id before we FK to it

    # Create the linked music_generation_calls row
    call = MusicGenerationCall(
        provider=task.provider,
        task_id=task.task_id,
        status="pending",
        prompt=final_prompt,
        params_json=task.params_echo,
        model_variant=body.model_variant,
        duration_seconds_requested=body.duration_seconds,
        genre_hint=blueprint.primary_genre or blueprint.genre_id,
        breakout_event_id=None,
        blueprint_id=blueprint.id,
        estimated_cost_usd=task.estimated_cost_usd,
        submitted_at=task.submitted_at,
    )
    db.add(call)
    await db.flush()
    # Link the call row to the song (new FK column from T-160)
    await db.execute(
        _text("UPDATE music_generation_calls SET song_id = :sid WHERE id = :cid"),
        {"sid": song.song_id, "cid": call.id},
    )

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.exception("[orchestrator] persistence failed")
        raise HTTPException(500, detail=f"persistence failed: {e}")

    # Cover-art strategy:
    #   - Providers that ship their own cover art (Udio via PiAPI,
    #     Suno wrappers, etc.) — skip DALL-E, the poll handler will
    #     harvest the provider cover into primary_artwork_asset_id.
    #   - Providers that don't ship cover art (MusicGen via Replicate,
    #     raw audio models) — fire DALL-E now so the song has a cover
    #     before the first poll.
    providers_with_covers = {"udio", "suno_kie"}
    cover_info = None
    if body.provider in providers_with_covers:
        logger.info(
            "[orchestrator] skipping DALL-E cover for %s — "
            "provider will supply its own",
            body.provider,
        )
    else:
        from api.services.image_generator import (
            build_song_cover_prompt,
            generate_and_store_image,
        )
        cover_prompt = build_song_cover_prompt(
            title=title,
            genre=blueprint.primary_genre or blueprint.genre_id,
            artist_visual=artist.visual_dna,
            themes=blueprint.target_themes,
        )
        cover = await generate_and_store_image(
            db,
            artist_id=artist.artist_id,
            asset_type="song_artwork",
            prompt=cover_prompt,
        )
        if cover is not None:
            await db.execute(
                _text("""
                    UPDATE songs_master
                    SET primary_artwork_asset_id = :asset_id,
                        artwork_brief = :brief,
                        updated_at = NOW()
                    WHERE song_id = :sid
                """),
                {"asset_id": cover.asset_id, "brief": cover_prompt[:500], "sid": song.song_id},
            )
            await db.commit()
            cover_info = {
                "asset_id": str(cover.asset_id),
                "storage_url": cover.storage_url,
                "provider": cover.provider,
            }
        else:
            logger.warning("[orchestrator] cover generation skipped for song %s", song.song_id)

    return {
        "song_id": str(song.song_id),
        "task_id": task.task_id,
        "provider": task.provider,
        "estimated_cost_usd": task.estimated_cost_usd,
        "title": title,
        "status": "draft",
        "prompt_preview": final_prompt[:200],
        "cover": cover_info,
    }


@router.post("/api/v1/admin/blueprints/{blueprint_id}/assign")
async def assign_blueprint(
    blueprint_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Run the §22 assignment engine against the current roster. On a reuse
    recommendation the decision is logged to ceo_decisions as pending. On
    create_new it's also logged but with proposal='create_new' and no
    proposed_artist_id.
    """
    import uuid as _uuid
    from api.models.ai_artist import AIArtist
    from api.models.ceo_decision import CEODecision
    from api.models.song_blueprint import SongBlueprint
    from api.services.assignment_engine import AssignmentEngine

    try:
        bp_uuid = _uuid.UUID(blueprint_id)
    except ValueError:
        raise HTTPException(400, detail="invalid blueprint_id")

    bp = (await db.execute(
        select(SongBlueprint).where(SongBlueprint.id == bp_uuid)
    )).scalar_one_or_none()
    if bp is None:
        raise HTTPException(404, detail="blueprint not found")

    roster_rows = (await db.execute(
        select(AIArtist).where(AIArtist.roster_status == "active")
    )).scalars().all()

    bp_dict = {
        "id": str(bp.id),
        "primary_genre": bp.primary_genre or bp.genre_id,
        "adjacent_genres": bp.adjacent_genres or [],
        "target_themes": bp.target_themes or [],
        "vocabulary_tone": bp.vocabulary_tone,
        "target_audience_tags": bp.target_audience_tags or [],
        "voice_requirements": bp.voice_requirements,
    }
    roster_dicts = [
        {
            "artist_id": str(a.artist_id),
            "stage_name": a.stage_name,
            "primary_genre": a.primary_genre,
            "adjacent_genres": a.adjacent_genres or [],
            "voice_dna": a.voice_dna,
            "lyrical_dna": a.lyrical_dna or {},
            "audience_tags": a.audience_tags or [],
            "song_count": a.song_count,
        }
        for a in roster_rows
    ]

    engine = AssignmentEngine(reuse_threshold=0.68)
    decision = engine.decide(blueprint=bp_dict, roster=roster_dicts)

    # Persist a CEODecision row as the pending gate.
    artist_name_map = {str(a.artist_id): a.stage_name for a in roster_rows}
    decision_row = CEODecision(
        decision_type="artist_assignment",
        entity_type="song_blueprint",
        entity_id=bp.id,
        proposal=decision.proposal,
        data={
            "blueprint_id": str(bp.id),
            "blueprint_genre": bp.genre_id,
            "proposed_artist_id": decision.proposed_artist_id,
            "proposed_artist_name": (
                artist_name_map.get(decision.proposed_artist_id)
                if decision.proposed_artist_id else None
            ),
            "scores": decision.scores,
            "breakdown": decision.breakdown,
            "threshold": decision.threshold,
            "reason": decision.reason,
            "roster_size": len(roster_dicts),
        },
        status="pending",
    )
    db.add(decision_row)
    await db.commit()
    await db.refresh(decision_row)

    # T-150: auto-dispatch to the CEO's configured channel (Telegram)
    try:
        from api.models.ceo_profile import CeoProfile
        profile_row = (await db.execute(select(CeoProfile).limit(1))).scalar_one_or_none()
        if profile_row:
            from api.services.telegram_bot import send_ceo_decision
            decision_dict = {
                "decision_id": str(decision_row.decision_id),
                "decision_type": decision_row.decision_type,
                "proposal": decision_row.proposal,
                "data": decision_row.data,
                "created_at": decision_row.created_at.isoformat() if decision_row.created_at else None,
            }
            await send_ceo_decision(decision_dict, profile_row)
    except Exception:
        logger.exception("[assign] CEO notify failed (non-fatal)")

    return {
        "decision_id": str(decision_row.decision_id),
        "proposal": decision.proposal,
        "proposed_artist_id": decision.proposed_artist_id,
        "proposed_artist_name": artist_name_map.get(decision.proposed_artist_id or ""),
        "scores": decision.scores,
        "breakdown": decision.breakdown,
        "threshold": decision.threshold,
        "reason": decision.reason,
        "status": decision_row.status,
    }


class CEODecisionRespondRequest(BaseModel):
    response_notes: str | None = None
    modifications: dict | None = None


class TelegramTestRequest(BaseModel):
    text: str | None = None


@router.post("/api/v1/admin/telegram/test")
async def telegram_test(
    body: TelegramTestRequest | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Send a test message to the CEO's configured Telegram chat.
    Verifies TELEGRAM_BOT_TOKEN + ceo_profile.telegram_chat_id.
    """
    from sqlalchemy import text as _text
    from api.services.telegram_bot import (
        TelegramNotConfigured, send_message,
    )

    row = await db.execute(
        _text("SELECT telegram_chat_id FROM ceo_profile LIMIT 1")
    )
    result = row.fetchone()
    if not result or not result[0]:
        raise HTTPException(
            409,
            detail="CEO profile has no telegram_chat_id — set it in Settings → CEO Profile",
        )
    chat_id = result[0]

    text = (body.text if body and body.text else
            "🔔 <b>SoundPulse test message</b>\n\n"
            "If you're seeing this, your Telegram delivery is wired correctly. "
            "You'll receive approval gates, setup reminders, and decision "
            "escalations here automatically.")

    try:
        await send_message(chat_id, text)
    except TelegramNotConfigured as e:
        raise HTTPException(503, detail=str(e))
    except Exception as e:
        raise HTTPException(502, detail=f"telegram send failed: {e}")

    return {"sent": True, "chat_id": chat_id}


# ---------------------------------------------------------------------
# Instrumentals — Task #86
#   CEO (or anyone with a track) can upload a beat/instrumental as an
#   audio file; Kie.ai's /api/v1/generate/add-vocals endpoint fetches it
#   via a public URL and Suno sings over it. Mirrors the other bytea
#   sidecar patterns (music_generation_audio, visual_asset_blobs).
# ---------------------------------------------------------------------

# Max bytes for a single upload — keeps uploads under Kie.ai's practical
# fetch limits and protects against accidental gigabyte drops. 40 MB
# covers ~15 minutes of mid-quality MP3, plenty for a single instrumental.
INSTRUMENTAL_MAX_BYTES = 40 * 1024 * 1024

# Content types we accept. Suno tolerates MP3/WAV/FLAC; other formats
# get rejected so we don't waste a Kie.ai call on a 415.
INSTRUMENTAL_ALLOWED_CTYPES = {
    "audio/mpeg", "audio/mp3",
    "audio/wav", "audio/x-wav", "audio/wave",
    "audio/flac", "audio/x-flac",
    "audio/ogg",
    "audio/aac", "audio/mp4", "audio/x-m4a", "audio/m4a",
}

# Map content type to the extension we serve publicly. Kie.ai inspects
# the URL's extension to decide how to decode the audio.
INSTRUMENTAL_EXT_FOR_CTYPE = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/flac": "flac",
    "audio/x-flac": "flac",
    "audio/ogg": "ogg",
    "audio/aac": "aac",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/m4a": "m4a",
}


@router.post("/api/v1/admin/instrumentals/upload")
async def upload_instrumental(
    title: str = Form(...),
    file: UploadFile = File(...),
    tempo_bpm: float | None = Form(None),
    key_hint: str | None = Form(None),
    genre_hint: str | None = Form(None),
    notes: str | None = Form(None),
    uploaded_by: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Upload an instrumental audio file. Stores metadata in `instrumentals`
    and bytes in `instrumental_blobs`. Returns the public streaming URL
    Kie.ai can fetch when we call /api/v1/generate/add-vocals.

    Multipart form fields:
      title       (required)   — friendly name for the track
      file        (required)   — the audio file (mp3/wav/flac/ogg/aac/m4a)
      tempo_bpm   (optional)   — known BPM if you have it
      key_hint    (optional)   — "A minor", "F# major", etc
      genre_hint  (optional)   — drives the style descriptor for Suno
      notes       (optional)   — free text
      uploaded_by (optional)   — who uploaded this (CEO or agent name)
    """
    from api.models.instrumental import Instrumental, InstrumentalBlob

    raw = await file.read()
    if not raw:
        raise HTTPException(400, detail="empty upload")
    if len(raw) > INSTRUMENTAL_MAX_BYTES:
        raise HTTPException(
            413,
            detail=f"file exceeds {INSTRUMENTAL_MAX_BYTES // (1024 * 1024)} MB limit",
        )

    content_type = (file.content_type or "application/octet-stream").lower().strip()
    if content_type not in INSTRUMENTAL_ALLOWED_CTYPES:
        # Try to infer from filename extension as a fallback
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
                detail=f"unsupported content type '{content_type}' — allowed: mp3, wav, flac, ogg, aac, m4a",
            )

    row = Instrumental(
        title=title,
        uploaded_by=uploaded_by,
        genre_hint=genre_hint,
        tempo_bpm=tempo_bpm,
        key_hint=key_hint,
        notes=notes,
        original_filename=file.filename,
        content_type=content_type,
        size_bytes=len(raw),
    )
    db.add(row)
    await db.flush()  # we need row.id before inserting the blob
    db.add(InstrumentalBlob(
        instrumental_id=row.id,
        audio_bytes=raw,
    ))
    await db.commit()
    await db.refresh(row)

    ext = INSTRUMENTAL_EXT_FOR_CTYPE.get(content_type, "mp3")
    public_path = f"/api/v1/instrumentals/public/{row.id}.{ext}"

    logger.info(
        "[instrumentals] uploaded %s (%d bytes, %s) → %s",
        row.title, row.size_bytes, content_type, public_path,
    )
    return {
        "instrumental_id": str(row.id),
        "title": row.title,
        "size_bytes": row.size_bytes,
        "content_type": row.content_type,
        "tempo_bpm": row.tempo_bpm,
        "key_hint": row.key_hint,
        "public_url_path": public_path,
        "created_at": row.created_at.isoformat(),
    }


@router.get("/api/v1/admin/instrumentals")
async def list_instrumentals(
    active_only: bool = True,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """List uploaded instrumentals — used by the SongLab UI to pick one."""
    from api.models.instrumental import Instrumental
    stmt = select(Instrumental).order_by(Instrumental.created_at.desc()).limit(
        max(1, min(limit, 500))
    )
    if active_only:
        stmt = stmt.where(Instrumental.is_active == True)  # noqa: E712
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "count": len(rows),
        "instrumentals": [
            {
                "instrumental_id": str(r.id),
                "title": r.title,
                "uploaded_by": r.uploaded_by,
                "genre_hint": r.genre_hint,
                "tempo_bpm": r.tempo_bpm,
                "key_hint": r.key_hint,
                "duration_seconds": r.duration_seconds,
                "size_bytes": r.size_bytes,
                "content_type": r.content_type,
                "original_filename": r.original_filename,
                "usage_count": r.usage_count,
                "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
                "public_url_path": f"/api/v1/instrumentals/public/{r.id}.{INSTRUMENTAL_EXT_FOR_CTYPE.get(r.content_type, 'mp3')}",
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


@router.delete("/api/v1/admin/instrumentals/{instrumental_id}")
async def delete_instrumental(
    instrumental_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Soft-delete an instrumental (sets is_active=false). Blob stays
    until a separate prune sweep to avoid breaking any in-flight Suno
    calls that already have the public URL."""
    import uuid as _uuid
    from api.models.instrumental import Instrumental
    try:
        iid = _uuid.UUID(instrumental_id)
    except ValueError:
        raise HTTPException(400, detail="invalid instrumental_id")
    row = (await db.execute(
        select(Instrumental).where(Instrumental.id == iid)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, detail="not found")
    row.is_active = False
    await db.commit()
    return {"instrumental_id": str(iid), "is_active": False}


@router.post("/api/v1/admin/blueprints/{blueprint_id}/generate-song-with-instrumental")
async def generate_song_with_instrumental(
    blueprint_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Variant of generate-song that uploads an uploaded instrumental and
    has Suno write vocals over it via Kie.ai's /api/v1/generate/add-vocals
    endpoint.

    Body:
      instrumental_id    (required, str) — uuid of a row in instrumentals
      duration_seconds   (optional int, default 60)
      title              (optional str — overrides derived title)
      vocal_gender       (optional 'm' | 'f')

    Preconditions: blueprint has assigned_artist_id (same as generate-song).
    """
    import uuid as _uuid
    from api.models.ai_artist import AIArtist
    from api.models.instrumental import Instrumental
    from api.models.music_generation_call import MusicGenerationCall
    from api.models.song_blueprint import SongBlueprint
    from api.models.songs_master import SongMaster
    from api.services.generation_orchestrator import (
        assemble_generation_prompt,
        derive_song_title,
    )
    from api.services.music_providers import (
        GenerateParams,
        ProviderError,
        get_provider,
    )

    instrumental_id_raw = body.get("instrumental_id")
    if not instrumental_id_raw:
        raise HTTPException(400, detail="instrumental_id is required")
    try:
        iid = _uuid.UUID(instrumental_id_raw)
    except ValueError:
        raise HTTPException(400, detail="invalid instrumental_id")
    try:
        bp_uuid = _uuid.UUID(blueprint_id)
    except ValueError:
        raise HTTPException(400, detail="invalid blueprint_id")

    instrumental = (await db.execute(
        select(Instrumental).where(Instrumental.id == iid)
    )).scalar_one_or_none()
    if instrumental is None or not instrumental.is_active:
        raise HTTPException(404, detail="instrumental not found or inactive")

    blueprint = (await db.execute(
        select(SongBlueprint).where(SongBlueprint.id == bp_uuid)
    )).scalar_one_or_none()
    if blueprint is None:
        raise HTTPException(404, detail="blueprint not found")
    if blueprint.assigned_artist_id is None:
        raise HTTPException(
            409,
            detail="blueprint has no assigned_artist_id — run assignment engine first",
        )

    artist = (await db.execute(
        select(AIArtist).where(AIArtist.artist_id == blueprint.assigned_artist_id)
    )).scalar_one_or_none()
    if artist is None:
        raise HTTPException(500, detail="assigned artist missing")

    artist_dict = {
        "voice_dna": artist.voice_dna,
        "song_count": artist.song_count or 0,
        "content_rating": artist.content_rating or "mild",
    }

    # Fresh smart_prompt with edge_profile, same as the text-only path
    from api.services.smart_prompt import generate_smart_prompt
    genre_for_prompt = blueprint.primary_genre or blueprint.genre_id
    fresh_text: str | None = None
    try:
        fresh = await generate_smart_prompt(
            db,
            genre=genre_for_prompt,
            model="suno",
            edge_profile=getattr(artist, "edge_profile", None),
        )
        if fresh and fresh.get("prompt"):
            fresh_text = fresh["prompt"]
    except Exception:
        logger.exception("[instrumental-gen] fresh smart_prompt failed")

    blueprint_dict = {
        "smart_prompt_text": fresh_text or blueprint.smart_prompt_text,
        "primary_genre": genre_for_prompt,
        "genre_id": blueprint.genre_id,
        "target_themes": blueprint.target_themes or [],
    }
    final_prompt = assemble_generation_prompt(
        artist=artist_dict,
        blueprint=blueprint_dict,
        voice_state=None,  # instrumental replaces voice reference
    )

    # Build the public URL for Kie.ai to fetch
    import os as _os
    public_base = _os.environ.get(
        "PUBLIC_BASE_URL",
        "https://soundpulse-production-5266.up.railway.app",
    )
    ext = INSTRUMENTAL_EXT_FOR_CTYPE.get(instrumental.content_type, "mp3")
    upload_url = f"{public_base}/api/v1/instrumentals/public/{instrumental.id}.{ext}"

    title = body.get("title") or derive_song_title(blueprint_dict, artist_dict)
    vocal_gender = body.get("vocal_gender")

    adapter = get_provider("suno_kie")
    gen_params = GenerateParams(
        prompt=final_prompt,
        duration_seconds=int(body.get("duration_seconds") or 60),
        genre_hint=genre_for_prompt,
        tempo_bpm=instrumental.tempo_bpm,
        key_hint=instrumental.key_hint,
    )
    try:
        task = await adapter.generate_with_instrumental(
            gen_params,
            instrumental_url=upload_url,
            title=title,
            vocal_gender=vocal_gender,
        )
    except ProviderError as e:
        raise HTTPException(503, detail=str(e))
    except Exception as e:
        logger.exception("[instrumental-gen] suno add-vocals failed")
        raise HTTPException(502, detail=f"add-vocals call failed: {e}")

    # Bump usage counter on the instrumental
    instrumental.usage_count = (instrumental.usage_count or 0) + 1
    instrumental.last_used_at = datetime.now(timezone.utc)

    # Persist songs_master draft + music_generation_call (same pattern
    # as the text-only generate-song endpoint)
    song = SongMaster(
        title=title,
        primary_artist_id=artist.artist_id,
        blueprint_id=blueprint.id,
        primary_genre=genre_for_prompt,
        content_rating=artist.content_rating or "mild",
        status="draft",
        generation_provider="suno_kie",
        generation_provider_job_id=task.task_id,
        generation_cost_usd=task.estimated_cost_usd,
    )
    db.add(song)
    await db.flush()

    gen_call = MusicGenerationCall(
        provider="suno_kie",
        task_id=task.task_id,
        song_id=song.song_id,
        status="pending",
        submitted_at=task.submitted_at,
        params_echo=task.params_echo,
        estimated_cost_usd=task.estimated_cost_usd,
    )
    db.add(gen_call)
    await db.commit()
    await db.refresh(song)

    return {
        "song_id": str(song.song_id),
        "task_id": task.task_id,
        "provider": "suno_kie",
        "endpoint": "add-vocals",
        "title": title,
        "instrumental_id": str(instrumental.id),
        "instrumental_url": upload_url,
        "estimated_cost_usd": task.estimated_cost_usd,
        "status": "draft",
    }


# ---------------------------------------------------------------------
# External submissions — distributor/PRO/sync/playlist/marketing agents
# PRD §28..§37, T-200..T-229
# ---------------------------------------------------------------------

@router.get("/api/v1/admin/submission-targets")
async def list_submission_targets(
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """List every registered downstream integration target + whether
    its env credentials are present. Used by the Submissions page to
    show 'ready to go' vs 'needs config'."""
    from api.models.external_submission import SubmissionTarget
    import os as _os
    rows = (
        await db.execute(
            select(SubmissionTarget).order_by(SubmissionTarget.target_type, SubmissionTarget.display_name)
        )
    ).scalars().all()
    out = []
    for r in rows:
        missing = [k for k in (r.credential_env_keys or []) if not _os.environ.get(k, "").strip()]
        out.append({
            "target_service": r.target_service,
            "target_type": r.target_type,
            "display_name": r.display_name,
            "integration_status": r.integration_status,
            "is_enabled": r.is_enabled,
            "credential_env_keys": r.credential_env_keys,
            "missing_credentials": missing,
            "credential_ready": len(missing) == 0,
            "notes": r.notes,
        })
    return {"count": len(out), "targets": out}


@router.post("/api/v1/admin/external-submissions/submit")
async def trigger_external_submission(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Trigger a submission to any registered target. Body:
      {
        "target_service": "distrokid" | "bmi" | ...,
        "submission_subject_type": "song" | "release" | ...,
        "subject_id": "<uuid>",
        "force_retry": false (optional)
      }
    """
    import uuid as _uuid
    from api.services.external_submission_agent import submit_subject
    target_service = (body.get("target_service") or "").strip()
    subject_type = (body.get("submission_subject_type") or "").strip()
    subject_id_raw = body.get("subject_id")
    if not (target_service and subject_type and subject_id_raw):
        raise HTTPException(400, detail="target_service, submission_subject_type, subject_id required")
    try:
        sid = _uuid.UUID(subject_id_raw)
    except ValueError:
        raise HTTPException(400, detail="invalid subject_id")

    sub = await submit_subject(
        db,
        target_service=target_service,
        submission_subject_type=subject_type,
        subject_id=sid,
        force_retry=bool(body.get("force_retry")),
    )
    return {
        "submission_id": str(sub.id),
        "target_service": sub.target_service,
        "subject_id": str(sub.subject_id),
        "status": sub.status,
        "external_id": sub.external_id,
        "last_error_message": sub.last_error_message,
        "retry_count": sub.retry_count,
    }


@router.get("/api/v1/admin/external-submissions")
async def list_external_submissions(
    target_service: str | None = None,
    status: str | None = None,
    subject_id: str | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Browse external_submissions — filter by target_service, status,
    or subject_id. Used by the Submissions page."""
    import uuid as _uuid
    from api.models.external_submission import ExternalSubmission
    stmt = select(ExternalSubmission).order_by(
        ExternalSubmission.created_at.desc()
    ).limit(max(1, min(limit, 500)))
    if target_service:
        stmt = stmt.where(ExternalSubmission.target_service == target_service)
    if status:
        stmt = stmt.where(ExternalSubmission.status == status)
    if subject_id:
        try:
            stmt = stmt.where(ExternalSubmission.subject_id == _uuid.UUID(subject_id))
        except ValueError:
            raise HTTPException(400, detail="invalid subject_id")
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "count": len(rows),
        "submissions": [
            {
                "id": str(r.id),
                "target_service": r.target_service,
                "target_type": r.target_type,
                "submission_subject_type": r.submission_subject_type,
                "subject_id": str(r.subject_id),
                "status": r.status,
                "external_id": r.external_id,
                "attempt_number": r.attempt_number,
                "retry_count": r.retry_count,
                "last_error_message": r.last_error_message,
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
                "accepted_at": r.accepted_at.isoformat() if r.accepted_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------
# ASCAP submissions — Fonzworth agent (T-190..T-194, PRD §31)
# ---------------------------------------------------------------------

@router.post("/api/v1/admin/songs/{song_id}/ascap-submit")
async def ascap_submit_song(
    song_id: str,
    force_retry: bool = False,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Submit a song to ASCAP's Fonzworth portal via the Playwright agent.

    Creates (or reuses) an ascap_submissions row and drives the browser
    to register the work. Returns the row's current state — check
    status field ('submitted' | 'failed' | 'accepted') and
    last_error_message on the response.

    Preconditions:
      - ASCAP_USERNAME / ASCAP_PASSWORD env vars set
      - playwright package + Chromium binary installed on the container
      - song exists and has a primary_artist_id
    """
    import uuid as _uuid
    from api.models.ai_artist import AIArtist
    from api.models.songs_master import SongMaster
    from api.services.ascap_fonzworth import submit_song_to_ascap

    try:
        sid = _uuid.UUID(song_id)
    except ValueError:
        raise HTTPException(400, detail="invalid song_id")

    song = (
        await db.execute(select(SongMaster).where(SongMaster.song_id == sid))
    ).scalar_one_or_none()
    if song is None:
        raise HTTPException(404, detail="song not found")

    artist = (
        await db.execute(
            select(AIArtist).where(AIArtist.artist_id == song.primary_artist_id)
        )
    ).scalar_one_or_none()
    if artist is None:
        raise HTTPException(500, detail="song's primary artist missing")

    sub = await submit_song_to_ascap(
        db,
        song=song,
        artist=artist,
        force_retry=force_retry,
    )
    return {
        "ascap_submission_id": str(sub.id),
        "song_id": str(sub.song_id),
        "status": sub.status,
        "ascap_work_id": sub.ascap_work_id,
        "attempt_number": sub.attempt_number,
        "retry_count": sub.retry_count,
        "last_error_message": sub.last_error_message,
        "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
    }


@router.get("/api/v1/admin/ascap-submissions")
async def list_ascap_submissions(
    status: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """List ASCAP submission rows. Used by the Submissions page."""
    from api.models.ascap_submission import AscapSubmission
    stmt = select(AscapSubmission).order_by(AscapSubmission.created_at.desc()).limit(
        max(1, min(limit, 500))
    )
    if status:
        stmt = stmt.where(AscapSubmission.status == status)
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "count": len(rows),
        "submissions": [
            {
                "id": str(r.id),
                "song_id": str(r.song_id),
                "status": r.status,
                "ascap_work_id": r.ascap_work_id,
                "attempt_number": r.attempt_number,
                "retry_count": r.retry_count,
                "submission_title": r.submission_title,
                "last_error_message": r.last_error_message,
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
                "accepted_at": r.accepted_at.isoformat() if r.accepted_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------
# Genre traits — Task #93
#   Multi-dimensional profile per genre (edginess, meme density,
#   earworm demand, etc). Seeded by migration 020; CEO can override.
#   Read by smart_prompt.py to scale behavior per genre.
# ---------------------------------------------------------------------

@router.get("/api/v1/admin/genre-traits")
async def list_genre_traits(
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Return every genre_traits row. Used by the admin UI to show the
    matrix and let the CEO bulk-edit."""
    from api.models.genre_traits import GenreTraits
    rows = (
        await db.execute(
            select(GenreTraits).order_by(GenreTraits.genre_id.asc())
        )
    ).scalars().all()
    return {
        "count": len(rows),
        "traits": [
            {
                "id": str(r.id),
                "genre_id": r.genre_id,
                "edginess": r.edginess,
                "meme_density": r.meme_density,
                "earworm_demand": r.earworm_demand,
                "sonic_experimentation": r.sonic_experimentation,
                "lyrical_complexity": r.lyrical_complexity,
                "vocal_processing": r.vocal_processing,
                "tempo_range_bpm": r.tempo_range_bpm,
                "key_mood": r.key_mood,
                "default_edge_profile": r.default_edge_profile,
                "vocabulary_era": r.vocabulary_era,
                "pop_culture_sources": r.pop_culture_sources,
                "instrumentation_palette": r.instrumentation_palette,
                "structural_conventions": r.structural_conventions,
                "notes": r.notes,
                "updated_by": r.updated_by,
                "is_system_default": r.is_system_default,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ],
    }


@router.put("/api/v1/admin/genre-traits/{genre_id:path}")
async def update_genre_traits(
    genre_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Update a genre_traits row — used by the CEO to override defaults.
    Flips is_system_default=FALSE so subsequent seeds don't clobber."""
    from api.models.genre_traits import GenreTraits
    from sqlalchemy import text as _text
    row = (
        await db.execute(
            select(GenreTraits).where(GenreTraits.genre_id == genre_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, detail=f"genre_traits for '{genre_id}' not found")

    allowed_int_fields = {
        "edginess", "meme_density", "earworm_demand",
        "sonic_experimentation", "lyrical_complexity", "vocal_processing",
    }
    for k in allowed_int_fields:
        if k in body and body[k] is not None:
            v = int(body[k])
            if v < 0 or v > 100:
                raise HTTPException(400, detail=f"{k} must be 0-100")
            setattr(row, k, v)

    if "tempo_range_bpm" in body and isinstance(body["tempo_range_bpm"], list) and len(body["tempo_range_bpm"]) == 2:
        row.tempo_range_bpm = [int(body["tempo_range_bpm"][0]), int(body["tempo_range_bpm"][1])]

    for k in ("key_mood", "default_edge_profile", "vocabulary_era", "structural_conventions", "notes"):
        if k in body and body[k] is not None:
            setattr(row, k, str(body[k]))

    for k in ("pop_culture_sources", "instrumentation_palette"):
        if k in body and isinstance(body[k], list):
            setattr(row, k, [str(x) for x in body[k]])

    row.is_system_default = False
    row.updated_by = body.get("updated_by") or "ceo_admin_ui"
    await db.execute(
        _text("UPDATE genre_traits SET updated_at = NOW() WHERE id = :id"),
        {"id": row.id},
    )
    await db.commit()
    await db.refresh(row)
    return {
        "genre_id": row.genre_id,
        "is_system_default": row.is_system_default,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.post("/api/v1/admin/pop-culture/refresh")
async def pop_culture_refresh(
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Part 3 of the edgy-themes pipeline — run the pop-culture reference
    scraper/harvester and persist fresh references.

    MVP: single LLM call to gpt-4o-mini asks for ~20 specific, currently-
    viral reference moments with type/text/context/genres/edge_tiers/decay.
    Each reference gets an expires_at based on its decay_weeks, then
    smart_prompt.py picks them up via fetch_references_for_prompt.

    Later: dedicated scrapers for TikTok Creative Center + X trending +
    Know Your Meme feed the same table — this function becomes one of
    several sources.
    """
    from api.services.pop_culture_scraper import refresh_pop_culture_references
    result = await refresh_pop_culture_references(db, caller="admin.pop_culture_refresh")
    if result.get("error"):
        raise HTTPException(502, detail=result["error"])
    return result


@router.get("/api/v1/admin/pop-culture/list")
async def pop_culture_list(
    live_only: bool = True,
    limit: int = 100,
    genre: str | None = None,
    edge: str | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Read pop_culture_references. Used to debug the scraper output
    and to surface 'what's in rotation' on the SongLab UI."""
    from sqlalchemy import text as _text
    params: dict[str, Any] = {"limit": max(1, min(limit, 500))}
    where: list[str] = []
    if live_only:
        where.append("expires_at > NOW()")
    if genre:
        where.append("(:genre = ANY(genres) OR genres = '{}' OR array_length(genres, 1) IS NULL)")
        params["genre"] = genre
    if edge:
        where.append(":edge = ANY(edge_tiers)")
        params["edge"] = edge
    sql = f"""
        SELECT id, reference_type, text, context, source, genres, edge_tiers,
               first_seen_at, expires_at, usage_count, last_used_at
        FROM pop_culture_references
        {"WHERE " + " AND ".join(where) if where else ""}
        ORDER BY first_seen_at DESC
        LIMIT :limit
    """
    rows = (await db.execute(_text(sql), params)).fetchall()
    return {
        "count": len(rows),
        "references": [
            {
                "id": str(r[0]),
                "type": r[1],
                "text": r[2],
                "context": r[3],
                "source": r[4],
                "genres": r[5] or [],
                "edge_tiers": r[6] or [],
                "first_seen_at": r[7].isoformat() if r[7] else None,
                "expires_at": r[8].isoformat() if r[8] else None,
                "usage_count": r[9] or 0,
                "last_used_at": r[10].isoformat() if r[10] else None,
            }
            for r in rows
        ],
    }


@router.get("/api/v1/admin/telegram/bot-info")
async def telegram_bot_info(
    _admin: ApiKey = Depends(require_admin),
):
    """
    Hit Telegram's getMe endpoint to verify the TELEGRAM_BOT_TOKEN is
    valid and tell us the bot's username. Used during setup to confirm
    the user /start'd the right bot.
    """
    import os
    import httpx
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise HTTPException(503, detail="TELEGRAM_BOT_TOKEN env not set")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            body = r.json()
    except Exception as e:
        raise HTTPException(502, detail=f"telegram getMe failed: {e}")
    if not body.get("ok"):
        raise HTTPException(401, detail=f"telegram rejected token: {body}")
    bot = body.get("result") or {}
    return {
        "valid": True,
        "bot_id": bot.get("id"),
        "username": bot.get("username"),
        "first_name": bot.get("first_name"),
        "can_join_groups": bot.get("can_join_groups"),
        "open_url": f"https://t.me/{bot.get('username')}" if bot.get("username") else None,
    }


@router.get("/api/v1/admin/telegram/get-chat-id")
async def telegram_get_chat_id(
    _admin: ApiKey = Depends(require_admin),
):
    """
    Fetch chat_ids that have recently messaged the bot. Used during
    setup so the CEO can send /start to the bot and then paste the
    returned chat_id into their profile without fishing through the
    Telegram API manually.
    """
    from api.services.telegram_bot import (
        TelegramNotConfigured, get_recent_chat_ids,
    )
    try:
        chats = await get_recent_chat_ids()
    except TelegramNotConfigured as e:
        raise HTTPException(503, detail=str(e))
    except Exception as e:
        raise HTTPException(502, detail=f"telegram getUpdates failed: {e}")

    return {
        "chats": chats,
        "count": len(chats),
        "hint": (
            "If this list is empty, open your Telegram bot in the app "
            "and send /start. Then call this endpoint again."
            if not chats else
            "Paste one of these chat_ids into Settings → CEO Profile → Telegram."
        ),
    }


@router.post("/api/v1/admin/ceo-decisions/{decision_id}/approve")
async def approve_ceo_decision(
    decision_id: str,
    body: CEODecisionRespondRequest | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """
    Approve a pending CEO decision. Side effects depend on decision_type:

    artist_assignment + proposal=reuse:
      - set blueprint.assigned_artist_id = proposed_artist_id
      - blueprint.status = 'assigned'
    artist_assignment + proposal=create_new:
      - blueprint.status = 'assigned_pending_creation'
        (the new-artist creation pipeline reads this status in a later session)
    """
    import uuid as _uuid
    from datetime import datetime, timezone
    from api.models.ceo_decision import CEODecision
    from api.models.song_blueprint import SongBlueprint

    try:
        d_uuid = _uuid.UUID(decision_id)
    except ValueError:
        raise HTTPException(400, detail="invalid decision_id")

    decision = (await db.execute(
        select(CEODecision).where(CEODecision.decision_id == d_uuid)
    )).scalar_one_or_none()
    if decision is None:
        raise HTTPException(404, detail="decision not found")
    if decision.status not in ("pending", "sent"):
        raise HTTPException(409, detail=f"decision already in status {decision.status}")

    now = datetime.now(timezone.utc)
    decision.status = (
        "approved_with_modifications"
        if (body and body.modifications) else "approved"
    )
    decision.response_at = now
    decision.response_payload = {
        "notes": body.response_notes if body else None,
        "modifications": body.modifications if body else None,
    }

    # Apply side effects
    if decision.decision_type == "artist_assignment" and decision.entity_id:
        blueprint = (await db.execute(
            select(SongBlueprint).where(SongBlueprint.id == decision.entity_id)
        )).scalar_one_or_none()
        if blueprint is not None:
            if decision.proposal == "reuse":
                artist_id_str = (decision.data or {}).get("proposed_artist_id")
                if artist_id_str:
                    blueprint.assigned_artist_id = _uuid.UUID(artist_id_str)
                blueprint.status = "assigned"
            elif decision.proposal == "create_new":
                blueprint.status = "assigned_pending_creation"

    await db.commit()
    await db.refresh(decision)
    return {
        "decision_id": str(decision.decision_id),
        "status": decision.status,
        "response_at": decision.response_at.isoformat() if decision.response_at else None,
    }


@router.post("/api/v1/admin/ceo-decisions/{decision_id}/reject")
async def reject_ceo_decision(
    decision_id: str,
    body: CEODecisionRespondRequest | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Reject a pending decision. Blueprint stays pending_assignment."""
    import uuid as _uuid
    from datetime import datetime, timezone
    from api.models.ceo_decision import CEODecision

    try:
        d_uuid = _uuid.UUID(decision_id)
    except ValueError:
        raise HTTPException(400, detail="invalid decision_id")

    decision = (await db.execute(
        select(CEODecision).where(CEODecision.decision_id == d_uuid)
    )).scalar_one_or_none()
    if decision is None:
        raise HTTPException(404, detail="decision not found")
    if decision.status not in ("pending", "sent"):
        raise HTTPException(409, detail=f"decision already in status {decision.status}")

    decision.status = "rejected"
    decision.response_at = datetime.now(timezone.utc)
    decision.response_payload = {"notes": body.response_notes if body else None}
    await db.commit()
    return {
        "decision_id": str(decision.decision_id),
        "status": decision.status,
    }


class SongMasterCreateRequest(BaseModel):
    title: str
    primary_artist_id: str
    blueprint_id: str
    primary_genre: str
    content_rating: str = "mild"
    language: str = "en"
    alt_titles: list[str] | None = None
    subtitle: str | None = None
    version_type: str | None = None
    tempo_bpm: float | None = None
    key_camelot: str | None = None
    duration_seconds: int | None = None
    status: str = "draft"


class SongMasterPatchRequest(BaseModel):
    status: str | None = None
    isrc: str | None = None
    upc: str | None = None
    distributor: str | None = None
    distributor_work_id: str | None = None
    iswc: str | None = None
    actual_release_date: str | None = None  # ISO date
    scheduled_release_date: str | None = None


@router.post("/api/v1/admin/songs")
async def create_song_master(
    body: SongMasterCreateRequest,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Persist a new songs_master row (the canonical song record)."""
    import uuid as _uuid
    from api.models.songs_master import SongMaster

    try:
        artist_uuid = _uuid.UUID(body.primary_artist_id)
        blueprint_uuid = _uuid.UUID(body.blueprint_id)
    except ValueError:
        raise HTTPException(400, detail="invalid artist or blueprint id")

    row = SongMaster(
        title=body.title,
        primary_artist_id=artist_uuid,
        blueprint_id=blueprint_uuid,
        primary_genre=body.primary_genre,
        content_rating=body.content_rating,
        language=body.language,
        alt_titles=body.alt_titles,
        subtitle=body.subtitle,
        version_type=body.version_type,
        tempo_bpm=body.tempo_bpm,
        key_camelot=body.key_camelot,
        duration_seconds=body.duration_seconds,
        status=body.status,
    )
    db.add(row)
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(409, detail=f"song creation failed: {e}")
    await db.refresh(row)
    return _song_to_dict(row)


@router.get("/api/v1/admin/songs")
async def list_songs_master(
    status: str | None = None,
    primary_artist_id: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    from api.models.songs_master import SongMaster
    stmt = select(SongMaster).order_by(SongMaster.created_at.desc()).limit(min(limit, 200))
    if status:
        stmt = stmt.where(SongMaster.status == status)
    if primary_artist_id:
        import uuid as _uuid
        try:
            stmt = stmt.where(SongMaster.primary_artist_id == _uuid.UUID(primary_artist_id))
        except ValueError:
            raise HTTPException(400, detail="invalid primary_artist_id")
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {
        "songs": [_song_to_dict(r) for r in rows],
        "count": len(rows),
    }


@router.get("/api/v1/admin/songs/{song_id}")
async def get_song_master(
    song_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    import uuid as _uuid
    from sqlalchemy import text as _text
    from api.models.songs_master import SongMaster
    try:
        sid = _uuid.UUID(song_id)
    except ValueError:
        raise HTTPException(400, detail="invalid song_id")
    row = (await db.execute(
        select(SongMaster).where(SongMaster.song_id == sid)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, detail="song not found")

    # Attached audio_assets — pick the master candidate if there is one
    assets_result = await db.execute(
        _text("""
            SELECT asset_id, provider, provider_job_id, format, duration_seconds,
                   storage_url, is_master_candidate, loudness_lufs, created_at
            FROM audio_assets
            WHERE song_id = :sid
            ORDER BY is_master_candidate DESC, created_at DESC
        """),
        {"sid": sid},
    )
    audio_assets = [
        {
            "asset_id": str(a[0]),
            "provider": a[1],
            "provider_job_id": a[2],
            "format": a[3],
            "duration_seconds": a[4],
            "storage_url": a[5],
            "is_master_candidate": a[6],
            "loudness_lufs": a[7],
            "created_at": a[8].isoformat() if a[8] else None,
        }
        for a in assets_result.fetchall()
    ]

    # Attached artist stage_name + release title for display
    meta = (await db.execute(
        _text("""
            SELECT a.stage_name, r.title
            FROM songs_master s
            LEFT JOIN ai_artists a ON a.artist_id = s.primary_artist_id
            LEFT JOIN releases r ON r.id = s.release_id
            WHERE s.song_id = :sid
        """),
        {"sid": sid},
    )).fetchone()

    detail = _song_to_dict(row, full=True)
    detail["audio_assets"] = audio_assets
    detail["artist_name"] = meta[0] if meta else None
    detail["release_title"] = meta[1] if meta else None
    return detail


@router.patch("/api/v1/admin/songs/{song_id}")
async def patch_song_master(
    song_id: str,
    body: SongMasterPatchRequest,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    """Patch lifecycle fields on a song. Partial updates only."""
    import uuid as _uuid
    from datetime import date as _date
    from sqlalchemy.exc import IntegrityError
    from api.models.songs_master import SongMaster
    try:
        sid = _uuid.UUID(song_id)
    except ValueError:
        raise HTTPException(400, detail="invalid song_id")
    row = (await db.execute(
        select(SongMaster).where(SongMaster.song_id == sid)
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, detail="song not found")

    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if value is None:
            continue
        if key in ("actual_release_date", "scheduled_release_date"):
            value = _date.fromisoformat(value)
        setattr(row, key, value)

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        # Most likely: duplicate ISRC. Surface as 409 with the offending field.
        msg = str(e.orig) if e.orig else str(e)
        if "isrc" in msg.lower():
            raise HTTPException(409, detail=f"ISRC already in use: {body.isrc}")
        raise HTTPException(409, detail=f"integrity constraint violated: {msg[:200]}")
    await db.refresh(row)
    return _song_to_dict(row, full=True)


def _song_to_dict(row, full: bool = False) -> dict:
    base = {
        "song_id": str(row.song_id),
        "title": row.title,
        "primary_artist_id": str(row.primary_artist_id),
        "blueprint_id": str(row.blueprint_id),
        "primary_genre": row.primary_genre,
        "status": row.status,
        "isrc": row.isrc,
        "upc": row.upc,
        "iswc": row.iswc,
        "distributor": row.distributor,
        "actual_release_date": row.actual_release_date.isoformat() if row.actual_release_date else None,
        "primary_artwork_asset_id": str(row.primary_artwork_asset_id) if row.primary_artwork_asset_id else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    if not full:
        return base
    base.update({
        "internal_code": row.internal_code,
        "alt_titles": row.alt_titles,
        "subtitle": row.subtitle,
        "version_type": row.version_type,
        "content_rating": row.content_rating,
        "language": row.language,
        "subgenres": row.subgenres,
        "mood_tags": row.mood_tags,
        "tempo_bpm": row.tempo_bpm,
        "key_camelot": row.key_camelot,
        "duration_seconds": row.duration_seconds,
        "loudness_lufs": row.loudness_lufs,
        "energy": row.energy,
        "danceability": row.danceability,
        "valence": row.valence,
        "lyric_text": row.lyric_text,
        "lyric_themes": row.lyric_themes,
        "writers": row.writers,
        "publishers": row.publishers,
        "master_owner": row.master_owner,
        "copyright_year": row.copyright_year,
        "distributor_work_id": row.distributor_work_id,
        "territory_rights": row.territory_rights,
        "release_id": str(row.release_id) if row.release_id else None,
        "scheduled_release_date": row.scheduled_release_date.isoformat() if row.scheduled_release_date else None,
        "pre_save_date": row.pre_save_date.isoformat() if row.pre_save_date else None,
        "release_strategy": row.release_strategy,
        "marketing_hook": row.marketing_hook,
        "marketing_tags": row.marketing_tags,
        "playlist_fit": row.playlist_fit,
        "target_audience_tags": row.target_audience_tags,
        "pr_angle": row.pr_angle,
        "generation_provider": row.generation_provider,
        "generation_provider_job_id": row.generation_provider_job_id,
        "generation_cost_usd": row.generation_cost_usd,
        "regeneration_count": row.regeneration_count,
        "qa_pass": row.qa_pass,
        "duplication_risk_score": row.duplication_risk_score,
        "predicted_success_score": row.predicted_success_score,
        "predicted_stream_range_median": row.predicted_stream_range_median,
        "predicted_revenue_usd": row.predicted_revenue_usd,
        "actual_streams_lifetime": row.actual_streams_lifetime,
        "actual_revenue_usd": row.actual_revenue_usd,
        "outcome_label": row.outcome_label,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    })
    return base


@router.get("/api/v1/admin/ceo-decisions")
async def list_ceo_decisions(
    status: str | None = None,
    decision_type: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _admin: ApiKey = Depends(require_admin),
):
    from api.models.ceo_decision import CEODecision
    stmt = select(CEODecision).order_by(CEODecision.created_at.desc()).limit(min(limit, 200))
    if status:
        stmt = stmt.where(CEODecision.status == status)
    if decision_type:
        stmt = stmt.where(CEODecision.decision_type == decision_type)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {
        "decisions": [
            {
                "decision_id": str(r.decision_id),
                "decision_type": r.decision_type,
                "entity_type": r.entity_type,
                "entity_id": str(r.entity_id) if r.entity_id else None,
                "proposal": r.proposal,
                "data": r.data,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
        "count": len(rows),
    }
