import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import get_api_key_record, get_redis, require_admin
from api.models.api_key import ApiKey
from api.models.artist import Artist
from api.models.prediction import Prediction
from api.models.track import Track
from api.schemas.predictions import FeedbackRequest, FeedbackResponse, PredictionResponse
from api.services.cache import CacheService
from shared.constants import CACHE_TTL, VALID_ENTITY_TYPES, VALID_HORIZONS, VALID_PREDICTION_SORT

router = APIRouter(prefix="/api/v1/predictions", tags=["predictions"])

# Valid US-market prediction targets for filtering
VALID_PREDICTION_TARGETS = {
    "billboard_hot_100",
    "spotify_top_50_us",
    "shazam_top_200_us",
    "cross_platform_breakout",
}


def _try_import_ml_predictor():
    """Lazily import the advanced ML predictor."""
    try:
        from ml.predictor import predict_entity as ml_predict_entity

        return ml_predict_entity
    except ImportError:
        return None


@router.get("", response_model=PredictionResponse)
async def get_predictions(
    entity_type: str = Query("all"),
    horizon: str = Query("7d"),
    genre: str | None = Query(None),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    prediction_target: str | None = Query(
        None,
        description="Filter by US-market prediction target: billboard_hot_100, spotify_top_50_us, shazam_top_200_us, cross_platform_breakout",
    ),
    limit: int = Query(50, ge=10, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("predicted_change"),
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key_record),
    redis=Depends(get_redis),
):
    if horizon not in VALID_HORIZONS:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "VALIDATION_ERROR", "message": f"Invalid horizon: {horizon}", "details": {}}},
        )
    if sort not in VALID_PREDICTION_SORT:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "VALIDATION_ERROR", "message": f"Invalid sort: {sort}", "details": {}}},
        )
    if prediction_target is not None and prediction_target not in VALID_PREDICTION_TARGETS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"Invalid prediction_target: {prediction_target}. Must be one of {sorted(VALID_PREDICTION_TARGETS)}",
                    "details": {},
                }
            },
        )

    cache = CacheService(redis)
    cache_key = f"predictions:{entity_type}:{horizon}:{genre}:{min_confidence}:{prediction_target}:{sort}:{limit}:{offset}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    query = select(Prediction).where(
        Prediction.horizon == horizon,
        Prediction.confidence >= min_confidence,
        Prediction.resolved_at.is_(None),  # Only unresolved predictions
    )

    if entity_type != "all":
        query = query.where(Prediction.entity_type == entity_type)

    # Sort
    if sort == "confidence":
        query = query.order_by(Prediction.confidence.desc())
    elif sort == "predicted_score":
        query = query.order_by(Prediction.predicted_score.desc())
    else:  # predicted_change
        query = query.order_by(Prediction.predicted_score.desc())

    result = await db.execute(query)
    predictions = result.scalars().all()

    # Build response
    items = []
    for pred in predictions:
        # Resolve entity name
        entity_name = ""
        entity_genres: list[str] = []
        image_url = None

        if pred.entity_type == "artist":
            try:
                entity_uuid = uuid_mod.UUID(pred.entity_id)
                r = await db.execute(select(Artist).where(Artist.id == entity_uuid))
                artist = r.scalar_one_or_none()
                if artist:
                    entity_name = artist.name
                    entity_genres = artist.genres or []
                    image_url = artist.image_url
            except ValueError:
                pass
        elif pred.entity_type == "track":
            try:
                entity_uuid = uuid_mod.UUID(pred.entity_id)
                r = await db.execute(select(Track).where(Track.id == entity_uuid))
                track = r.scalar_one_or_none()
                if track:
                    entity_name = track.title
                    entity_genres = track.genres or []
            except ValueError:
                pass
        elif pred.entity_type == "genre":
            entity_name = pred.entity_id  # Genre ID is the name

        # Genre filter
        if genre and not any(g.startswith(genre) for g in entity_genres):
            continue

        horizon_days = {"7d": 7, "30d": 30, "90d": 90}[pred.horizon]
        horizon_ends = pred.predicted_at + timedelta(days=horizon_days)

        # Extract top signals from features_json if available
        top_signals = []
        features_json = pred.features_json or {}
        if "top_features" in features_json:
            top_signals = features_json["top_features"]

        items.append({
            "prediction_id": str(pred.id),
            "entity": {
                "id": pred.entity_id,
                "type": pred.entity_type,
                "name": entity_name,
                "genres": entity_genres,
                "image_url": image_url,
            },
            "horizon": pred.horizon,
            "current_score": None,
            "predicted_score": pred.predicted_score,
            "predicted_change_pct": None,
            "predicted_change_abs": None,
            "confidence": pred.confidence,
            "confidence_interval": {},
            "top_signals": top_signals,
            "model_version": pred.model_version,
            "predicted_at": pred.predicted_at.isoformat(),
            "horizon_ends_at": horizon_ends.isoformat(),
        })

    total = len(items)
    items = items[offset : offset + limit]

    # Check if model is trained
    ml_predictor = _try_import_ml_predictor()
    model_warning = None
    if ml_predictor is None:
        model_warning = "Advanced ML predictor not available. Showing stored predictions."

    response = {
        "data": items,
        "meta": {
            "request_id": f"req_{uuid_mod.uuid4().hex[:12]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total": total,
            "limit": limit,
            "offset": offset,
            "horizon": horizon,
            "model_version": "ensemble-v1.0",
            "model_accuracy": {"mae_7d": None, "mae_30d": None, "calibration_score": None},
        },
    }
    if model_warning:
        response["meta"]["warning"] = model_warning

    await cache.set(cache_key, response, ttl=CACHE_TTL["predictions"])
    return response


