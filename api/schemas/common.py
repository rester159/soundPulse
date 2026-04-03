from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Meta(BaseModel):
    request_id: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
    data_freshness: datetime | None = None
    total: int | None = None
    limit: int | None = None
    offset: int | None = None


class PaginatedMeta(Meta):
    total: int = 0
    limit: int = 50
    offset: int = 0
