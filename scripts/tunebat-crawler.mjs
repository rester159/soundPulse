/**
 * Tunebat audio-features crawler — powered by BlackTip.
 *
 * Continuously enriches SoundPulse tracks with full Spotify audio features
 * (energy, danceability, valence, key, etc.) by scraping Tunebat pages.
 * BlackTip bypasses Cloudflare automatically via real Chrome + stealth.
 *
 * Usage:
 *   SOUNDPULSE_API=https://soundpulse-production-5266.up.railway.app \
 *   API_ADMIN_KEY=sp_admin_... \
 *   node scripts/tunebat-crawler.mjs
 *
 * Requires BlackTip installed at ../blacktip (sibling directory).
 * The crawler runs indefinitely. Ctrl+C to stop.
 */
import { BlackTip } from '../../blacktip/dist/index.js';

// ---- Config from env ----
const API_BASE = process.env.SOUNDPULSE_API || 'http://localhost:8000';
const API_KEY = process.env.API_ADMIN_KEY || '';
const BATCH_SIZE = parseInt(process.env.BATCH_SIZE || '50', 10);
const PAGE_DELAY_MS = parseInt(process.env.PAGE_DELAY_MS || '6000', 10);
const LOOP_SLEEP_MS = parseInt(process.env.LOOP_SLEEP_MS || '3600000', 10);
const CF_WAIT_MS = 2000;
const CF_MAX_TICKS = 15;
const POST_CF_RENDER_MS = 2000;

if (!API_KEY) {
  console.error('ERROR: API_ADMIN_KEY env var is required');
  process.exit(1);
}

// ---- Feature extraction JS (runs inside browser context) ----
// Extract ALL useful metadata from a Tunebat track page.
// Tunebat's layout: value appears on the line BEFORE its label.
// Stop at "Recommendations" to avoid the harmonic-mixing table
// which reuses the same label words.
// Also grab release_date, explicit, album from the mid-section text.
const EXTRACT_FEATURES_JS = `
(() => {
  const text = document.body.innerText || '';
  const cutoff = text.indexOf('Recommendations');
  const relevant = cutoff > 0 ? text.substring(0, cutoff) : text;
  const lines = relevant.split('\\n').map(l => l.trim()).filter(Boolean);

  const features = {};
  const labels = new Set([
    'key','bpm','energy','danceability','happiness','acousticness',
    'instrumentalness','liveness','speechiness','loudness','popularity',
    'camelot','duration'
  ]);
  for (let i = 1; i < lines.length; i++) {
    const label = lines[i].toLowerCase();
    if (labels.has(label) && !(label in features)) {
      features[label] = lines[i - 1];
    }
  }

  // Release date, explicit, album — appear as "Release Date: X", "Explicit: Y", "Album: Z"
  const rdMatch = relevant.match(/Release Date:\\s*(.+?)(?:\\n|$)/i);
  if (rdMatch) features.release_date = rdMatch[1].trim();
  const exMatch = relevant.match(/Explicit:\\s*(Yes|No)/i);
  if (exMatch) features.explicit = exMatch[1].trim();
  const alMatch = relevant.match(/Album:\\s*(.+?)(?:\\n|$)/i);
  if (alMatch) features.album = alMatch[1].trim();

  return features;
})()
`;

// ---- Helpers ----
function slugify(title, artist) {
  return [title, artist]
    .filter(Boolean)
    .join('-')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .substring(0, 100);
}

