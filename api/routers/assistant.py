"""AI Assistant endpoint — natural language interface to SoundPulse data."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.dependencies import get_api_key_record
from api.models.api_key import ApiKey
from api.services.assistant_service import ask_assistant

router = APIRouter(tags=["assistant"])


class ChatRequest(BaseModel):
    question: str
    history: list[dict] | None = None


@router.post("/api/v1/assistant/chat")
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    _key: ApiKey = Depends(get_api_key_record),
):
    """Ask the AI assistant a question about SoundPulse data."""
    result = await ask_assistant(db, request.question, request.history)
    return {"data": result}
