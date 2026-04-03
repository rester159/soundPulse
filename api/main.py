from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.middleware.rate_limiter import RateLimitMiddleware
from api.config import get_settings
from api.routers import admin, assistant, backtesting, blueprint, genres, predictions, search, trending


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start scraper scheduler
    try:
        from scrapers.scheduler import init_scheduler, shutdown_scheduler
        settings = get_settings()
        await init_scheduler(settings.database_url)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Scheduler startup failed: %s", e, exc_info=True)

    yield

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

# Middleware
app.add_middleware(RateLimitMiddleware)

# Routers
app.include_router(genres.router)
app.include_router(trending.router)
app.include_router(search.router)
app.include_router(predictions.router)
app.include_router(admin.router)
app.include_router(backtesting.router)
app.include_router(blueprint.router)
app.include_router(assistant.router)


@app.get("/")
async def root():
    return {"service": "SoundPulse API", "version": "0.1.0", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "ok"}


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
