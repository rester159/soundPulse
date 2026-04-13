"""
Telegram Bot delivery for CEO gate decisions (PRD §23, T-150).

Uses the Telegram Bot API directly over httpx (no python-telegram-bot
dep). Free, no rate limits for our volumes, works from any environment
that can make outbound HTTPS.

Setup:
  1. Open Telegram → message @BotFather → /newbot → pick name + username
  2. BotFather returns a token like `7123456789:AAH...` — set as
     TELEGRAM_BOT_TOKEN on Railway
  3. Open your new bot in Telegram → send /start → the chat exists
  4. Call GET /api/v1/admin/telegram/get-chat-id to pull the chat_id
     from getUpdates and paste it into Settings → CEO Profile → Telegram

Usage:
  from api.services.telegram_bot import send_ceo_decision
  await send_ceo_decision(decision_dict, ceo_profile_row)
"""
from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
TELEGRAM_API_BASE = "https://api.telegram.org"

# Where the CEO clicks to review and approve/reject
UI_BASE_URL = os.environ.get(
    "FRONTEND_BASE_URL",
    "https://ui-production-02e9.up.railway.app",
)


class TelegramNotConfigured(Exception):
    """Raised when TELEGRAM_BOT_TOKEN is not set."""


def _bot_url(method: str) -> str:
    token = os.environ.get(TELEGRAM_TOKEN_ENV, "").strip()
    if not token:
        raise TelegramNotConfigured(
            f"{TELEGRAM_TOKEN_ENV} env var not set — create a bot via "
            f"@BotFather on Telegram and drop the token in Railway env"
        )
    return f"{TELEGRAM_API_BASE}/bot{token}/{method}"


async def send_message(
    chat_id: str | int,
    text: str,
    *,
    parse_mode: str = "HTML",
    reply_markup: dict[str, Any] | None = None,
    disable_web_page_preview: bool = True,
) -> dict[str, Any]:
    """
    Send a text message to a Telegram chat. Returns the Telegram API
    response dict. Raises TelegramNotConfigured or httpx errors on
    failure.
    """
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    url = _bot_url("sendMessage")
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(url, json=payload)
        if r.status_code != 200:
            logger.error("[telegram] sendMessage %s: %s", r.status_code, r.text[:400])
            r.raise_for_status()
        return r.json()


async def get_recent_chat_ids() -> list[dict[str, Any]]:
    """
    Call getUpdates to discover chat_ids that have messaged the bot.
    Used once during CEO setup so the user doesn't have to fish for
    their chat_id manually.

    Returns a list of {chat_id, name, username, last_message} dicts.
    """
    url = _bot_url("getUpdates")
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, params={"limit": 20})
        r.raise_for_status()
        body = r.json()

    if not body.get("ok"):
        return []

    seen_chat_ids: dict[int, dict] = {}
    for update in body.get("result", []):
        msg = update.get("message") or update.get("edited_message") or {}
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        if not chat_id or chat_id in seen_chat_ids:
            continue
        seen_chat_ids[chat_id] = {
            "chat_id": chat_id,
            "type": chat.get("type"),  # private | group | supergroup | channel
            "name": (
                chat.get("first_name", "") + " " + chat.get("last_name", "")
            ).strip() or chat.get("title") or "unknown",
            "username": chat.get("username"),
            "last_message": (msg.get("text") or "")[:100],
        }

    return list(seen_chat_ids.values())


def format_decision_message(decision: dict) -> tuple[str, dict | None]:
    """
    Format a ceo_decisions row as a Telegram message with inline
    action buttons. Returns (html_text, reply_markup).

    decision fields used:
      - decision_id (UUID)
      - decision_type
      - proposal
      - data (JSONB)
      - created_at
    """
    decision_id = decision.get("decision_id") or decision.get("id") or "?"
    dtype = decision.get("decision_type") or "unknown"
    proposal = decision.get("proposal") or "?"
    data = decision.get("data") or {}

    # Build the text block
    lines: list[str] = []

    if dtype == "artist_assignment":
        artist_name = data.get("proposed_artist_name") or "new artist"
        if proposal == "reuse":
            lines.append(f"🎤 <b>Reuse existing artist: {artist_name}</b>")
            lines.append("")
            if (reason := data.get("reason")):
                lines.append(f"<i>{reason}</i>")
        elif proposal == "create_new":
            lines.append("✨ <b>Create a new artist for this blueprint</b>")
        lines.append("")
        bp_genre = data.get("blueprint_genre") or "?"
        lines.append(f"Genre: {bp_genre}")
        roster_size = data.get("roster_size")
        if roster_size is not None:
            lines.append(f"Roster size: {roster_size}")

    elif dtype == "setup_required":
        lane_name = data.get("lane_display_name") or data.get("lane_id", "?")
        missing = data.get("missing") or []
        lines.append(f"⚠️ <b>Setup required: {lane_name}</b>")
        lines.append("")
        lines.append(f"Artist: {data.get('artist_name', '?')}")
        if (summary := data.get("summary")):
            lines.append(summary)
        lines.append("")
        if missing:
            lines.append(f"<b>{len(missing)} action item(s):</b>")
            for item in missing[:5]:
                desc = item.get("description") or item.get("code", "?")
                lines.append(f" • {desc}")
                if (env := item.get("env_var")):
                    lines.append(f"   → set <code>{env}</code>")
                elif (plat := item.get("social_platform")):
                    lines.append(f"   → create account on {plat.upper()}")

    else:
        lines.append(f"🔔 <b>New CEO decision: {dtype}</b>")
        lines.append(f"Proposal: {proposal}")

    # Footer: deep link to settings page
    link = f"{UI_BASE_URL}/settings"
    lines.append("")
    lines.append(f'<a href="{link}">Open SoundPulse → Settings</a>')

    text = "\n".join(lines)

    # Inline keyboard with approve/reject buttons (optional — requires
    # webhook wiring on our side, deferred). For now just a "View" button.
    reply_markup = {
        "inline_keyboard": [[
            {"text": "View in SoundPulse →", "url": link},
        ]],
    }

    return text, reply_markup


async def send_ceo_decision(decision: dict, profile_row) -> bool:
    """
    Dispatch a ceo_decisions row to the configured CEO channel.
    Returns True on success, False on any failure (logged).

    `profile_row` is an instance of the CeoProfile ORM model. Honors
    profile.preferred_channel — only sends if set to 'telegram'.
    """
    if not profile_row:
        logger.warning("[telegram] no CEO profile — skipping decision notify")
        return False

    preferred = getattr(profile_row, "preferred_channel", None)
    if preferred != "telegram":
        logger.info(
            "[telegram] preferred_channel=%s, skipping telegram delivery", preferred,
        )
        return False

    chat_id = getattr(profile_row, "telegram_chat_id", None)
    if not chat_id:
        logger.warning("[telegram] no telegram_chat_id on ceo_profile — skipping")
        return False

    try:
        text, reply_markup = format_decision_message(decision)
        await send_message(chat_id, text, reply_markup=reply_markup)
        return True
    except TelegramNotConfigured as e:
        logger.warning("[telegram] %s", e)
        return False
    except Exception:
        logger.exception("[telegram] send_ceo_decision failed")
        return False
