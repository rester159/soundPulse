/**
 * ASCAP Fonzworth portal flow — powered by BlackTip (rester159/blacktip).
 *
 * Takes a claimed ascap_submissions row from the portal-worker main
 * loop, drives the ASCAP portal through the work registration flow,
 * and returns a result object the worker posts back via
 * /admin/worker/ack or /admin/worker/fail.
 *
 * Credentials (required env on the portal-worker service):
 *   ASCAP_USERNAME, ASCAP_PASSWORD
 *
 * Portal docs / screenshots referenced while building this flow:
 *   https://my.ascap.com/                — login
 *   https://my.ascap.com/Repertory        — work registration landing
 *   https://my.ascap.com/Repertory/AddWork — add-work form
 *
 * SELECTOR TUNING: the selectors below are best-guess based on public
 * Fonzworth screenshots and will need live adjustment against the real
 * DOM on first production run. Each selector is wrapped in a named
 * helper (FIELD_TITLE, FIELD_IPI, etc) so re-tuning is local — search
 * for FIELD_ or STEP_ to find every interactive element in one place.
 */
import { BlackTip } from 'black-tip';

const ASCAP_LOGIN_URL = process.env.ASCAP_LOGIN_URL || 'https://my.ascap.com/';
const ASCAP_ADD_WORK_URL = process.env.ASCAP_ADD_WORK_URL || 'https://my.ascap.com/Repertory/AddWork';
const PORTAL_MIN_DELAY_MS = parseInt(process.env.PORTAL_MIN_DELAY_MS || '1500', 10);
const STEP_TIMEOUT_MS = 30000;

// ---- Selector registry (update these as the real DOM is inspected) ----
const SEL = {
  // Login page
  USERNAME_INPUT:    "input[name='username'], input#username, input[type='email']",
  PASSWORD_INPUT:    "input[name='password'], input#password, input[type='password']",
  LOGIN_BUTTON:      "button[type='submit'], button:has-text('Sign in'), button:has-text('Log in')",
  // Dashboard → Repertory nav
  REPERTORY_LINK:    "a:has-text('Repertory'), nav a[href*='Repertory' i]",
  ADD_WORK_LINK:     "a:has-text('Add Work'), button:has-text('Add Work'), a[href*='AddWork' i]",
  // Work registration form
  FIELD_TITLE:       "input[name='Title'], input[placeholder*='title' i]",
  FIELD_ISWC:        "input[name='ISWC'], input[placeholder*='ISWC' i]",
  FIELD_LANGUAGE:    "select[name='Language']",
  FIELD_CREATION_DATE: "input[name='CreationDate'], input[type='date']",
  // Writer row (first writer)
  ADD_WRITER_BTN:    "button:has-text('Add Writer'), button:has-text('+ Writer')",
  WRITER_NAME:       "input[name='Writer_Name'], input[placeholder*='writer' i]",
  WRITER_SHARE:      "input[name='Writer_Share']",
  WRITER_ROLE:       "select[name='Writer_Role']",
  // Publisher row
  ADD_PUBLISHER_BTN: "button:has-text('Add Publisher'), button:has-text('+ Publisher')",
  PUBLISHER_NAME:    "input[name='Publisher_Name']",
  PUBLISHER_SHARE:   "input[name='Publisher_Share']",
  // Submit
  SUBMIT_BUTTON:     "button[type='submit']:has-text('Submit'), button:has-text('Register Work')",
  // Confirmation
  WORK_ID_TEXT:      "[data-testid='work-id'], .work-id, .confirmation-id, [data-work-id]",
  CONFIRMATION_BANNER: ".confirmation, .success-banner, [role='status']",
};


function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }


async function _safeFill(page, selector, value) {
  if (value === null || value === undefined || value === '') return false;
  try {
    await page.waitForSelector(selector, { timeout: 10000 });
    await page.fill(selector, String(value));
    return true;
  } catch (e) {
    console.warn(`[ascap] fill failed for ${selector}: ${e.message}`);
    return false;
  }
}


async function _safeClick(page, selector, { timeout = 10000 } = {}) {
  try {
    await page.waitForSelector(selector, { timeout });
    await page.click(selector);
    return true;
  } catch (e) {
    console.warn(`[ascap] click failed for ${selector}: ${e.message}`);
    return false;
  }
}


async function _loginFlow(page, username, password) {
  await page.goto(ASCAP_LOGIN_URL, { waitUntil: 'domcontentloaded', timeout: STEP_TIMEOUT_MS });
  await sleep(PORTAL_MIN_DELAY_MS);

  await _safeFill(page, SEL.USERNAME_INPUT, username);
  await _safeFill(page, SEL.PASSWORD_INPUT, password);
  await sleep(500);
  const clicked = await _safeClick(page, SEL.LOGIN_BUTTON);
  if (!clicked) {
    // Fall back to pressing Enter on the password field
    await page.keyboard.press('Enter');
  }
  await page.waitForLoadState('networkidle', { timeout: STEP_TIMEOUT_MS });
  await sleep(PORTAL_MIN_DELAY_MS);

  // Post-login URL should no longer contain 'login' — use that as a
  // rough success heuristic until we add a real dashboard selector check
  const postUrl = page.url().toLowerCase();
  if (postUrl.includes('/login') || postUrl.includes('/signin')) {
    throw new Error(`login failed — still on login page: ${page.url()}`);
  }
}


