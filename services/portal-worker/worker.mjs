/**
 * SoundPulse portal-worker — main loop.
 *
 * Polls /admin/worker/claim-next for pending submissions, dispatches
 * to a portal-specific flow under ./portals/, posts the result back
 * via /admin/worker/ack or /admin/worker/fail.
 *
 * Usage (env):
 *   SOUNDPULSE_API        — base URL of the SoundPulse API
 *                           (https://soundpulse-production-5266.up.railway.app)
 *   API_ADMIN_KEY         — X-API-Key with admin privilege
 *   WORKER_ID             — stable identifier for this worker (defaults to hostname)
 *   TARGET_SERVICES       — comma-separated list of target_service ids
 *                           to drain. Default: 'ascap'. When we add more
 *                           portals: 'ascap,distrokid,bmi'
 *   POLL_INTERVAL_MS      — sleep between empty polls (default 30000)
 *   PORTAL_MIN_DELAY_MS   — min delay between portal actions to avoid
 *                           tripping anti-automation heuristics
 *
 * Per portal, the real credentials live in this service's env:
 *   ascap        → ASCAP_USERNAME, ASCAP_PASSWORD
 *   distrokid    → DISTROKID_USERNAME, DISTROKID_PASSWORD
 *   (etc — one pair per portal, provisioned on Railway as each portal
 *   flow gets implemented)
 */

import os from 'node:os';
import { runAscapFlow } from './portals/ascap.mjs';
import { runWebResearchFlow } from './portals/web_research.mjs';

const API_BASE = (process.env.SOUNDPULSE_API || 'http://localhost:8000').replace(/\/$/, '');
const API_KEY = process.env.API_ADMIN_KEY || '';
const WORKER_ID = process.env.WORKER_ID || os.hostname() || 'portal-worker-unknown';
// Default target list now includes web_research (#31) so a fresh
// portal-worker instance picks up genre research jobs out of the box.
const TARGET_SERVICES = (process.env.TARGET_SERVICES || 'ascap,web_research')
  .split(',').map(s => s.trim()).filter(Boolean);
const POLL_INTERVAL_MS = parseInt(process.env.POLL_INTERVAL_MS || '30000', 10);

if (!API_KEY) {
  console.error('[portal-worker] FATAL: API_ADMIN_KEY env var is required');
  process.exit(1);
}

// Registry — one portal flow per target_service. Add entries here as
// new portals come online. Each flow is (claimedRow) => {status, external_id, response, screenshot_b64?}
const PORTAL_FLOWS = {
  ascap: runAscapFlow,
  web_research: runWebResearchFlow,
};

function log(...args) {
  const ts = new Date().toISOString();
  console.log(`[portal-worker ${ts}]`, ...args);
}

async function apiRequest(method, path, body) {
  const url = `${API_BASE}${path}`;
  const options = {
    method,
    headers: {
      'X-API-Key': API_KEY,
      'Content-Type': 'application/json',
    },
  };
  if (body !== undefined) {
    options.body = JSON.stringify(body);
  }
  const resp = await fetch(url, options);
  const text = await resp.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }
  if (!resp.ok) {
    throw new Error(`API ${method} ${path} → ${resp.status}: ${text.slice(0, 300)}`);
  }
  return data;
}

async function claimNext(targetService) {
  try {
    const res = await apiRequest('POST', '/api/v1/admin/worker/claim-next', {
      target_service: targetService,
      worker_id: WORKER_ID,
    });
    return res?.claimed || null;
  } catch (e) {
    log(`claim-next ${targetService} failed:`, e.message);
    return null;
  }
}

async function ack(submissionId, targetService, payload) {
  const qs = targetService ? `?target_service=${encodeURIComponent(targetService)}` : '';
  return apiRequest('POST', `/api/v1/admin/worker/ack/${submissionId}${qs}`, payload);
}

async function fail(submissionId, targetService, error, retry = true) {
  const qs = targetService ? `?target_service=${encodeURIComponent(targetService)}` : '';
  return apiRequest('POST', `/api/v1/admin/worker/fail/${submissionId}${qs}`, {
    error: String(error).slice(0, 1000),
    retry,
  });
}

async function handleOne(claimed) {
  const targetService = claimed.target_service;
  const submissionId = claimed.submission_id;
  const flow = PORTAL_FLOWS[targetService];
  if (!flow) {
    log(`no flow registered for ${targetService}, marking failed`);
    await fail(submissionId, targetService, `no portal flow registered for ${targetService}`, false);
    return;
  }

  log(`claimed ${targetService} submission ${submissionId}`);
  try {
    const result = await flow(claimed);
    if (result?.status === 'failed') {
      await fail(submissionId, targetService, result.error || 'flow returned failed', result.retry !== false);
      log(`FAIL  ${targetService} ${submissionId}: ${result.error}`);
    } else {
      await ack(submissionId, targetService, {
        external_id: result.external_id || null,
        response: result.response || {},
        screenshot_b64: result.screenshot_b64 || null,
        status: result.status || 'submitted',
      });
      log(`OK    ${targetService} ${submissionId} → ${result.external_id || '(no id)'}`);
    }
  } catch (e) {
    log(`ERROR ${targetService} ${submissionId}:`, e.message);
    try {
      await fail(submissionId, targetService, e.message || String(e), true);
    } catch (e2) {
      log(`fail post-back also errored:`, e2.message);
    }
  }
}

async function mainLoop() {
  log(`starting worker ${WORKER_ID} — targets: ${TARGET_SERVICES.join(', ')}`);
  log(`API base: ${API_BASE}`);
  log(`registered flows: ${Object.keys(PORTAL_FLOWS).join(', ') || '(none)'}`);

  while (true) {
    let didWork = false;
    for (const svc of TARGET_SERVICES) {
      const claimed = await claimNext(svc);
      if (claimed) {
        didWork = true;
        await handleOne(claimed);
      }
    }
    if (!didWork) {
      await new Promise(r => setTimeout(r, POLL_INTERVAL_MS));
    }
  }
}

mainLoop().catch(e => {
  log('FATAL main loop crash:', e);
  process.exit(1);
});