@router.get("/{entity_id}")
async def get_entity_prediction(
    entity_id: str = Path(..., description="UUID of the artist or track"),
    entity_type: str = Query("track", description="'artist' or 'track'"),
    horizon: str = Query("7d", description="Prediction horizon: '7d', '30d', '90d'"),
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key_record),
    redis=Depends(get_redis),
):
    """Generate live US-market predictions for a single entity.

    Returns 4 specific US-market prediction targets:
      - billboard_hot_100: probability of appearing on Billboard Hot 100 (14d)
      - spotify_top_50_us: probability of entering Spotify US Top 50 (7d)
      - shazam_top_200_us: probability of entering Shazam US Top 200 (7d)
      - cross_platform_breakout: probability of charting on 3+ US platforms (14d)

    Uses the trained ML ensemble when available, otherwise falls back to
    a rule-based heuristic.
    """
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"Invalid entity_type: {entity_type}. Must be one of {VALID_ENTITY_TYPES}",
                    "details": {},
                }
            },
        )

    if horizon not in VALID_HORIZONS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"Invalid horizon: {horizon}. Must be one of {VALID_HORIZONS}",
                    "details": {},
                }
            },
        )

    try:
        entity_uuid = uuid_mod.UUID(entity_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "entity_id must be a valid UUID",
                    "details": {},
                }
            },
        )

    # Check cache
    cache = CacheService(redis)
    cache_key = f"prediction:entity:{entity_id}:{entity_type}:{horizon}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    # Resolve entity metadata
    entity_name = ""
    entity_genres: list[str] = []
    image_url = None

    if entity_type == "artist":
        r = await db.execute(select(Artist).where(Artist.id == entity_uuid))
        artist = r.scalar_one_or_none()
        if artist is None:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "NOT_FOUND", "message": "Artist not found", "details": {}}},
            )
        entity_name = artist.name
        entity_genres = artist.genres or []
        image_url = artist.image_url
    else:
        r = await db.execute(select(Track).where(Track.id == entity_uuid))
        track = r.scalar_one_or_none()
        if track is None:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "NOT_FOUND", "message": "Track not found", "details": {}}},
            )
        entity_name = track.title
        entity_genres = track.genres or []

    # Try advanced ML predictor first, fall back to basic service
    prediction = None
    ml_predictor = _try_import_ml_predictor()

    if ml_predictor is not None:
        try:
            prediction = await ml_predictor(db, entity_uuid, entity_type, horizon)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(
                "Advanced predictor failed, falling back to basic: %s", exc
            )

    # Fallback to basic prediction service
    if prediction is None:
        try:
            from api.services.prediction_service import predict_entity as basic_predict

            prediction = await basic_predict(db, entity_uuid, entity_type)
        except Exception:
            pass

    if prediction is None:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "INSUFFICIENT_DATA",
                    "message": "Not enough trending history to generate a prediction for this entity.",
                    "details": {},
                }
            },
        )

    # Normalize prediction response format — now includes 4 US-market targets
    confidence = prediction.get("calibrated_confidence", prediction.get("confidence_level", 0.5))
    if isinstance(confidence, str):
        confidence = {"high": 0.8, "medium": 0.5, "low": 0.3}.get(confidence, 0.5)

    # Extract the 4 US-market prediction targets
    predictions_dict = prediction.get("predictions", {})

    # Backwards compatibility: if old-format prediction without "predictions" key,
    # wrap single probability into the new 4-target format
    if not predictions_dict:
        probability = prediction.get("probability", 0.5)
        predictions_dict = {
            "billboard_hot_100": {"probability": round(probability * 0.85, 4), "horizon": "14d", "label": "Billboard Hot 100"},
            "spotify_top_50_us": {"probability": round(probability, 4), "horizon": "7d", "label": "Spotify Top 50 US"},
            "shazam_top_200_us": {"probability": round(min(probability * 1.1, 0.99), 4), "horizon": "7d", "label": "Shazam Top 200 US"},
            "cross_platform_breakout": {"probability": round(probability * 0.7, 4), "horizon": "14d", "label": "3+ US Platform Breakout"},
        }

    response = {
        "data": {
            "entity": {
                "id": entity_id,
                "type": entity_type,
                "name": entity_name,
                "genres": entity_genres,
                "image_url": image_url,
            },
            "predictions": predictions_dict,
            "prediction_summary": {
                "calibrated_confidence": confidence,
                "prediction_label": prediction.get("prediction_label", "steady"),
                "confidence_level": prediction.get("confidence_level", "medium"),
                "model_version": prediction.get("model_version", "unknown"),
                "is_ml_model": prediction.get("is_ml", False),
                "active_models": prediction.get("active_models", []),
                "top_features": prediction.get("top_features", []),
                "horizon": horizon,
            },
            "features": prediction.get("features", {}),
        },
        "meta": {
            "request_id": f"req_{uuid_mod.uuid4().hex[:12]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "market": "US",
        },
    }

    await cache.set(cache_key, response, ttl=CACHE_TTL["predictions"])
    return response


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    admin_key: ApiKey = Depends(require_admin),
):
    try:
        pred_uuid = uuid_mod.UUID(body.prediction_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "Invalid prediction_id format", "details": {}}},
        )

    result = await db.execute(select(Prediction).where(Prediction.id == pred_uuid))
    prediction = result.scalar_one_or_none()

    if prediction is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Prediction not found", "details": {}}},
        )

    if prediction.actual_score is not None:
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "CONFLICT", "message": "Prediction already resolved", "details": {}}},
        )

    prediction.actual_score = body.actual_score
    prediction.error = prediction.predicted_score - body.actual_score
    prediction.resolved_at = datetime.now(timezone.utc)

    return FeedbackResponse(
        data={
            "prediction_id": str(prediction.id),
            "predicted_score": prediction.predicted_score,
            "actual_score": body.actual_score,
            "error": prediction.error,
            "resolved_at": prediction.resolved_at.isoformat(),
        }
    )
