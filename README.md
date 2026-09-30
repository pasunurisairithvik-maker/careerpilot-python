# CareerPilot 1.0

A private job-seeker workspace built with Python, Django and PostgreSQL. AI-assisted portfolio project. No invented user numbers, employment outcomes or research claims.

## Completed release scope
- Private username/password accounts, normalized sign-in, CSRF, server-side sessions, bounded authentication attempts and single-use recovery codes. Recovery hashes survive signing-key rotation.
- Save/edit applications, original job URLs and descriptions, seven stages, search/filter, next actions, due and overdue views, reversible archive and password-confirmed deletion.
- Paste a resume or import UTF-8 `.txt`, bounded at 20,000 characters. Resume text is not sent to an AI provider.
- Explainable phrase matching against a versioned dictionary or up to 30 custom requirements. Every match shows its exact supporting resume line. No artificial ATS or hiring-probability score.
- CSV export with formula protection, complete private JSON download, calendar export with one-day-before alerts, account timezone/password/recovery management and confirmed permanent account deletion.
- PostgreSQL constraints, owner-scoped idempotent form submissions, request IDs, private-data-excluding logs, generic database-unavailable responses and separate readiness/liveness.

This is a completed first release for the scope above, not the existing HirePilot commercial product. No affiliation is claimed. It is not independently security audited or validated at enterprise traffic levels.

## Local use
```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
DEBUG=1 .venv/bin/python manage.py migrate
DEBUG=1 .venv/bin/python manage.py collectstatic --noinput
DEBUG=1 .venv/bin/python manage.py runserver
DEBUG=1 .venv/bin/python manage.py test
```
SQLite is local-only. Production requires a private strong SECRET_KEY, persistent PostgreSQL DATABASE_URL and a provider hostname. Never commit credentials or real resumes. Local and CI tests use isolated synthetic fixtures.

## Honest limits
100 accounts; 100 applications per account including archive; resume and description each 20,000 characters; `.txt` import maximum 80 KB. No PDF/DOCX parser, browser extension, automatic scraping or submissions, recruiter messages, paid AI calls, email delivery, background push notifications, automatic backup import or guaranteed uptime. Calendar reminders work only after the user imports the file into their calendar. Free hosting sleeps and can take about a minute to wake.

Phrase coverage means text overlap. It does not establish proficiency, eligibility, experience duration or hiring probability. Negated statements can be matched; the exact evidence line is displayed for human review. Synonyms outside the dictionary can be missed. Use custom phrases when necessary.

See [release checks](docs/RELEASE.md), [architecture](docs/ARCHITECTURE.md), [operations](docs/OPERATIONS.md), and [matching evaluation](docs/EVALUATION.md).
