"""
PRO + rights adapters: BMI, SoundExchange.

BMI: alternate writer-side PRO (ASCAP on §31 is our default). Playwright
portal. Same pattern as Fonzworth.

SoundExchange: digital performance royalties for the sound recording
side — pays performers + master owners when tracks are streamed on
non-interactive services (SiriusXM, Pandora, etc). Playwright portal,
deps=['distrokid'] because the tracks must be live on a DSP before
SoundExchange can register them.

Both register as portal adapters with the shared dispatcher. Selectors
are placeholders — first live run needs DOM tuning.
"""
from __future__ import annotations

from .playwright_distributors import PortalConfig, _run_portal_flow
from api.services.external_submission_agent import register_adapter

BMI_PORTAL = PortalConfig(
    target_service="bmi",
    signin_url="https://www.bmi.com/login",
    upload_url="https://www.bmi.com/works/new",
    username_env="BMI_USERNAME",
    password_env="BMI_PASSWORD",
    username_selector="input#Username",
    password_selector="input#Password",
    title_selector="input[name='WorkTitle']",
    artist_selector="input[name='WriterName']",
)

SOUNDEXCHANGE_PORTAL = PortalConfig(
    target_service="soundexchange",
    signin_url="https://www.soundexchange.com/login",
    upload_url="https://isrc.soundexchange.com/register",
    username_env="SOUNDEXCHANGE_USERNAME",
    password_env="SOUNDEXCHANGE_PASSWORD",
    title_selector="input[name='title']",
    artist_selector="input[name='artist']",
)


@register_adapter("bmi")
async def bmi_adapter(db, subject_row, target):
    return await _run_portal_flow(db, subject_row, BMI_PORTAL)


@register_adapter("soundexchange")
async def soundexchange_adapter(db, subject_row, target):
    return await _run_portal_flow(db, subject_row, SOUNDEXCHANGE_PORTAL)
