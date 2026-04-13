# stem-extractor

SoundPulse microservice that runs Demucs + ffmpeg to:
1. Separate vocals from a Suno `add-vocals` output
2. Mix the isolated vocals onto the user's ORIGINAL uploaded instrumental
3. Post all three stems (plus optional drums/bass/other) back to the API

Runs as a separate Railway service. Polls the main API for pending jobs.

## Why this exists

Kie.ai's Suno `add-vocals` endpoint doesn't lock to the uploaded audio — it analyzes the instrumental, **recreates** a similar backing track, and sings on top. The final MP3 Suno returns is "similar but not the same" as the user's upload. This service fixes that by extracting the vocal stem from Suno's output and laying it onto the user's real instrumental via ffmpeg.

See PRD §25 Audio QA + §27 for context.

## Architecture

```
┌─────────────────────┐              ┌──────────────────────────┐
│  SoundPulse API     │              │  stem-extractor          │
│  (Python/FastAPI)   │  ← poll ───  │  (Python + Demucs)       │
│                     │              │                          │
│  song_stem_jobs     │  ─ claim →   │  worker.py               │
│  song_stems         │              │    loop:                 │
│                     │  ← ack ──    │     claim-next           │
│  POST /stem-claim   │              │     download suno + instr│
│  POST /stem-ack     │              │     demucs htdemucs      │
│  POST /stem-fail    │              │     ffmpeg mix           │
└─────────────────────┘              │     ack back             │
                                     └──────────────────────────┘
```

## Required env vars

| Var | Purpose |
|---|---|
| `SOUNDPULSE_API` | Base URL of the main API (e.g. `https://soundpulse-production-5266.up.railway.app`) |
| `API_ADMIN_KEY` | `X-API-Key` with admin privilege |
| `WORKER_ID` | Stable id (default hostname) |
| `POLL_INTERVAL_SEC` | Sleep between empty polls (default 30) |
| `DEMUCS_MODEL` | Demucs model name (default `htdemucs` — hybrid transformer) |
| `STEM_STORE_EXTRAS` | Set to `1` to also store drums/bass/other stems (default `0`) |

## How the mix works

1. Download Suno's output MP3 (the reinterpreted track)
2. Download user's original instrumental MP3 from `/api/v1/instrumentals/public/{uuid}.mp3`
3. Run `python -m demucs -n htdemucs --mp3 suno.mp3` → produces `vocals.mp3`, `drums.mp3`, `bass.mp3`, `other.mp3` in `demucs_out/htdemucs/suno/`
4. `ffmpeg -i vocals.mp3 -i instrumental.mp3 -filter_complex [0:a]volume=1.25[v];[1:a]volume=1.0[i];[v][i]amix=inputs=2:duration=longest[out] -map [out] -ac 2 -b:a 192k final_mixed.mp3`
5. Base64-encode `suno.mp3`, `vocals.mp3`, and `final_mixed.mp3` and POST to `/api/v1/admin/worker/stem-ack/{job_id}`

The vocal is boosted +2dB relative to the instrumental to sit on top without fighting the beat. Adjust the `volume=` filter in `worker.py::_ffmpeg_mix` if the mix comes out muddy or bright.

## Performance

On Railway's default Dockerfile container (CPU-only PyTorch 2.2, htdemucs model, ~3-minute track):
- Download step: 2-5 seconds
- Demucs separation: ~90-180 seconds
- ffmpeg mix: 3-5 seconds
- Total per job: ~2-3 minutes

The model weights are pre-downloaded at Docker build time (~500 MB) so the first job after a cold start doesn't pay the download cost.

## Storage footprint per song

Each `song_stems` row carries a BYTEA blob directly in Postgres:
- `suno_original`: ~2-4 MB (full Suno mp3)
- `vocals_only`: ~1-2 MB (isolated vocals)
- `final_mixed`: ~2-4 MB (mixed output)
- With `STEM_STORE_EXTRAS=1`: +3 × ~2 MB (drums, bass, other)

So ~6-10 MB per song baseline, ~12-16 MB with extras. For a 1000-song catalog that's ~10-15 GB — Neon handles it fine.

## Adding more stem-producing flows

Any song that ends up with a row in `song_stem_jobs` gets processed. To trigger extraction on a new generation path, call `_enqueue_stem_job_if_needed(db, song_id, music_generation_call_id, source_audio_url)` from wherever the song hits status `succeeded`.

Today only the instrumental-backed generation path triggers stem extraction (detected via `music_generation_calls.params_json.uploadUrl`). Text-only generations skip it since there's no user instrumental to mix against.
