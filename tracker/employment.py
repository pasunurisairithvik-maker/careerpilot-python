"""Independent employment and engagement labels from explicit listing wording."""
import re

EMPLOYMENT = [('full_time', 'Full-time'), ('part_time', 'Part-time'), ('contract', 'Contract'), ('temporary', 'Temporary'), ('internship', 'Internship'), ('unknown', 'Not stated')]
ENGAGEMENT = [('w2', 'W-2'), ('1099', '1099 / independent contractor'), ('c2c', 'C2C / corp-to-corp'), ('unknown', 'Not stated')]

def terms(title, description):
    text = '\n'.join([title or '', description or ''])
    patterns = {
        'full_time': r'\bfull[- ]time\b',
        'part_time': r'\bpart[- ]time\b',
        'contract': r'\bcontract(?:or)? (?:role|position|job|opportunity|employment)\b|\b(?:role|position|job|employment type)\s*[:–-]?\s*contract\b|\bcontract[- ]to[- ]hire\b',
        'temporary': r'\btemporary (?:role|position|job|employment)\b|\b(?:employment type|job type)\s*:\s*temporary\b',
        'internship': r'\binternship (?:role|position|job|opportunity)\b|\b(?:employment type|job type)\s*:\s*internship\b|\bthis is an? internship\b',
        'w2': r'\bW[- ]?2\b',
        '1099': r'\b1099\b|\bindependent contractor\b',
        'c2c': r'\bC2C\b|\bcorp[- ]to[- ]corp\b',
    }
    found = {'internship': (title or '')[:500]} if re.search(r'\bintern(?:ship)?\b', title or '', re.I) else {}
    for line in re.split(r'\n|(?<=[.!?])\s+', text):
        for key, pattern in patterns.items():
            match = re.search(pattern, line, re.I)
            if not match:
                continue
            before = line[max(0, match.start()-35):match.start()]
            after = line[match.end():match.end()+35]
            if re.search(r'\b(?:no|not|without|exclude|excluding)\s*(?:accepting\s+)?$', before, re.I) or re.match(r'\s+(?:is |are )?(?:not accepted|not available|not offered|not eligible)', after, re.I):
                continue
            found.setdefault(key, line.strip()[:500])
    # These dimensions can overlap (for example full-time W-2 contract).
    return {'employment': [(label, found[key]) for key, label in EMPLOYMENT if key in found], 'engagement': [(label, found[key]) for key, label in ENGAGEMENT if key in found], 'keys': set(found)}
