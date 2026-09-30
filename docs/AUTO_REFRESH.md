# Public job refresh
GitHub Actions runs refresh-jobs.yml every three hours at minute 17 UTC. It wakes the public health endpoint with bounded retries. When due, the web process starts a daemon thread that reads only fixed public employer feeds; no account or resume credentials are sent to GitHub. A database row lock enforces a shared refresh lease. Manual refresh retains its thirty-minute cooldown.

GitHub scheduled runs can be delayed or dropped and scheduled workflows on inactive public repositories can be disabled by GitHub. Render Free can sleep. This is best-effort refresh, not a precise deadline or uptime guarantee. Each feed displays its last success and keeps its prior records on failure. CI and local DEBUG mode disable automatic network refresh by default. Set AUTO_JOB_REFRESH=0 to disable.

Role categories are title-based and sponsorship labels summarize textual employer statements. Unknown does not imply sponsorship or immigration eligibility. Source counts are not a completeness claim.

Seven additional Greenhouse boards were verified on 2026-09-30: Asana 94, Zscaler 367, Okta 360, Rubrik 127, Gusto 100, Brex 268, Elastic 391. These are source observations, not permanent totals. Three rejected board endpoints were not added.

A 170-minute due threshold allows ten minutes of scheduler jitter around the three-hour cadence, avoiding an accidental six-hour interval when a prior run started a few seconds late.
