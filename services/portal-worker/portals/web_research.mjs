/**
 * Web research portal flow — BlackTip browser-driven.
 *
 * Called from worker.mjs when target_service === 'web_research'.
 * Claimed payload shape (from /api/v1/admin/worker/claim-next):
 *   {
 *     submission_id: <web_research_jobs.id>,
 *     target_service: 'web_research',
 *     target_kind: 'genre_research' | ...,
 *     query: 'music genre: hip-hop.boom-bap.east-coast',
 *     genre_id: 'hip-hop.boom-bap.east-coast' | null,
 *     blueprint_id: '<uuid>' | null,
 *     worker_id: ...
 *   }
 *
 * Returns to worker.mjs for ack:
 *   {
 *     status: 'submitted',
 *     external_id: null,
 *     response: {
 *       result_text: '<concatenated article text>',
 *       sources: [{url, title, source: 'wikipedia'|'allmusic'|'rym', chars}],
 *     }
 *   }
 *
 * Strategy: hit Wikipedia + Allmusic + Rate Your Music for the genre.
 * Wikipedia provides reliable structured prose; Allmusic + RYM cover
 * the long-tail subgenres Wikipedia is thin on. Each source is wrapped
 * in a try/catch so one failure doesn't fail the whole job — we want
 * partial results over no results.
 */
import { BlackTip } from 'black-tip';

const STEP_TIMEOUT_MS = 25000;
const MAX_CHARS_PER_SOURCE = 4000;
const TOTAL_BUDGET_CHARS = 12000;

function _genreToQuery(genreId) {
  // 'hip-hop.boom-bap.east-coast' → 'East Coast Boom Bap Hip Hop'
  // Reverse so the leaf (most distinctive) leads.
  if (!genreId) return null;
  const parts = genreId.split('.').map(p => p.replace(/-/g, ' ').trim()).filter(Boolean);
  if (parts.length === 0) return null;
  return parts.reverse().join(' ');
}

async function _fetchWikipedia(page, query) {
  // Direct Wikipedia search → click top result → extract main article
  // text. Wikipedia doesn't block scrapers but we go via browser anyway
  // to keep the tooling consistent with the other sources.
  try {
    const url = `https://en.wikipedia.org/w/index.php?search=${encodeURIComponent(query)}&go=Go`;
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: STEP_TIMEOUT_MS });
    // Wikipedia auto-redirects to the article when the search exactly
    // matches a title. If we land on a search results page, click the
    // first result instead.
    const onSearch = (await page.url()).includes('Special:Search');
    if (onSearch) {
      const firstHit = await page.locator('.mw-search-result-heading a').first();
      if (await firstHit.count() === 0) {
        return { source: 'wikipedia', url: page.url(), title: '(no results)', text: '', chars: 0 };
      }
      await firstHit.click();
      await page.waitForLoadState('domcontentloaded', { timeout: STEP_TIMEOUT_MS });
    }
    const title = await page.title();
    // Pull the lead section — usually the first 1-3 paragraphs of the
    // main article body. #mw-content-text > div > p selectors.
    const text = await page.evaluate(() => {
      const paras = document.querySelectorAll('#mw-content-text .mw-parser-output > p');
      const out = [];
      for (const p of paras) {
        const t = (p.innerText || '').trim();
        if (t.length > 80) out.push(t);
        if (out.join(' ').length > 4000) break;
      }
      return out.join('\n\n');
    });
    return {
      source: 'wikipedia',
      url: page.url(),
      title: title.replace(/ - Wikipedia$/, ''),
      text: (text || '').slice(0, MAX_CHARS_PER_SOURCE),
      chars: (text || '').length,
    };
  } catch (e) {
    return { source: 'wikipedia', error: e.message || String(e), text: '', chars: 0 };
  }
}

