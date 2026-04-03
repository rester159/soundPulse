# PRO Registration Automation Research

**Date:** 2026-04-03
**Purpose:** Evaluate all pathways for automating Performance Rights Organization (PRO) and mechanical license registration for SoundPulse virtual label operations.

---

## 1. TuneRegistry (tuneregistry.com)

### What It Is
A music publishing administration **software platform** (not an admin service). You manage your own catalog and registrations; TuneRegistry delivers the data to PROs/agencies on your behalf. No commission taken -- flat monthly fee.

### Registration Network (Direct Connections)
- **ASCAP** (daily delivery)
- **BMI** (daily delivery)
- **SESAC** (daily delivery)
- **Harry Fox Agency / HFA** (delivers on 15th and 30th of each month)
- **Music Reports Inc.** (weekly delivery)
- **SoundExchange** (via DDEX RDR-N v1.4 feed)
- **The MLC** (supported)
- **AARC** (exports)

### Data Fields Required Per Song
| Field | Required | Notes |
|-------|----------|-------|
| Song Title | Yes | |
| Writers (name, PRO affiliation, IPI#) | Yes | All writers must be PRO members |
| Publishers (name, PRO affiliation, IPI#) | Yes | |
| Ownership Splits (writer % + publisher %) | Yes | Must total 100% |
| ISRC | Recommended | For linking composition to recording |
| ISWC | Optional | TuneRegistry can obtain from PROs (takes ~14 days) |
| Lyrics | Optional | |
| Custom Music Codes | Optional | |

### Bulk Import / Batch Features
- **CSV Bulk Import:** YES. Two templates available:
  1. **Contacts template** -- bulk import creators/companies (must be done FIRST)
  2. **Works template** -- bulk import songs/works with all metadata
- **Undo window:** Bulk uploads can be reversed within 24 hours
- **Export formats:** CSV, XML, JSON, DDEX
- **Delivery methods:** Email, FTP, and API

### API
- TuneRegistry advertises API delivery capability for data output
- No public developer API documentation found for programmatic input (song creation)
- Best automation path: **CSV bulk import** for input, API/DDEX for output

### Automation Feasibility
| Method | Feasibility | Notes |
|--------|------------|-------|
| CSV Bulk Import | **HIGH** | Best path. Generate CSV from SoundPulse DB, upload to TuneRegistry |
| Playwright/Puppeteer | MEDIUM | Dashboard is a standard web app, automatable but fragile |
| Direct API | LOW | No public input API documented |
| DDEX | OUTPUT ONLY | Used for SoundExchange feed delivery |

### Pricing
| Plan | Cost | For |
|------|------|-----|
| Solo | $15/month | Solo songwriters, producers, artists |
| Team | $35/month | Small labels, publishers, managers (shared catalog) |
| Business | $95/month | Established labels, isolated catalogs, advanced permissions |

- **No per-song fees**
- **No commission on royalties** (you keep 100%)
- ISRCs included free with most plans

### Time to First Royalty
- Registration processing: ~7 days for PROs to accept
- ISWC assignment: ~14 days after accepted registration
- First royalty payment: **9-18 months** from performance date (standard PRO timeline)

### Verdict for SoundPulse
**BEST OPTION for automation.** CSV bulk import + flat fee + direct connections to all major US PROs/agencies. Build a pipeline: SoundPulse DB -> generate CSV -> upload to TuneRegistry -> registrations flow to ASCAP/BMI/SESAC/HFA/MLC/SoundExchange automatically.

---

## 2. Songtrust (songtrust.com)

### What It Is
A **publishing administration service** (not just software). They handle registration AND collection on your behalf, but take a commission.

### Registration Flow
1. Create account ($100 one-time signup fee per songwriter)
2. Register songwriters with PRO affiliation details
3. Register songs: title, co-writers, splits (songwriter share percentages)
4. Add ISRCs (manually or via Spotify catalog search tool)
5. Songtrust registers with 65+ global societies across 100+ territories
6. Each song has a status page tracking registration progress

### Data Fields Required Per Song
| Field | Required | Notes |
|-------|----------|-------|
| Song Title | Yes | |
| Songwriter(s) | Yes | With PRO affiliation |
| Co-writer names and splits | Yes | Percentage shares |
| ISRC | Yes | Can search via Spotify integration |
| Recording details | Recommended | |

### API / Batch Import
- **No public developer API found**
- **No CSV bulk import documented**
- Songs are registered through the Songtrust dashboard one at a time (or via their Spotify search tool)
- They position themselves as a "technical partner" for the industry but this appears to be B2B partnerships, not a developer API

### Commission / Pricing
| Item | Cost |
|------|------|
| Signup fee | $100 per songwriter (one-time) |
| Performance royalty commission | 15% |
| Mechanical royalty commission | 20% (increased Jan 2025) |

- Songtrust only collects the **publisher's share** (writer's share comes direct from PRO)
- Effective cost on total royalties: ~7.5-10% of publisher share

### Automation Feasibility
| Method | Feasibility | Notes |
|--------|------------|-------|
| Playwright/Puppeteer | MEDIUM | Standard web dashboard, could be automated |
| API | NOT AVAILABLE | No public API |
| CSV Import | NOT AVAILABLE | No bulk import feature found |

### Verdict for SoundPulse
**Not recommended as primary.** The commission model (15-20%) and lack of API/bulk import make this poor for automation at scale. Only useful if you want a fully hands-off service and don't mind the commission.

---

## 3. ASCAP Direct Registration

### Membership
- Songwriter membership: $50 (one-time)
- Publisher membership: $50 (one-time)

### Registration Flow
1. Log into Member Access at ascap.com/members
2. Navigate to Online Work Registration
3. Choose **Quick Registration** (basic fields) or **Guided Registration** (comprehensive)
4. Fill in work details
5. Submit -- processing takes up to 7 days
6. ASCAP sends data to CISAC for ISWC assignment

### Required Fields
| Field | Required | Notes |
|-------|----------|-------|
| Work Title | Yes | |
| Your name (as writer) | Yes | |
| Your split percentage | Yes | Writer splits must total 50% |
| Co-writer names | Yes (if applicable) | Each with their PRO affiliation |
| Co-writer splits | Yes | |
| Publisher name(s) | Yes (if applicable) | Publisher splits must total 50% |
| Publisher splits | Yes | |
| Performer name | Recommended | If work has been performed |
| ISRC | Optional | |
| Release date | Optional | |
| Genre | Optional | |

**Key rule:** Writer splits must total exactly 50%, publisher splits must total exactly 50%, for a combined 100%.

### Automation Feasibility
| Method | Feasibility | Notes |
|--------|------------|-------|
| Playwright/Puppeteer | MEDIUM-LOW | Possible but ASCAP likely has anti-automation protections. ToS may prohibit automated submissions. |
| API | NOT AVAILABLE | ASCAP has no public registration API |
| CSV/Batch | NOT AVAILABLE | No bulk upload for individual members |
| Via TuneRegistry | **HIGH** | TuneRegistry has direct daily feed to ASCAP |

### Time to First Royalty
- Registration processing: ~7 business days
- ASCAP pays quarterly with ~6-9 month lag from performance
- First payment from registration: **9-12 months**

### Verdict
**Do not automate directly.** Use TuneRegistry as the intermediary -- it has a direct daily data feed to ASCAP and handles the registration format requirements.

---

## 4. BMI Direct Registration

### Membership
- Songwriter: Free
- Publisher: $250 (one-time, for-profit entity)

### Registration Flow
1. Log into BMI Online Services
2. Go to Works Registration
3. Click "Add New Work"
4. Select genre: "Classical" or "All Other Genres"
5. Fill in work info, add writers with required fields
6. Ensure writer share percentages total 100%
7. Submit -- most works appear in catalog within 24 hours

### Required Fields
| Field | Required | Notes |
|-------|----------|-------|
| Work Title | Yes | Limited to 30 characters |
| Genre classification | Yes | Classical vs. All Other Genres |
| Writer name(s) | Yes | With IPI numbers |
| Writer PRO affiliation | Yes | |
| Writer share percentages | Yes | Must total 100% |
| Publisher name(s) | If applicable | |
| Publisher share percentages | If applicable | |
| Artist/Performer | Recommended | |

**Note:** BMI does NOT require audio files or lyrics.

**Key difference from ASCAP:** BMI allows claiming writer share AND publisher share under the same 100% split (no forced 50/50 split structure). Self-published writers can claim their own publisher share.

### Automation Feasibility
| Method | Feasibility | Notes |
|--------|------------|-------|
| Playwright/Puppeteer | MEDIUM-LOW | Same concerns as ASCAP -- ToS restrictions likely |
| API | NOT AVAILABLE | No public API |
| CSV/Batch | NOT AVAILABLE | No bulk upload for members |
| Via TuneRegistry | **HIGH** | TuneRegistry has direct daily feed to BMI |

### Time to First Royalty
- Registration processing: 24 hours to 7 business days
- BMI pays quarterly with similar lag to ASCAP
- First payment: **9-12 months**

---

## 5. CD Baby Pro Publishing

### Current Status (2025-2026)
**DISCONTINUED.** CD Baby Pro Publishing was shut down on August 8, 2023.

- Legacy releases (signed up before Aug 8, 2023) continue receiving Pro Publishing services
- New releases use "CDB Boost" which replaced Pro Publishing
- No batch API workflow available
- Not viable for new automation pipelines

### Verdict
**Dead end.** Do not pursue.

---

## 6. Harry Fox Agency (HFA) / The MLC

### Harry Fox Agency (HFA)

#### What They Handle
- Mechanical royalties for **physical** and **download** formats
- Post-Music Modernization Act, HFA handles non-digital phonorecord deliveries and certain digital transmissions outside the MLC blanket license

#### Registration Requirements
- Must have a publishing entity affiliated with ASCAP, BMI, or SESAC
- Full affiliation requires at least 1 commercially released song by a US-based third party within the last 12 months
- Self-published / DIY musicians can create an "HFA Online Account" (limited features)

#### Required Fields (Publisher Account)
| Field | Required | Notes |
|-------|----------|-------|
| Publisher Name | Yes | Must match ASCAP/BMI/SESAC entity name |
| HFA Account P# | If existing | Skip if new |
| Administrator Title | Yes | "Self" or representative title |
| Administrator Name | Yes | Full legal name |
| Song registrations | Yes | Title, writers, publisher, splits |

#### API
- No public API documented
- TuneRegistry has direct integration (delivers data on 15th and 30th monthly)

### The MLC (Mechanical Licensing Collective)

#### What They Handle
- Mechanical royalties from **digital streaming services** (Spotify, Apple Music, etc.)
- Mandated by the Music Modernization Act (2020)

#### Registration Methods
| Method | Details |
|--------|---------|
| Individual Work Registration | One song at a time through MLC Portal |
| **Bulk Work Registration** | Spreadsheet template upload, max 300 rows per upload |
| **CWR (Common Works Registration)** | Industry-standard format for hundreds/thousands of works. Requires CISAC submitter code |
| **Public Search API** | Beta available -- READ-ONLY for searching works in MLC database |

#### Bulk Work Template Required Fields
| Field | Required | Notes |
|-------|----------|-------|
| Work Title | Yes* | |
| AKA Title | Dependent | Requires AKA Title Type Code |
| Writer Name(s) | Yes* | |
| Writer IPI Number(s) | Recommended | |
| Publisher Name(s) | Yes* | |
| Publisher IPI Number(s) | Recommended | |
| Administrator Name | Dependent | Requires Administrator IPI Number |
| Recording Title | Dependent | Requires Recording Artist |
| Recording Artist | Dependent | Requires Recording Title |
| ISRC | Recommended | |
| Ownership shares | Yes* | |

*Fields marked with asterisk are required in the template.

#### MLC API Status
- **Public Search API:** Now in BETA. Read-only. Allows searching works by title, writers, publishers
- **No write/registration API** -- registration must go through portal, bulk upload, or CWR

#### Automation Feasibility
| Method | Feasibility | Notes |
|--------|------------|-------|
| MLC Bulk Upload (spreadsheet) | **HIGH** | Generate from SoundPulse DB, upload via portal. Max 300 rows per file. |
| CWR Submission | **HIGH** | Best for large catalogs. Requires obtaining CISAC submitter code |
| MLC Search API | READ-ONLY | Good for verification, not registration |
| Via TuneRegistry | **HIGH** | TuneRegistry registers with both HFA and MLC |
| Playwright/Puppeteer | MEDIUM | Portal is automatable for bulk upload button |

---

## 7. SoundExchange

### What They Handle
- Digital performance royalties for **sound recordings** (not compositions)
- Collects from non-interactive streaming: SiriusXM, Pandora, iHeartRadio, etc.
- Free to register

### Registration Flow
1. Create free SoundExchange Direct account at soundexchange.com/register
2. Register as Featured Artist, Non-Featured Artist, or Sound Recording Copyright Owner
3. Use "Submit Recordings" tool to add catalog
4. Search and claim existing recordings in their database
5. Track payments through dashboard

### Required Fields Per Recording
| Field | Required | Notes |
|-------|----------|-------|
| Artist Name | Yes | Recording artist, band, or group |
| Song Title | Yes | Name of specific sound recording |
| ISRC | Yes | 12-character alphanumeric code |
| Album Name | For bulk | Required in bulk CSV |
| Marketing Label | For bulk | Required in bulk CSV |
| Country of Fixation | Recommended | |
| Date of First Release | Recommended | |
| Release associations | Recommended | At least one release per ISRC |

### Bulk / API Options
| Method | Details |
|--------|---------|
| **ISRC Ingest Form (CSV/Excel)** | Download spreadsheet from Submit Recordings page, fill columns: Artist, Song_Title, Album_Name, Marketing_Label, ISRC |
| **DDEX Feeds** | ERN and RDR/MLC formats accepted |
| **Flat Excel Files** | Alternative to DDEX |
| **API Access** | Available -- contact techsupport@soundexchange.com to request |
| **Via TuneRegistry** | Uses DDEX RDR-N v1.4 feed |

### Automation Feasibility
| Method | Feasibility | Notes |
|--------|------------|-------|
| CSV/Excel Bulk Upload | **HIGH** | Generate from SoundPulse DB, upload via portal |
| DDEX Feed | **HIGH** | TuneRegistry can handle this automatically |
| API | **HIGH** | Available on request -- contact techsupport@soundexchange.com |
| Via TuneRegistry | **HIGH** | Automated DDEX delivery |

### Cost
- **Free** to register and collect

### Time to First Royalty
- SoundExchange pays quarterly
- Typical delay: **6-9 months** from airplay to payment

---

## Summary: Recommended Automation Architecture

### Tier 1: Best Path (TuneRegistry as Hub)

```
SoundPulse DB
    |
    v
Generate CSV (Contacts + Works templates)
    |
    v
TuneRegistry Bulk Import
    |
    +---> ASCAP (daily)
    +---> BMI (daily)
    +---> SESAC (daily)
    +---> HFA (bi-monthly)
    +---> Music Reports (weekly)
    +---> SoundExchange (DDEX feed)
    +---> The MLC
```

**Cost:** $35-95/month (Team or Business plan)
**Commission:** 0%
**Automation complexity:** LOW (CSV generation from database)

### Tier 2: Direct Supplemental (For MLC specifically)

```
SoundPulse DB
    |
    v
Generate MLC Bulk Work Spreadsheet (max 300 rows)
    or
Generate CWR file (for large catalogs, needs CISAC submitter code)
    |
    v
Upload to MLC Portal
```

### Tier 3: Direct SoundExchange API

```
SoundPulse DB
    |
    v
API calls to SoundExchange
(request access: techsupport@soundexchange.com)
```

### What NOT to Do
- Do not browser-automate ASCAP/BMI directly (ToS risk, fragile, unnecessary if using TuneRegistry)
- Do not use Songtrust (commission-based, no API, no bulk import)
- Do not pursue CD Baby Pro Publishing (discontinued)
- Do not try to build CWR files without a CISAC submitter code

---

## Data Model Requirements for SoundPulse

To support PRO registration automation, SoundPulse needs to track:

### Per Composition (Musical Work)
```
- title: str (required)
- alternate_titles: list[str] (optional)
- writers: list[Writer] (required)
    - name: str
    - ipi_number: str (assigned by PRO)
    - pro_affiliation: enum (ASCAP, BMI, SESAC)
    - writer_share_pct: decimal (must sum to 50% for ASCAP, or 100% for BMI)
- publishers: list[Publisher] (required if applicable)
    - name: str
    - ipi_number: str
    - pro_affiliation: enum
    - publisher_share_pct: decimal
- iswc: str (optional, assigned after registration)
- genre: str (optional)
- lyrics: text (optional)
```

### Per Recording (Sound Recording)
```
- isrc: str (required, 12-char alphanumeric)
- recording_title: str (required)
- artist_name: str (required)
- album_name: str (required for SoundExchange bulk)
- label_name: str (required for SoundExchange bulk)
- release_date: date (recommended)
- country_of_fixation: str (recommended)
- linked_composition_id: FK to composition
```

### Per Registration Event
```
- composition_id or recording_id: FK
- target_organization: enum (ASCAP, BMI, SESAC, HFA, MLC, SoundExchange, MRI)
- registration_method: enum (tuneregistry_csv, mlc_bulk, soundexchange_api, direct)
- submitted_at: datetime
- status: enum (pending, accepted, rejected, conflict)
- external_reference_id: str (from PRO/agency)
- iswc_assigned: str (when returned)
```

---

## Cost Comparison

| Service | Monthly Cost | Commission | Bulk Import | API | PROs Covered |
|---------|-------------|------------|-------------|-----|--------------|
| TuneRegistry (Team) | $35/mo | 0% | CSV | Output only | ASCAP, BMI, SESAC, HFA, MRI, SoundExchange, MLC |
| TuneRegistry (Business) | $95/mo | 0% | CSV | Output only | Same as above |
| Songtrust | $100 one-time per writer | 15-20% | No | No | 65+ global societies |
| ASCAP Direct | $50 one-time | 0% | No | No | ASCAP only |
| BMI Direct | Free (writer) / $250 (publisher) | 0% | No | No | BMI only |
| The MLC | Free | 0% | Spreadsheet / CWR | Search only (beta) | MLC only |
| SoundExchange | Free | 0% | CSV + DDEX | On request | SoundExchange only |
| CD Baby Pro | DISCONTINUED | N/A | N/A | N/A | N/A |

---

## Implementation Priority

1. **Immediate:** Set up TuneRegistry Business account ($95/mo) -- covers all US PROs/agencies
2. **Immediate:** Build CSV export pipeline from SoundPulse DB matching TuneRegistry bulk import templates
3. **Week 2:** Register with SoundExchange Direct, request API access
4. **Week 2:** Register with The MLC as publisher member, set up bulk upload workflow
5. **Week 3:** Ensure all writers/publishers have IPI numbers from their PROs
6. **Week 4:** Set up HFA Online Account for mechanical licensing coverage
7. **Ongoing:** Monitor registration statuses, handle conflicts/rejections

## Sources

- [TuneRegistry Bulk Import](http://help.tuneregistry.com/en/articles/1591125-bulk-import)
- [TuneRegistry Registration Network](https://www.tuneregistry.com/network)
- [TuneRegistry Pricing](https://www.tuneregistry.com/pricing)
- [TuneRegistry vs Alternatives](https://help.tuneregistry.com/en/articles/2440867-publishing-administration-alternatives)
- [Songtrust Pricing Changes 2025](https://help.songtrust.com/knowledge/what-is-changing-about-songtrusts-pricing-structure-in-2025)
- [Songtrust Technical Partner](https://blog.songtrust.com/songtrust-as-your-technical-partner-in-music-publishing-administration)
- [ASCAP Work Registration](https://www.ascap.com/help/royalties-and-payment/payment/registering)
- [ASCAP ISWC FAQ](https://www.ascap.com/help/registering-your-music/iswc-number-work-codes-faq)
- [BMI Work Registration FAQ](https://www.bmi.com/faq/entry/how-do-i-register-my-songs-with-bmi)
- [BMI Registration Video Guide](https://www.bmi.com/video/entry/how-to-register-your-songs-online-at-bmi.com)
- [The MLC Work Registration](https://www.themlc.com/work-registration)
- [MLC Bulk Work Guide](https://help.themlc.com/en/support/how-do-i-complete-the-bulk-work-document)
- [MLC Data Programs / API](https://www.themlc.com/dataprograms)
- [HFA Registration Guide](https://www.tuneregistry.com/blog/how-to-apply-for-a-harry-fox-agency-online-account-as-a-diy-musician-a-step-by-step-guide)
- [SoundExchange Submit Recordings Guide](https://www.soundexchange.com/2019/11/04/mastering-my-catalog-a-guide-to-submit-recordings/)
- [SoundExchange Registration](https://www.soundexchange.com/register/)
- [SoundExchange DDEX via TuneRegistry](https://help.tuneregistry.com/en/articles/5776227-soundexchange-ddex-feed)
- [CD Baby Pro Publishing Discontinued](https://support.cdbaby.com/hc/en-us/articles/211130163-What-was-CD-Baby-Pro-Publishing)
- [Royalty Payment Timeline](https://help.songtrust.com/knowledge/when-should-i-expect-my-first-royalty-payments)
