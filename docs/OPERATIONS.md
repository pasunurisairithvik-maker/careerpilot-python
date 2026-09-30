# Operations
Deploy only after CI passes SQLite/PostgreSQL tests, production security checks and dependency auditing. Build: `pip install -r requirements.txt && python manage.py collectstatic --noinput`. Start: `python ops/start.py`.

Startup checks production security, applies forward migrations, removes expired sessions/rate buckets and starts one Gunicorn worker with four threads. SQL statement/lock/connection waits are bounded. PostgreSQL is mandatory outside DEBUG. Keep DEBUG disabled publicly and SECRET_KEY privately stable. New salted recovery hashes are independent of signing keys, while sessions expire on rotation.

Verify readiness, liveness, public pages and auth-required redirects after deployment. Allow up to 90 seconds and one retry for a cold start. Test private workflows with local disposable synthetic fixtures; never inspect customer records to diagnose a fault.

CSV contains application records; JSON includes resume text and all active/archived applications. Calendar files expose company/role/action, so keep downloads private. Restore/import is outside release scope. Operators must establish encrypted backups and rehearsed recovery before real production reliance; provider retention is not an app backup guarantee.

Rollback means deploying an earlier compatible commit after checking schema compatibility. Do not force-push or reverse migrations automatically. Code rollback cannot undo confirmed user deletion. Do not spend money, change project permissions or contact others during routine maintenance. Daily checks, if configured, would not mean continuous monitoring; no new monitor has been configured for CareerPilot during this release.
