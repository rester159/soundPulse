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
const EXTRACT_FEATURES_JS = `
(() => {
  const lines = (document.body.innerText || '').split('\\n').map(l => l.trim()).filter(Boolean);
  const features = {};
  const labels = new Set([
    'key','bpm','energy','danceability','happiness','acousticness',
    'instrumentalness','liveness','speechiness','loudness','popularity',
    'camelot','duration'
  ]);
  for (let i = 1; i < lines.length; i++) {
    const label = lines[i].toLowerCase();
    if (labels.has(label)) {
      features[label] = lines[i - 1];
    }
  }
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
  const out = {};
  if (raw.bpm) out.tempo = parseFloat(raw.bpm);
  if (raw.energy) out.energy = parseInt(raw.energy, 10) / 100;
  if (raw.danceability) out.danceability = parseInt(raw.danceability, 10) / 100;
  if (raw.happiness) out.valence = parseInt(raw.happiness, 10) / 100;
  if (raw.acousticness) out.acousticness = parseInt(raw.acousticness, 10) / 100;
  if (raw.instrumentalness) out.instrumentalness = parseInt(raw.instrumentalness, 10) / 100;
  if (raw.liveness) out.liveness = parseInt(raw.liveness, 10) / 100;
  if (raw.speechiness) out.speechiness = parseInt(raw.speechiness, 10) / 100;
  if (raw.loudness) out.loudness = parseFloat(raw.loudness);
  if (raw.key) {
    const keyMatch = raw.key.match(/^([A-G][#b]?)\s*(Major|Minor|maj|min)/i);
    if (keyMatch) {
      const keyMap = {
        C: 0, 'C#': 1, Db: 1, D: 2, 'D#': 3, Eb: 3, E: 4,
        F: 5, 'F#': 6, Gb: 6, G: 7, 'G#': 8, Ab: 8, A: 9,
        'A#': 10, Bb: 10, B: 11,
      };
      out.key = keyMap[keyMatch[1]] ?? null;
      out.mode = /maj/i.test(keyMatch[2]) ? 1 : 0;
    }
  }
  if (raw.duration) {
    const parts = raw.duration.split(':').map(Number);
    if (parts.length === 2) out.duration_ms = (parts[0] * 60 + parts[1]) * 1000;
    if (parts.length === 3) out.duration_ms = (parts[0] * 3600 + parts[1] * 60 + parts[2]) * 1000;
  }
  return out;
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

      const features = normalizeFeatures(raw);
      const count = Object.keys(features).length;
      console.log(`  ✓ ${count} features: tempo=${features.tempo} energy=${features.energy} valence=${features.valence} key=${features.key}`);
      enriched++;

      buffer.push({
        platform: 'tunebat',
        entity_type: 'track',
        entity_identifier: { spotify_id: spotifyId, title: title || '' },
        raw_score: null,
        rank: null,
        snapshot_date: today,
        signals: {
          audio_features: features,
          source_platform: 'tunebat',
          chart_type: 'audio_features_enrichment',
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
