# Rank Math Pro — Clean-Room Architecture Analysis (2026-10-10)

Sources: `seo-by-rank-math-pro` (PRO 404-monitor, analytics extras, link-genius, seo-analysis extras) and `seo-by-rank-math` (free core: Google API layer, SEO analyzer, per-post scoring, 404 core, link counter). Concepts only — no code copied. Read-only analysis; nothing in the app was modified.

Relevance to our roadmap: §1 is the module we deliberately deferred in the Rank Math parity waves (wave I — GSC/GA4, needs owner OAuth). §3 is the audit engine we already paralleled (our `seo_analysis` service). §4 matches our existing 404 monitor (`seo_404_logs`) — see the comparison note there.

---

## 1. Analytics module (GSC / GA4 / AdSense / URL Inspection / PageSpeed)

**What it does.** Connects the site to a Google account via OAuth (proxied through the vendor's server), pulls Search Console query/page stats, GA4 pageviews (incl. AI-referral traffic), AdSense earnings, URL-Inspection index status and PageSpeed scores into local DB tables, and renders dashboards, per-post/per-keyword reports, winning/losing movers, a keyword rank tracker, frontend admin-bar stats, and scheduled email reports. PRO extends retention (180/365 days vs free 90) and adds GA4/AdSense/keyword-tracker/email layers on top of free's GSC core.

### Data sources

| API | Endpoint | Data |
|---|---|---|
| Search Console | `POST webmasters/v3/sites/{site}/searchAnalytics/query` | dims `date`, then `query`+`page`; rowLimit 10000 |
| GSC sites/sitemaps | `webmasters/v3/sites`, `…/sitemaps` | property list, sitemap submit/delete/sync |
| Site Verification | `siteVerification/v1/token`, `/webResource` (META) | auto-verify property |
| GA4 Data | `POST analyticsdata/v1beta/properties/{id}:runReport` | dims `date`, `pagePath`, `sessionSourceMedium`; metric `screenPageViews`; filters: streamId, optional country, hostname |
| GA4 Admin | `analyticsadmin/v1beta/accountSummaries` (paginated) | account→property picker |
| URL Inspection | `POST searchconsole/v1/urlInspection/index:inspect` | verdicts, coverage, fetch, robots, rich results, canonicals, referring URLs |
| PageSpeed | `GET pagespeedonline/v5/runPagespeed` | performance score, TTI |
| AdSense | daily date+earnings rows | earnings/day |
| Token info | `oauth2/v1/tokeninfo` | granted-scope introspection |

### OAuth & connection flow

1. Connect → redirect to vendor proxy (`oauth.rankmath.com?version=…&api_version=2.1&redirect_uri=<admin URL>&security=<nonce>`). The proxy holds the Google console project (client_id/secret) — sites never see the secret.
2. Proxy runs Google consent, redirects back with `access_token`, `refresh_token`, `expire` as URL params (legacy: numeric id, plugin fetches tokens from `get.php?id=N` server-to-server).
3. Plugin verifies nonce, stores tokens in one option — access+refresh **encrypted at rest** — then redirects to strip tokens from the URL.
4. Scopes: `webmasters`, `analytics.readonly`, `adsense.readonly` — discovered via tokeninfo, cached, features gated per scope.
5. Refresh: lazily before each call — if expired, `refresh.php?code=<refresh_token>` on the proxy returns a new access token. **The vendor proxy is required for refresh.**
6. Property selection: wizard fetches GSC sites + GA4 account summaries; saves GSC site URL (or `sc-domain:` property) and GA4 account/property/**stream** ID + country. First connect can auto-verify (META token) and auto-submit the sitemap.
7. Revocation: local-only — deletes tokens/profile, kills all scheduled jobs; no Google-side revoke.

### DB schema (custom tables)

- **`…_analytics_gsc`** — GSC facts: `day, query(1000), page(500), clicks, impressions, position double, ctr`. Prefixed indexes on query/page(190), clicks, position. Insert-only; URLs with `?` skipped; position >100 dropped.
- **`…_analytics_ga`** (PRO) — `day, page, pageviews, visitors, referrer` (referrer = AI-engine group or organic).
- **`…_analytics_adsense`** (PRO) — `day, earnings`.
- **`…_analytics_objects`** — **join hub**: `page, object_type/subtype/id, focus_keyword, seo_score, page_score, is_indexable, schemas_in_use, desktop/mobile pagespeed`. Synced on every content save + a bulk backfill job (50 IDs / 30 s).
- **`…_analytics_inspections`** — one row per page (upsert): index_verdict, indexing_state, coverage_state, fetch/robots states, rich_results (JSON), last_crawl_time, google/user canonical, sitemap, referring URLs (JSON), raw response (JSON).
- **`…_analytics_keyword_manager`** (PRO) — tracked keywords: `keyword, collection, is_active`.
- Retention: `console_caching_control` days (90/180/365) **×2 kept** to power period comparisons; orphan rows (page not in objects) purged after each sync.

### Sync pipeline (persistent job queue — Action Scheduler)

1. Recurring heartbeat every **3 days** (first run jittered 3–1380 min PRO / up to 4320 free). Per service: test connection → find missing days → enqueue per-day jobs.
2. A probe query (dim `date` only) finds days with impressions not yet stored and not in an `empty_dates` option; each missing day = one job at `now + count × gap` (**10 s PRO / 30 s free**).
3. Per-day fetch: GSC one `searchAnalytics/query` (query+page, 10k rows) bulk-inserted in **chunks of 50**; GA4 one `runReport` per day, rows filtered to organic + AI referrers (gemini/chatgpt/copilot/perplexity/deepseek/claude/grok domain map), dedup by `page|referrer` (UPDATE-add / INSERT); AdSense whole range in one call. Zero-row days recorded as empty → never re-fetched.
4. Finalizer: orphan cleanup, cache flush, precompute top-keywords for 7/15/30d/3m/6m/1y, stamp last-updated, kick inspections.
5. URL Inspections: all indexable pages ranked by 90-day impressions DESC; **7 s between requests, 2000/day quota**; overflow pushed +N days; skip pages inspected today.
6. Errors: HTTP ≠ 200 unschedules the rest of the workflow; >3 failures → "reconnect" flag; one retry after 60 s; `sleep(1)` client-side throttle on every API call; disconnect kills all jobs.

### API surface & display

Internal REST (namespace `…/an`, GET unless noted): `dashboard`, `keywordsOverview/Summary`, `analyticsSummary`, `postsSummary`, `postsRowsByObjects`, `keywordsRows` (paged/sorted/searchable), `post/{id}`, `inspectionResults`, POST `userPreferences`. PRO adds (verified: 15 routes): `getKeywordPages`, `postsOverview`, tracked-keyword CRUD + `autoAddFocusKeywords`, POST `getDesktopPagespeed`/`getMobilePagespeed`/`getPageSEOScore`, `postsRows`, `inspectionStats`. AJAX for connect/disconnect/property-save/cache-clear.

React SPA tabs: Dashboard, Site Analytics, SEO Performance, Keywords, Rank Tracker, Index Status; plus WP dashboard widget, frontend admin-bar stats, post-list "Search Traffic" column. Comparison logic: **end date = today − 3 days** (GSC latency), compare vs the equal-length preceding window; `{total, previous, difference}` per metric; SUM clicks/impressions, AVG position, COUNT DISTINCT query; winning/losing = diff filters. SEO-score histogram: good 81–100 / ok 51–80 / bad 1–50. Email reports: recurring midnight job, 30-day period (PRO adds 7/15), sections: summary, positions, winning/losing posts + keywords.

### Implementer checklist (Next.js/FastAPI)

1. **OAuth**: own Google Cloud project (scopes above, `access_type=offline, prompt=consent`) — skip the vendor proxy; standard code exchange; refresh token **encrypted**, access token with `expires_at`; refresh lazily at `oauth2.googleapis.com/token`. Never put tokens in redirect URLs — one-time server-side exchange.
2. **Tables**: `gsc_fact(day, query, page, clicks, impressions, position, ctr)`, `ga_fact(day, page, referrer, pageviews)`, `objects(page, type, id, focus_keyword, seo_score, is_indexable, schemas)`, `inspections(page UNIQUE, verdict fields, raw_json)`, `keyword_manager`. Unique keys `(day,query,page)` / `(day,page,referrer)` → **INSERT … ON CONFLICT** (their insert-only + existence probe is needless complexity).
3. **Worker**: Celery beat every 1–3 days → probe missing days → per-day fetch tasks spaced 10–30 s → bulk upsert → finalize (orphan cleanup, cache flush, precompute ranges, prune at 2× retention).
4. **Gotchas**: GSC data final 2–3 days late → anchor windows at today−3; track empty days to save quota; GSC rowLimit truncation (max 25000, paginate `startRow`); inspections 2000/day; strip URL fragments + host when joining pages; schedule jitter (thundering herd); quota backoff — kill remaining jobs on repeated failures, don't retry-storm; GA4 only (UA dead; their `view_id` = stream ID).

---

## 2. Link Genius (internal link suggestions + management)

**What it does.** Per-post link extraction/counting (internal/external, anchor, nofollow), TF-IDF + AI-refined internal-link suggestions and related posts, keyword→URL auto-linking ("Keyword Maps"), bulk link editing with rollback, and a background broken-link HTTP crawler.

### Data

Tables: `internal_links` (url, post_id, target_post_id, type, anchor_text, anchor_type, is_nofollow, target_blank, url_hash=md5; FULLTEXT on anchor/url); `internal_meta` per-post counters (incoming/internal/external); `…_audit` (url_hash unique, http_status, category 2xx–5xx/timeout/error/blocked, robots_blocked, is_marked_safe, last_checked); `…_history` + `…_snapshots` (batch rollback); `…_maps` (name, target_url, max_links_per_post=3, auto_link_on_publish, case_sensitive, stats) + `…_map_variations` (manual | ai).

### Suggestion algorithm (pseudocode)

```
pool(100)  = pillar_posts ∪ posts_sharing_taxonomy ∪ recent_posts   // same type, published
doc(p)     = SEO_title + SEO_description              // cached, keyed by post_modified
target     = selected text, or seo_text + excerpt + headings + terms + focus_kw + content[:20k]
tokens     = lowercase, strip non-word, split, drop stopwords (~35 EN) and len<=2
idf[w]     = log((N+1)/docs_with_w)
score      = cosine(tfidf(target), tfidf(candidate))
rank desc, top 20 → if AI available: POST summaries to AI service for re-ranking
```

Related posts persist to post meta and seed reverse links. Extraction: single-pass anchor regex, skip `#`/mailto/tel/system/self/media, host compare for internal/external, batch URL→post resolution; delete-then-reinsert per save; incoming counts via GROUP BY.

### Keyword maps (auto-linking)

On publish → async (10 s): gather enabled maps + variations; one content scan; `\b(v1|v2|…)\b` /iu; reject matches inside existing links or "unsafe ranges" (scripts, styles, shortcodes, non-paragraph/heading blocks); cap = max_links_per_post minus existing same-target links; skip self-links (normalized: scheme/www/trailing-slash/case); string-splice insert, one write.

### Audit crawler

Background queue (batches of 100), cursor by url_hash, dedup by hash, 24 h recheck skip; robots.txt per-domain cached 24 h (longest-match, Allow wins ties); HEAD → GET fallback; 3xx-as-200 if mere normalization; 5 s timeout; weekly orphan cleanup; "mark safe" override.

### Implementer checklist (Next.js/FastAPI)

- Unicode tokenizer — Persian stopword list (و، از، به، که، در …), drop the len>2 rule (Persian words are short), **ZWNJ normalization**, Arabic ی/ي / ک/ك folding. Caveat: `\b` behaves differently around ZWNJ — test.
- pg_trgm / FTS for candidate pooling beyond taxonomy; per-post term table; incremental TF-IDF invalidated by `post_modified`.
- HTML parser (not regex) for extraction; snapshot-before-write rollback table; Celery crawler with per-domain robots cache; normalize URLs everywhere before comparing.
- API parity: suggestions, related-posts, links CRUD + undo, bulk actions, keyword-maps CRUD + execute/preview, audit start/stats/recheck/mark-safe, export.

---

## 3. SEO Analysis (site-wide audit)

**What it does.** One-click homepage audit. The free plugin does **not** crawl: it GETs the vendor API `rankmath.com/analyze/v2/json/?u=<home_url>` (30 s timeout), which fetches the homepage HTML/headers/robots and returns `{test_id: {category, status, message, data}}`. ~8 local PHP tests are merged in; results cached indefinitely in two options until re-run. PRO lifts the same-domain restriction and adds competitor analysis (any URL, `ca=1`, separate cache, side-by-side UI) and print view.

### Checks & weights

**Local:** site_description (tagline set), blog_public (not noindexed), permalink_structure (weight 7), focus_keywords (posts lacking one, 3), post_titles (keyword absent from title, 4), search_console (linked, 1), sitemaps (3), auto_update.
**Remote:** Basic — h1 (5), h2 (2), img_alt (4), keywords_meta (5), links_ratio (3), title_length (4); Advanced — canonical (5), noindex (7), www redirect (4), opengraph (2), robots_txt (3), schema (3); Performance — image expires (3), minify css/js (2/1), page objects (2), page size (3), response time (3); Security — directory listing (1), safe browsing (8), ssl (7). Perf/security hidden unless advanced mode.

**Scoring:** `round(Σ weight of passed / Σ weight of all × 100)`. Bands: `<70 average`, `<50 bad`, else `good` — **verified live bug** (`class-seo-analyzer.php:184-194`): the `<70` check runs first, so `bad` is dead code; everything under 70 renders "average". Don't replicate; use explicit bands.

### Implementer checklist

FastAPI `POST /seo-audit/run` (admin, rate-limited): fetch homepage server-side once (status, headers, timing), parse title/meta/headings/alts/canonical/OG/schema; separate probes for robots.txt, sitemap.xml, http→https, www↔non-www, TLS, directory listing; local DB checks (missing focus keywords, keyword-in-title, noindex flag). Store JSON + timestamp; serve cached until re-run; weighted-pass ratio with explicit red/yellow/green bands. This replaces the vendor API with our own fetch — we already do this (our audit is self-hosted, which is strictly better than theirs).

## Per-Post Content Scoring (editor checklist)

Client-side "assessor", ~21 tests. **Basic:** keywordInTitle (36 pts EN / 38 non-EN), keywordInMetaDescription (2), keywordInPermalink (5, stopword-stripped accepted), keywordIn10Percent (3, >400 words), keywordInContent (3), keywordDensity (max 6: <0.5%→0, >2.5%→0, 0.5–0.75→2, 0.76–1.0→3, else 6), keywordNotUsed (async DB uniqueness check). **Additional:** keywordInSubheadings h2–h6 (3), keywordInImageAlt (2), lengthContent (max 8: ≥2500→8, ≥2000→5, ≥1500→4, ≥1000→3, ≥600→2), lengthPermalink ≤75 (4), hasInternalLink (5), hasExternalLink (4), ≥1 dofollow external (2), contentHasAssets (max 6: images 0/1/2/3→0/1/2/4, ≥4→6; videos 0/1/2→0/1/2), shortParagraphs (3; fail if any >120 words), hasTOC (2), contentAI (5). **Title readability:** startsWithKeyword (3, first half), sentiment (1, EN-only lexicon), powerWords (1), hasNumber (1). No Flesch/transition-word checks.

**Score:** per focus keyword `round(Σ score / Σ max × 100)`, only applicable tests; badge **>80 green / >50 yellow / else red**; primary keyword drives the badge. Implementer: a `Paper` DTO (title, description, permalink, plain-text body, keywords) + researches (wordCount, paragraphs, linkStats), each test `isApplicable → score|maxScore|message`, `GET /posts/{id}/keyword-unused`, recompute debounced on keystroke, tests filterable per content type.

---

## 4. 404 Monitor (quick overview)

Logs every front-end 404 (skips 410/451). Table `…_404_logs`: `id, uri(255, indexed 191), accessed, times_accessed, referer, user_agent`. Capture: flag on `wp`, record on `get_header`/`wp_head`; URI normalized (strip query string optionally, strip home prefix, untrailingslash); exclusion rules {pattern, exact|starts|ends|contains|regex}. **Simple mode:** upsert by URI, `times_accessed+1`. **Advanced mode:** row per hit with referer + parsed UA. Retention: row limit (default **100**) — on overflow **TRUNCATE the whole table** (crude; delete-oldest-N is better); no time-based expiry. Row actions: View, Delete, and **"Redirect"** — prefills a rule in the Redirections module; dashboard widget shows rows + total hits. PRO adds date-range CSV export and a per-URI hits column.

**vs ours:** our `seo_404_logs` + query-param handling + redirect deep-link already match this shape (see memory: seom1-3). Adopt only: exclusion-rule list, advanced mode (per-hit referer/UA), delete-oldest-N instead of their truncate, CSV export.

---

## Cross-cutting takeaways for our stack

1. **Analytics is the only module that truly needs external OAuth** — everything else is self-hostable. The vendor-proxy pattern exists to hide their client secret AND to meter PRO quotas server-side; with our own Google Cloud project we get a strictly cleaner flow (direct refresh, no third party in the trust path).
2. **Every module = small fact tables + a background sync pipeline + a React admin SPA.** Maps directly to: SQLAlchemy tables + Celery beat + Next.js admin pages.
3. **Retention ×2 for comparisons** and **anchor windows at today−3 (GSC latency)** are the two non-obvious design rules worth stealing.
4. **Their scoring-band dead-code bug and TRUNCATE-based 404 cleanup** are anti-patterns to avoid, not copy.
5. Persian-specific work is entirely in Link Genius's tokenizer (stopwords, ZWNJ, Arabic-char folding) — the rest is language-agnostic.
