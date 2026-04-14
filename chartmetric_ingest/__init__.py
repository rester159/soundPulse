"""Chartmetric global ingest pipeline.

One fetcher, one token bucket, one priority queue. Planners emit jobs
into the queue; the fetcher drains it at exactly the rate the global
quota allows and dispatches parsed responses to registered handlers.

Entry points:
  - chartmetric_ingest.queue.enqueue(...)   — producer API
  - chartmetric_ingest.fetcher.ChartmetricFetcher — the single consumer
  - chartmetric_ingest.handlers.register(...) — result parser registry
  - chartmetric_ingest.priority.priority_from_scores(...) — planner helper

See `alembic/versions/027_chartmetric_ingest_queue.py` for the schema.
"""
