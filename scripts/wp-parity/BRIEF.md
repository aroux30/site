# BRIEF — WordPress core parity audit (read-only)

## What we are doing
Compare the **real** WordPress core source against **our** FastAPI + Next.js app
(`C:\Users\Administrator\Desktop\site`) and classify every WordPress feature as
PRESENT / PARTIAL / MISSING / BROKEN / NA.

## WordPress source of truth (READ-ONLY, never modify, never run PHP)
- GitHub: `WordPress/WordPress`, clone at `c586ba782bc2193bebb97ced60ea63e13f37d2a4`
- `$wp_version = '7.2-alpha-63984'`
- Path in bash: `/tmp/wp-core`   Path in Python: `C:\Users\ADMINI~1\AppData\Local\Temp\wp-core`
- Pre-extracted inventory: `scripts/wp-parity/wp_inventory.json` (post types, taxonomies,
  statuses, formats, 86 capabilities, 5 roles + their cap counts, 47 REST controllers,
  115 block dirs, 23 block-supports, 19 widgets, 95 admin screens, 257 wp-includes files)
- Our route inventory (800 routes, AST-extracted): `scripts/wp-parity/our_routes.json`

## Hard rules — violating these makes the finding worthless
1. **READ-ONLY.** Do not edit any file. Do not start/stop servers. Do not run migrations.
   Do not touch the database. Do not clear Recovery Mode or any pause flag.
2. **Every finding needs evidence**: a `path:line` we can open, or the actual output of a
   command you ran. "I believe it exists" is not a finding. A negative claim ("X does not
   exist") needs an exhaustive grep, and you must state the command you ran.
3. **A docstring is not an implementation.** Several of our files *claim* features they
   do not have (e.g. `transfer_service.py` docstring says "WordPress WXR XML" — check the
   body). Verify behaviour, not prose.
4. **An endpoint is not a feature.** A route with no caller anywhere in `frontend/` is a
   gap even if the route exists. Before saying "no consumer", grep for the path as a
   plain string, as a template literal (`` `${base}/x` ``), and as a concatenation.
5. **Count before you count.** Never report "0" / "none" without running the query.
6. Do not re-report things already known-fixed unless you find them broken again.

## Verdict vocabulary
- `PRESENT` — we have a working equivalent of comparable scope
- `PARTIAL` — exists, but narrower than WP (say precisely what is missing)
- `MISSING` — no equivalent anywhere
- `BROKEN` — an endpoint/model/UI exists but the implementation cannot actually work
  (raises, returns a constant, has zero callers that run, guard that never fires)
- `NA` — genuinely WordPress-only (PHP plugin API, .php files, theme.json editor UI shell)

## Output format — return ONLY this, compact
For each feature, one block. Group by the domain I gave you. Be exhaustive inside your
domain; do not stray into other agents' domains.

```
### <Feature name> — <VERDICT>
WP: <what it is, wp-core path:symbol>
OURS: <our path:line, or "none">
EVIDENCE: <the grep/read output that proves the verdict, trimmed>
NOTE: <one line, only when it matters>
```

Then a final section:

```
## DOMAIN SUMMARY
COVERED: <n features>
MISSING: <n>   PARTIAL: <n>   BROKEN: <n>   NA: <n>
TOP 5 (by user impact): <one line each>
FALSE ALARMS I RULED OUT: <claim that looked like a gap but is not, + why>
```

Aim for depth over breadth inside your domain, but do not pad. If a feature genuinely
does not apply to an e-commerce CMS, mark `NA` with one line of justification.
