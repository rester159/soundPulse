web: uvicorn api.main:app --host 0.0.0.0 --port $PORT
worker: celery -A scrapers.celery_app worker --loglevel=info --concurrency=2
beat: celery -A scrapers.celery_app beat --loglevel=info
