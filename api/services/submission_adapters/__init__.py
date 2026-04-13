"""
Submission adapters — one module per downstream service.

Each adapter registers itself with the external_submission_agent
dispatcher via @register_adapter('<target_service>') and replaces the
default _stub_adapter. Importing this package at boot time (via
api/main.py) runs all the decorators.

Structure: each adapter exposes a single async function
(db, subject_row, target) -> (status, external_id, response_dict).
"""
from __future__ import annotations

# Import each adapter module so its @register_adapter decorators run.
# Order doesn't matter — all decorators are additive.
from . import distrokid  # noqa: F401
from . import mlc  # noqa: F401