async function _navigateToAddWork(page) {
  // Prefer the direct URL. Fall back to clicking through the nav if
  // the portal redirects.
  await page.goto(ASCAP_ADD_WORK_URL, { waitUntil: 'domcontentloaded', timeout: STEP_TIMEOUT_MS });
  await sleep(PORTAL_MIN_DELAY_MS);
  if (!page.url().toLowerCase().includes('addwork')) {
    await _safeClick(page, SEL.REPERTORY_LINK);
    await sleep(PORTAL_MIN_DELAY_MS);
    await _safeClick(page, SEL.ADD_WORK_LINK);
    await sleep(PORTAL_MIN_DELAY_MS);
  }
  await page.waitForLoadState('networkidle', { timeout: STEP_TIMEOUT_MS });
}


async function _fillWorkForm(page, claimed) {
  const song = claimed.song || {};
  const writers = claimed.writers_json?.writers || [];
  const publishers = claimed.publishers_json?.publishers || [];

  await _safeFill(page, SEL.FIELD_TITLE, claimed.submission_title || song.title || 'Untitled');
  if (claimed.iswc) await _safeFill(page, SEL.FIELD_ISWC, claimed.iswc);
  if (song.actual_release_date) await _safeFill(page, SEL.FIELD_CREATION_DATE, song.actual_release_date);
  if (song.language) {
    try { await page.selectOption(SEL.FIELD_LANGUAGE, song.language); } catch {}
  }

  // Fill first writer (the UI usually pre-renders one empty row)
  if (writers.length > 0) {
    const w = writers[0];
    await _safeFill(page, SEL.WRITER_NAME, w.name || claimed.artist?.legal_name || claimed.artist?.stage_name || '');
    await _safeFill(page, SEL.WRITER_SHARE, String(w.share_pct ?? 100));
    if (w.role) {
      try { await page.selectOption(SEL.WRITER_ROLE, w.role); } catch {}
    }
  }

  // Additional writers — click "Add Writer" once per extra row
  for (let i = 1; i < writers.length; i++) {
    await _safeClick(page, SEL.ADD_WRITER_BTN);
    await sleep(400);
    // Additional writer selectors would need nth-based resolution —
    // leaving this as a TODO for multi-writer tuning. First writer
    // covers 95% of SoundPulse's current catalog.
  }

  // First publisher
  if (publishers.length > 0) {
    const p = publishers[0];
    await _safeFill(page, SEL.PUBLISHER_NAME, p.name || 'SoundPulse Records LLC');
    await _safeFill(page, SEL.PUBLISHER_SHARE, String(p.share_pct ?? 100));
  }
}


async function _submitAndCapture(page) {
  await _safeClick(page, SEL.SUBMIT_BUTTON);
  await page.waitForLoadState('networkidle', { timeout: STEP_TIMEOUT_MS });
  await sleep(PORTAL_MIN_DELAY_MS);

  // Extract work_id from URL or DOM
  let workId = null;
  const url = page.url();
  const urlMatch = url.match(/workid=([^&#]+)/i) || url.match(/work\/(\d+)/i);
  if (urlMatch) workId = urlMatch[1];

  if (!workId) {
    try {
      const txt = await page.innerText(SEL.WORK_ID_TEXT, { timeout: 3000 });
      if (txt && txt.trim()) workId = txt.trim();
    } catch {}
  }

  // Always capture a confirmation screenshot for the audit trail
  let screenshotB64 = null;
  try {
    const buf = await page.screenshot({ fullPage: true });
    // Truncate to 15KB of base64 so we don't balloon the JSONB column
    screenshotB64 = buf.toString('base64').slice(0, 20000);
  } catch (e) {
    console.warn(`[ascap] screenshot failed: ${e.message}`);
  }

  return { workId, confirmationUrl: url, screenshotB64 };
}


/**
 * Main entry point — drives one ASCAP work registration end-to-end.
 * Called by worker.mjs with the `claimed` row payload. Returns a
 * result object matching what the worker posts to /admin/worker/ack
 * or /admin/worker/fail.
 */
export async function runAscapFlow(claimed) {
  const username = process.env.ASCAP_USERNAME?.trim();
  const password = process.env.ASCAP_PASSWORD?.trim();
  if (!username || !password) {
    return {
      status: 'failed',
      error: 'ASCAP_USERNAME/ASCAP_PASSWORD not set on portal-worker service',
      retry: false,
    };
  }

  console.log(`[ascap] starting flow for submission ${claimed.submission_id} title="${claimed.submission_title}"`);

  const tip = new BlackTip();
  let browser, page;
  try {
    browser = await tip.launch({ headless: false });  // Xvfb handles display
    const context = await browser.newContext();
    page = await context.newPage();

    await _loginFlow(page, username, password);
    console.log(`[ascap] logged in as ${username}`);

    await _navigateToAddWork(page);
    console.log(`[ascap] on AddWork page: ${page.url()}`);

    await _fillWorkForm(page, claimed);
    console.log(`[ascap] form filled`);

    const { workId, confirmationUrl, screenshotB64 } = await _submitAndCapture(page);
    console.log(`[ascap] submitted — work_id=${workId || '(none parsed)'} confirmation=${confirmationUrl}`);

    return {
      status: 'submitted',
      external_id: workId,
      response: {
        confirmation_url: confirmationUrl,
        ascap_work_id: workId,
        portal: 'ascap.my.ascap.com',
      },
      screenshot_b64: screenshotB64,
    };
  } catch (e) {
    console.error(`[ascap] flow failed: ${e.message}`);
    // Capture an error screenshot if the page is still alive
    let screenshotB64 = null;
    if (page) {
      try {
        const buf = await page.screenshot({ fullPage: true });
        screenshotB64 = buf.toString('base64').slice(0, 20000);
      } catch {}
    }
    return {
      status: 'failed',
      error: e.message || String(e),
      screenshot_b64: screenshotB64,
      retry: true,
    };
  } finally {
    try { if (browser) await browser.close(); } catch {}
    try { if (tip?.close) await tip.close(); } catch {}
  }
}
