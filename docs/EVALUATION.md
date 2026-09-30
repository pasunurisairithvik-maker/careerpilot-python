# Matching diagnostic evidence
Run `python tools/evaluate_matching.py`. The adjacent JSON contains every input, expected label and observed result for ten authored synthetic cases. These cases were created while implementing the matcher, are not held out and do not represent applicant populations. No real resumes, copyrighted dataset or publications are used.

The set deliberately includes a negated Java statement and an unsupported OS abbreviation. Inspect false positives and false negatives in the generated report; do not discard them to improve metrics. Phrase boundaries prevent matching Java inside JavaScript and Git inside legitimate. Dictionary aliases help with Postgres/PostgreSQL and pytest/unit testing.

Neither synthetic precision/recall nor the in-app phrase coverage predicts employer screening or hiring outcomes. A future ML project would need consented/licensed data, frozen splits, baselines, subgroup/error analysis and reproducible evaluation before claiming superiority.