async function _fetchAllmusic(page, query) {
  // Allmusic genre pages live under /style/* with slug-style URLs. We
  // search via their search box and extract the "Genre Description"
  // section if we land on a style page.
  try {
    const url = `https://www.allmusic.com/search/styles/${encodeURIComponent(query)}`;
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: STEP_TIMEOUT_MS });
    // Click the first style result if present
    const firstHit = page.locator('a.styles[href*="/style/"]').first();
    if (await firstHit.count() === 0) {
      return { source: 'allmusic', url: page.url(), title: '(no style match)', text: '', chars: 0 };
    }
    await firstHit.click();
    await page.waitForLoadState('domcontentloaded', { timeout: STEP_TIMEOUT_MS });
    const title = await page.title();
    const text = await page.evaluate(() => {
      // Allmusic style pages have a description block. Selector varies;
      // grab any prominent prose div as a best-effort fallback.
      const candidates = [
        '.styleDescription',
        '.description',
        '#descriptionContent',
        'section.descriptionContent',
        '.text',
      ];
      for (const sel of candidates) {
        const el = document.querySelector(sel);
        if (el && el.innerText && el.innerText.trim().length > 200) {
          return el.innerText.trim();
        }
      }
      // Last resort: largest <p> on the page
      const paras = Array.from(document.querySelectorAll('p'))
        .map(p => p.innerText || '')
        .filter(t => t.length > 200)
        .sort((a, b) => b.length - a.length);
      return paras[0] || '';
    });
    return {
      source: 'allmusic',
      url: page.url(),
      title: title.replace(/ \| AllMusic$/i, ''),
      text: (text || '').slice(0, MAX_CHARS_PER_SOURCE),
      chars: (text || '').length,
    };
  } catch (e) {
    return { source: 'allmusic', error: e.message || String(e), text: '', chars: 0 };
  }
}

async function _fetchRYM(page, query) {
  // Rate Your Music uses /genre/<slug>/ but their slug scheme requires
  // the canonical genre name. We hit their search page, take the first
  // /genre/ link, then extract the description block.
  try {
    const url = `https://rateyourmusic.com/search?searchterm=${encodeURIComponent(query)}&searchtype=g`;
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: STEP_TIMEOUT_MS });
    const firstHit = page.locator('a[href*="/genre/"]').first();
    if (await firstHit.count() === 0) {
      return { source: 'rym', url: page.url(), title: '(no genre match)', text: '', chars: 0 };
    }
    await firstHit.click();
    await page.waitForLoadState('domcontentloaded', { timeout: STEP_TIMEOUT_MS });
    const title = await page.title();
    const text = await page.evaluate(() => {
      const candidates = [
        '.genre_description',
        '#genre_description',
        '.text',
        '.section_description',
      ];
      for (const sel of candidates) {
        const el = document.querySelector(sel);
        if (el && el.innerText && el.innerText.trim().length > 200) {
          return el.innerText.trim();
        }
      }
      return '';
    });
    return {
      source: 'rym',
      url: page.url(),
      title: title.replace(/ - RateYourMusic.*$/i, ''),
      text: (text || '').slice(0, MAX_CHARS_PER_SOURCE),
      chars: (text || '').length,
    };
  } catch (e) {
    return { source: 'rym', error: e.message || String(e), text: '', chars: 0 };
  }
}

export async function runWebResearchFlow(claimed) {
  const { genre_id, query: rawQuery } = claimed;
  const query = _genreToQuery(genre_id) || rawQuery;
  if (!query) {
    return { status: 'failed', error: 'no query / genre_id provided', retry: false };
  }
  console.log(`[web_research] starting research for query="${query}" genre_id="${genre_id || ''}"`);

  const tip = new BlackTip();
  let browser, page;
  try {
    browser = await tip.launch({ headless: false });  // Xvfb in container
    const context = await browser.newContext();
    page = await context.newPage();

    const results = [];
    // Run sources sequentially (single browser tab) — keeps the worker
    // instance count low. Each source has its own try/catch, so a 500
    // on Allmusic doesn't block Wikipedia.
    for (const fetcher of [_fetchWikipedia, _fetchAllmusic, _fetchRYM]) {
      const r = await fetcher(page, query);
      results.push(r);
      const totalChars = results.reduce((s, x) => s + (x.chars || 0), 0);
      if (totalChars > TOTAL_BUDGET_CHARS) {
        console.log(`[web_research] hit total budget (${totalChars} chars), stopping early`);
        break;
      }
    }

    // Concatenate non-empty results into a single text blob the API
    // can pass to the LLM as ground-truth context.
    const blocks = [];
    const sources = [];
    for (const r of results) {
      if (r.text && r.text.trim()) {
        blocks.push(`# ${r.source.toUpperCase()} — ${r.title}\n${r.text}`);
        sources.push({
          source: r.source,
          url: r.url || '',
          title: r.title || '',
          chars: r.chars || 0,
        });
      } else if (r.error) {
        sources.push({ source: r.source, error: r.error });
      }
    }
    const result_text = blocks.join('\n\n---\n\n');
    console.log(`[web_research] done: ${result_text.length} chars across ${sources.length} sources`);

    return {
      status: 'submitted',
      external_id: null,
      response: { result_text, sources },
    };
  } catch (e) {
    console.error(`[web_research] flow failed: ${e.message}`);
    return { status: 'failed', error: e.message || String(e), retry: true };
  } finally {
    try { if (browser) await browser.close(); } catch {}
    try { if (tip?.close) await tip.close(); } catch {}
  }
}
