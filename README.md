# CareerPilot 2.0

A zero-budget Python job-discovery and private career workspace. Live: https://careerpilot-python-7twk.onrender.com/

## What works
- Unified real openings from six curated employer boards: Stripe, Cloudflare, Datadog, MongoDB (Greenhouse); Palantir and Spotify (Lever).
- Keyword, location, company, developer/analyst/QA/data/support/product role, title-based experience, source, workplace, salary-present, freshness and first-seen filters. Original employer links and source timestamps.
- OPT, STEM OPT, H-1B, green-card/permanent-resident and citizen **listing mention** filters, exact evidence, exclusions, mixed/unknown states and separate sponsorship-statement filters. They do not certify candidate eligibility or legal compliance.
- Duplicate canonical application URL suppression; successfully removed records marked closed; 30-day closed public-cache retention; failures preserve cached jobs.
- Private accounts, recovery codes, bounded application tracking, idempotent track-from-listing, saved searches (10/account) with in-app new-match alerts.
- TXT, DOCX and text-based PDF extraction; explicit parser preview and structural/phrase-evidence checks. No universal ATS rank or invented hiring probability.
- Truthful editable resume builder: entered facts only, target-job skill ordering, draft storage, matching preview, TXT/DOCX downloads.
- CSV exports, full private JSON backup including drafts/searches, calendar reminders requiring user import, confirmed account/application deletion.

## Boundaries
This is a scoped portfolio release, not an Amazon-scale system. Curated employer coverage is not all websites. No LinkedIn/Indeed scraping, job applications, recruiter outreach, paid AI, OCR, email/push delivery, guaranteed eligibility, ATS certification or auto backup restore. Download DOCX and export to PDF using your editor if needed. Exact phrase matching can miss paraphrases and match negated claims; read the supporting lines.

Refresh runs at deployment and on signed-in requests, globally limited to every 30 minutes. There is no always-on scheduler. Failed feeds preserve cached records; source status makes stale data visible. First-seen is CareerPilot's discovery date, not a posting date. Workplace/level/role are heuristics, not verified employer classifications. Salary is displayed only when supplied by the selected endpoint; most boards do not supply it.

## Local run
Python 3.12:
```
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export DEBUG=1
python manage.py migrate
python manage.py sync_jobs
python manage.py runserver
```
SQLite local; persistent PostgreSQL on Render Free + Neon Free. Linux is required for bounded PDF parsing. Run `python manage.py test tracker`; real PostgreSQL and SQLite run in CI, along with deployment security and dependency auditing. Synthetic fixtures only; tests do not access account production data.

## Feed safety
Read-only, fixed allowlisted endpoints. No user-supplied server fetch URL or redirect following. 8-second timeout per feed, at most 12 MB and 1,000 listings per board; oversized/malformed feeds are failures rather than silently truncated success. Three network fetch threads, serialized database batch upserts, maximum 20,000 description characters. Cached feeds with errors remain visibly stale. Public descriptions are stripped to text and template escaped. No provenance claim beyond the endpoint received.

References: [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html), [Lever public Postings API](https://github.com/lever/postings-api). Listings belong to their employers/providers; apply and verify current terms on the original site. This project is not affiliated with HirePilot, employers, or ATS vendors.

See docs/OPERATIONS.md and docs/RELEASE.md for release verification and limits. AI-assisted implementation; the student must understand and demonstrate the code rather than claim unaided authorship.
