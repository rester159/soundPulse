import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.middleware.rate_limiter import RateLimitMiddleware
from api.config import get_settings
from api.routers import admin, admin_genre_structures, assistant, backtesting, blueprint, genres, instrumentals_public, predictions, search, trending

# Record when this process started — proxy for "when was this code deployed"
_PROCESS_STARTED_AT = datetime.now(timezone.utc).isoformat()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging
    log = logging.getLogger(__name__)

    # AUD-036/037: security check runs here (not at import time). Logs a
    # CRITICAL warning if running in production with default keys but does
    # not raise, so the app still boots. L005: previous implementation
    # raised at import time and caused 4 consecutive deploys to fail.
    try:
        from api.config import InsecureDefaultError
        settings = get_settings()
        try:
            settings.assert_secure_in_production()
        except InsecureDefaultError as exc:
            log.critical("[SECURITY] %s", exc)
    except Exception as e:
        log.warning("Security check skipped: %s", e)

    # Start scraper scheduler
    try:
        from scrapers.scheduler import init_scheduler, shutdown_scheduler
        settings = get_settings()
        await init_scheduler(settings.database_url)
    except Exception as e:
        log.warning("Scheduler startup failed: %s", e, exc_info=True)

    # Stage 3 Phase A: spawn the single Chartmetric fetcher. Runs in
    # dry-mode unless CHARTMETRIC_FETCHER_DRY_MODE=0 is set.
    try:
        from chartmetric_ingest import runner as cm_runner
        await cm_runner.start()
    except Exception as e:
        log.warning("Chartmetric fetcher startup failed: %s", e, exc_info=True)

    yield

    # Shutdown Chartmetric fetcher
    try:
        from chartmetric_ingest import runner as cm_runner
        await cm_runner.stop()
    except Exception:
        pass

    # Shutdown scheduler
    try:
        from scrapers.scheduler import shutdown_scheduler
        shutdown_scheduler()
    except Exception:
        pass


app = FastAPI(
    title="SoundPulse API",
    description="Music intelligence API — trending data, predictions, and genre taxonomy",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow all origins (API is protected by API key, not origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware
app.add_middleware(RateLimitMiddleware)

# Routers
app.include_router(genres.router)
app.include_router(trending.router)
app.include_router(search.router)
app.include_router(predictions.router)
app.include_router(admin.router)
app.include_router(admin_genre_structures.router)  # task #109 Phase 3
app.include_router(backtesting.router)
app.include_router(blueprint.router)
app.include_router(assistant.router)
app.include_router(instrumentals_public.router)

# Import marketing_agents so its @register_adapter decorators run
# and the press_release + social_media adapters replace the stubs.
from api.services import marketing_agents  # noqa: F401
# Import submission_adapters package so each adapter module's
# @register_adapter decorator fires at boot.
from api.services import submission_adapters  # noqa: F401


@app.get("/")
async def root():
    return {"service": "SoundPulse API", "version": "0.1.0", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/v1/version")
async def version():
    """
    Deployment identity for the running process.

    Railway sets RAILWAY_GIT_COMMIT_SHA automatically on every deploy.
    `deployed_at` is the UTC timestamp when this API process started —
    close-enough proxy for "when was this version deployed".
    Frontend displays the short commit + timestamp in the top-right badge
    so deploy staleness is visible at a glance.
    """
    commit_full = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "")
    return {
        "commit": commit_full[:12] if commit_full else "dev",
        "commit_full": commit_full or "dev",
        "deployed_at": _PROCESS_STARTED_AT,
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "deploy_id": os.environ.get("RAILWAY_DEPLOYMENT_ID", "")[:12],
        "branch": os.environ.get("RAILWAY_GIT_BRANCH", "main"),
        "service": os.environ.get("RAILWAY_SERVICE_NAME", "local"),
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"error": str(exc)} if True else {},
            }
        },
    )
