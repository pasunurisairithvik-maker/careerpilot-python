"""Conservative experience extraction and readable plain-text job presentation."""
import re

YEAR_REQUIREMENT = re.compile(
    r"\b(?:(?:at\s+least|minimum(?:\s+of)?|a\s+minimum\s+of)\s+)?"
    r"(\d{1,2})\s*(?:\+|(?:-|–|—|to)\s*\d{1,2})?\s*"
    r"(?:years?|yrs?)\s*(?:of\s+)?(?:relevant\s+|professional\s+|related\s+|"
    r"hands[- ]on\s+|prior\s+|work\s+|industry\s+|practical\s+){0,3}experience\b",
    re.I,
)

def experience_requirement(text):
    """Extract stated years conservatively; preferred years still flag review."""
    matches = list(YEAR_REQUIREMENT.finditer(text or ""))
    if not matches:
        return None
    values = [int(m.group(1)) for m in matches if int(m.group(1)) <= 40]
    if not values:
        return None
    minimum = max(values)
    match = next(m for m in matches if int(m.group(1)) == minimum)
    start = max((text or "").rfind("\n", 0, match.start()), (text or "").rfind(".", 0, match.start())) + 1
    end = (text or "").find("\n", match.end())
    if end < 0:
        end = (text or "").find(".", match.end())
    if end < 0:
        end = min(len(text), match.end() + 150)
    return {"years": minimum, "quote": text[start:end].strip()[:500]}

SECTION = re.compile(
    r"(?:^|\n)\s*(Who we are|The role|About the role|About us|What you.ll do|"
    r"Responsibilities|What you.ll need|Requirements|Qualifications|"
    r"Preferred qualifications|Nice to have|Compensation and Benefits|"
    r"Benefits|Internal Employees|Equal opportunity)\s*:?\s*(?:\n|$)", re.I
)

def description_sections(text):
    text = text or ""
    # Some feeds collapse HTML whitespace; only recognize explicit colon headings.
    text = re.sub(
        r"(?<!\n)\s+(The role|What you.ll do|What you.ll need|Responsibilities|"
        r"Requirements|Qualifications|Benefits|Internal Employees)\s*:",
        lambda m: "\n" + m.group(1) + ":\n", text, flags=re.I
    )
    matches = list(SECTION.finditer(text))
    if not matches:
        return [{"heading": "About this opportunity", "paragraphs": [x.strip() for x in text.split("\n") if x.strip()]}]
    sections = []
    lead = text[:matches[0].start()].strip()
    if lead:
        sections.append({"heading": "About the company", "paragraphs": [x.strip() for x in lead.split("\n") if x.strip()]})
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[match.end():end].strip()
        if content:
            sections.append({"heading": match.group(1).strip().rstrip(":"), "paragraphs": [x.strip() for x in content.split("\n") if x.strip()]})
    return sections

def authorization_rows(evidence):
    labels = {"opt": "OPT", "stem_opt": "STEM OPT", "h1b": "H-1B",
              "green_card": "Permanent residency", "citizen": "US citizenship",
              "sponsorship": "Visa sponsorship"}
    return [{"label": label, "state": evidence[key].get("state", "unknown"),
             "quotes": evidence[key].get("evidence", [])}
            for key, label in labels.items()
            if isinstance(evidence.get(key), dict) and evidence[key].get("evidence")]
