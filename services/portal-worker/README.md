# portal-worker

SoundPulse downstream-portal submission worker. Runs as a **separate Railway service** from the main API. Polls the SoundPulse API for pending submissions, drives the external portals via [BlackTip](https://github.com/rester159/blacktip) (real Chrome + Cloudflare bypass), and posts results back.

## Architecture

```
┌─────────────────────┐              ┌─────────────────────────┐
│  SoundPulse API     │              │  portal-worker          │
│  (Python)           │   ← poll ──  │  (Node + BlackTip)      │
│                     │              │                         │
│  ascap_submissions  │  ─ claim →   │  worker.mjs             │
│  external_submissions│             │    loop:                │
│                     │  ← ack ──    │     claim-next          │
│  POST /worker/claim │              │     dispatch → portals/ │
│  POST /worker/ack   │              │     ack | fail          │
│  POST /worker/fail  │              │                         │
└─────────────────────┘              │  portals/               │
                                     │    ascap.mjs            │
                                     │    (more portals later) │
                                     └─────────────────────────┘
```

- API enqueues work: `ascap_submissions.status = 'pending'` or `external_submissions.status = 'pending'`
- Worker polls `POST /admin/worker/claim-next` which atomically claims one row via `SELECT ... FOR UPDATE SKIP LOCKED` (so parallel workers never step on each other)
- Worker dispatches to a portal-specific flow under `portals/`
- Worker posts back via `POST /admin/worker/ack` (success) or `POST /admin/worker/fail` (error, `retry=true` bounces it back to `pending`)

## Required env vars

| Var | Purpose |
|---|---|
| `SOUNDPULSE_API` | Base URL of the main API (default `http://localhost:8000`) |
| `API_ADMIN_KEY` | `X-API-Key` with admin privilege |
| `WORKER_ID` | Stable identifier for this worker instance (default: hostname) |
| `TARGET_SERVICES` | Comma-separated list of target_service ids to drain. Default `ascap` |
| `POLL_INTERVAL_MS` | Sleep between empty polls (default `30000`) |
| `PORTAL_MIN_DELAY_MS` | Delay between portal actions (default `1500`) |
| `ASCAP_USERNAME` | **Required if TARGET_SERVICES includes `ascap`** |
| `ASCAP_PASSWORD` | **Required if TARGET_SERVICES includes `ascap`** |

When more portals come online, add the corresponding `<PORTAL>_USERNAME` / `_PASSWORD` env vars.

## Adding a new portal

1. Create `portals/<portal_id>.mjs` exporting `runXFlow(claimedRow) → result` where result is `{status, external_id, response, screenshot_b64?}`
2. Import it in `worker.mjs` and add to `PORTAL_FLOWS` registry
3. Set the portal creds on Railway env
4. Update `TARGET_SERVICES` to include the new target_service id

Each portal file can use BlackTip freely — real Chrome, stealth, Cloudflare bypass, file upload via the standard Playwright API.

## Local dev

```bash
cd services/portal-worker
npm install  # will fail — black-tip is /opt/blacktip in container
# For local testing, either run inside Docker or point black-tip at a local clone
```

For actual local runs, build the Dockerfile and `docker run` with the env vars set.

## Running under Xvfb

BlackTip runs a real visible Chrome. `start.sh` launches `Xvfb :99` before starting the worker so Chrome has a display even on a headless Railway container.