function normalizeFeatures(raw) {
  // audio_features: the canonical Spotify shape (0-1 scale for most fields)
  const audio = {};
  if (raw.bpm) audio.tempo = parseFloat(raw.bpm);
  if (raw.energy) audio.energy = parseInt(raw.energy, 10) / 100;
  if (raw.danceability) audio.danceability = parseInt(raw.danceability, 10) / 100;
  if (raw.happiness) audio.valence = parseInt(raw.happiness, 10) / 100;
  if (raw.acousticness) audio.acousticness = parseInt(raw.acousticness, 10) / 100;
  if (raw.instrumentalness) audio.instrumentalness = parseInt(raw.instrumentalness, 10) / 100;
  if (raw.liveness) audio.liveness = parseInt(raw.liveness, 10) / 100;
  if (raw.speechiness) audio.speechiness = parseInt(raw.speechiness, 10) / 100;
  if (raw.loudness) audio.loudness = parseFloat(raw.loudness);
  if (raw.key) {
    // Tunebat uses Unicode ♯ (U+266F) and ♭ (U+266D) instead of # and b
    const normalized = raw.key.replace(/♯/g, '#').replace(/♭/g, 'b');
    const keyMatch = normalized.match(/^([A-G][#b]?)\s*(Major|Minor|maj|min)/i);
    if (keyMatch) {
      const keyMap = {
        C: 0, 'C#': 1, Db: 1, D: 2, 'D#': 3, Eb: 3, E: 4,
        F: 5, 'F#': 6, Gb: 6, G: 7, 'G#': 8, Ab: 8, A: 9,
        'A#': 10, Bb: 10, B: 11,
      };
      audio.key = keyMap[keyMatch[1]] ?? null;
      audio.mode = /maj/i.test(keyMatch[2]) ? 1 : 0;
    }
  }
  if (raw.duration) {
    const parts = raw.duration.split(':').map(Number);
    if (parts.length === 2) audio.duration_ms = (parts[0] * 60 + parts[1]) * 1000;
    if (parts.length === 3) audio.duration_ms = (parts[0] * 3600 + parts[1] * 60 + parts[2]) * 1000;
  }

  // Extra metadata beyond audio_features — stored in signals alongside
  // audio_features so the ingest path can route them appropriately.
  const meta = {};
  if (raw.key) meta.key_display = raw.key;  // human-readable "C# Major"
  if (raw.camelot) meta.camelot = raw.camelot;
  if (raw.popularity) meta.tunebat_popularity = parseInt(raw.popularity, 10);
  if (raw.release_date) meta.release_date = raw.release_date;
  if (raw.explicit) meta.explicit = raw.explicit.toLowerCase() === 'yes';
  if (raw.album) meta.album = raw.album;

  return { audio, meta };
}

async function fetchQueue() {
  const url = `${API_BASE}/api/v1/admin/tracks/needing-audio-features?limit=${BATCH_SIZE}`;
  try {
    const resp = await fetch(url, { headers: { 'X-API-Key': API_KEY } });
    if (!resp.ok) {
      console.error(`[queue] HTTP ${resp.status}`);
      return [];
    }
    return (await resp.json()).data || [];
  } catch (err) {
    console.error(`[queue] ${err.message}`);
    return [];
  }
}

async function postFeatures(items) {
  if (!items.length) return;
  try {
    const resp = await fetch(`${API_BASE}/api/v1/trending/bulk`, {
      method: 'POST',
      headers: { 'X-API-Key': API_KEY, 'Content-Type': 'application/json' },
      body: JSON.stringify({ items }),
    });
    if (resp.ok) {
      const d = (await resp.json()).data || {};
      console.log(`[post] ingested=${d.ingested} dupes=${d.duplicates} errors=${d.errors}`);
    } else {
      console.error(`[post] HTTP ${resp.status}`);
    }
  } catch (err) {
    console.error(`[post] ${err.message}`);
  }
}

async function crawlBatch(bt, tracks) {
  const buffer = [];
  const today = new Date().toISOString().split('T')[0];
  let enriched = 0;
  let skipped = 0;
  let errors = 0;

  for (let i = 0; i < tracks.length; i++) {
    const { spotify_id: spotifyId, title, track_id: trackId } = tracks[i];
    if (!spotifyId) { skipped++; continue; }

    const slug = slugify(title || 'track', '');
    const url = `https://tunebat.com/Info/${slug}/${spotifyId}`;
    console.log(`[${i + 1}/${tracks.length}] ${(title || '').substring(0, 40)} → ${spotifyId}`);

    try {
      await bt.navigate(url);

      // Wait for Cloudflare to clear
      let loaded = false;
      for (let tick = 0; tick < CF_MAX_TICKS; tick++) {
        await new Promise(r => setTimeout(r, CF_WAIT_MS));
        try {
          const pageTitle = await bt.executeJS('document.title');
          if (pageTitle && !pageTitle.includes('Just a moment')) {
            loaded = true;
            break;
          }
        } catch { /* context destroyed during redirect */ }
      }

      if (!loaded) {
        console.log(`  skip: Cloudflare timeout`);
        skipped++;
        continue;
      }

      await new Promise(r => setTimeout(r, POST_CF_RENDER_MS));

      const raw = await bt.executeJS(EXTRACT_FEATURES_JS);
      if (!raw || Object.keys(raw).length < 3) {
        console.log(`  skip: <3 features extracted`);
        skipped++;
        continue;
      }

      const { audio, meta } = normalizeFeatures(raw);
      const count = Object.keys(audio).length;
      console.log(`  ✓ ${count} audio features + ${Object.keys(meta).length} meta: tempo=${audio.tempo} energy=${audio.energy} valence=${audio.valence} key=${meta.key_display} camelot=${meta.camelot}`);
      enriched++;

      buffer.push({
        platform: 'spotify',
        entity_type: 'track',
        entity_identifier: { spotify_id: spotifyId, title: title || '' },
        snapshot_date: today,
        signals: {
          audio_features: audio,
          source_platform: 'tunebat',
          chart_type: 'audio_features_enrichment',
          // Extra metadata alongside audio_features
          tunebat_popularity: meta.tunebat_popularity,
          camelot: meta.camelot,
          key_display: meta.key_display,
          release_date: meta.release_date,
          explicit: meta.explicit,
          album: meta.album,
        },
      });

      if (buffer.length >= 20) {
        await postFeatures(buffer.splice(0));
      }
    } catch (err) {
      console.error(`  ✗ ${err.message?.substring(0, 80)}`);
      errors++;
    }

    await new Promise(r => setTimeout(r, PAGE_DELAY_MS));
  }

  if (buffer.length > 0) {
    await postFeatures(buffer.splice(0));
  }

  console.log(`[batch] enriched=${enriched} skipped=${skipped} errors=${errors}`);
}

// ---- Main loop ----
async function main() {
  const bt = new BlackTip({
    headless: false,
    logLevel: 'warn',
    deviceProfile: 'desktop-windows',
    behaviorProfile: 'scraper',
    timeout: 30000,
    retryAttempts: 2,
    screenResolution: { width: 1440, height: 900 },
  });

  console.log('[init] launching BlackTip...');
  await bt.launch();
  console.log('[init] ready');
  console.log(`[init] API: ${API_BASE} | batch: ${BATCH_SIZE} | delay: ${PAGE_DELAY_MS}ms`);

  while (true) {
    console.log(`\n[loop] fetching queue...`);
    const tracks = await fetchQueue();

    if (tracks.length === 0) {
      console.log(`[loop] queue empty, sleeping ${LOOP_SLEEP_MS / 60000} min...`);
      await new Promise(r => setTimeout(r, LOOP_SLEEP_MS));
      continue;
    }

    console.log(`[loop] ${tracks.length} tracks`);
    await crawlBatch(bt, tracks);
  }
}

main().catch(err => { console.error('[fatal]', err); process.exit(1); });
