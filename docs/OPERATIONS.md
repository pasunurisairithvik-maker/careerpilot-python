# Operations
Deploy only after CI passes SQLite/PostgreSQL tests, production security checks and dependency auditing. Build: `pip install -r requirements.txt && python manage.py collectstatic --noinput`. Start: `python ops/start.py`.

Startup checks production security, applies forward migrations, removes expired sessions/rate buckets and starts one Gunicorn worker with four threads. SQL statement/lock/connection waits are bounded. PostgreSQL is mandatory outside DEBUG. Keep DEBUG disabled publicly and SECRET_KEY privately stable. New salted recovery hashes are independent of signing keys, while sessions expire on rotation.

Verify readiness, liveness, public pages and auth-required redirects after deployment. Allow up to 90 seconds and one retry for a cold start. Test private workflows with local disposable synthetic fixtures; never inspect customer records to diagnose a fault.

CSV contains application records; JSON includes resume text and all active/archived applications. Calendar files expose company/role/action, so keep downloads private. Restore/import is outside release scope. Operators must establish encrypted backups and rehearsed recovery before real production reliance; provider retention is not an app backup guarantee.

Rollback means deploying an earlier compatible commit after checking schema compatibility. Do not force-push or reverse migrations automatically. Code rollback cannot undo confirmed user deletion. Do not spend money, change project permissions or contact others during routine maintenance. Daily checks, if configured, would not mean continuous monitoring; no new monitor has been configured for CareerPilot during this release.

## 2.0 discovery and document checks
`sync_jobs` reads fixed employer endpoints, never private account records. Startup runs it after migrations; a 120-second supervisor timeout falls back to cached data. Public readiness requires the account tables, not external feed availability. Users can POST a CSRF-protected refresh; a database lease prevents frequent overlapping requests. There is no always-on feed worker or new monitoring schedule.

Per-board bound: 1,000 postings and 12 MB; six configured boards. Batch upserts preserve first-seen dates. Full successful responses close removed jobs; any fetch/normalization failure retains existing records. Closed public cache records expire after 30 days; private tracked copies do not. Changes to the curated board registry require release review.

Uploaded TXT/DOCX/PDF files are not stored. DOCX expansion capped at 10 MB with no XML entities; PDF parsing occurs in a disposable Linux subprocess limited to 200 MB, six CPU seconds, ten wall seconds, ten pages and 20,000 extracted characters. Only one PDF subprocess per app worker at a time. Free deployment defaults to one worker. PDF worker receives no deployment credentials in its environment. Multi-worker configurations require a resource budget review.

Full JSON backup version 2 also includes resume draft and saved searches. Delete-account cascades these private models. Public jobs do not include user resume data. Do not log text, files, search query values or credentials.
