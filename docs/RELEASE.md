# Release acceptance
Require real PostgreSQL and SQLite CI success, startup security checks, no pending schema changes and a dependency audit. Workflow tests cover owner isolation, CSRF, authentication/recovery, quota/archive/deletion, safe URLs, resume upload bounds, exports, evidence context and duplicate submission. These tests are bounded evidence, not proof of all possible conditions.

Public deployment checks verify 200 homepage/readiness/liveness and sign-in redirects on private routes. No paid resource, email campaign, recruiter outreach or customer fixture is created.

Known unsupported behavior is documented in README and the in-app privacy page. No buttons are advertised for unavailable scraping, extension, email or AI features. The first release uses deterministic matching; a scientific ML benchmark would require a suitable labeled corpus, baselines and reproducible held-out evaluation. No paper or publication is claimed.

## 2.0 scope
Live job discovery, saved-search in-app alerts, text-only eligibility evidence, local parser diagnostics, reviewed resume builder and DOCX/TXT exports. Tests cover cache preservation/closure, normalization, safe links, filter combinations/unknowns, URL deduplication, owner isolation, quotas, tracking idempotence/CSRF, upload corruption/limits/scanned PDFs, builder round-trip/no invented skills, backup completeness and cascading private deletion. Live feed counts are observations at a check time, not fixed benchmark claims. Neither legal eligibility nor ATS selection performance has been established.
