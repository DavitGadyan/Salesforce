"""Trust layer: detect sensitive data in Salesforce records and mask it before a
prompt leaves the network; restore the real values in the answer afterwards."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("email", "PII", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
    ("phone", "PII", re.compile(r"(?<![\w-])(?:\+\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?![\w-])")),
    ("dob", "PHI", re.compile(r"\b(?:DOB|date of birth)[:\s]*\d{4}-\d{2}-\d{2}\b", re.I)),
    ("member_id", "PHI", re.compile(r"\b(?:member ID|insurance)[^,.;]*?\b[A-Z]{2,5}-\d{6,}\b", re.I)),
    ("medication", "PHI", re.compile(r"\b(?:metformin|lisinopril|insulin|atorvastatin|warfarin)\b[^,.;)]*", re.I)),
    ("card", "PCI", re.compile(r"\bcard (?:ending|number)\s*\d{4}\b", re.I)),
    ("address", "PII", re.compile(r"\b\d{1,5}\s+\w+(?:\s\w+)*\s(?:Street|St|Avenue|Ave|Road|Rd|Blvd)\b[^.;]*", re.I)),
]


@dataclass
class Scan:
    findings: list[dict] = field(default_factory=list)

    @property
    def classes(self) -> set[str]:
        return {f["class"] for f in self.findings}


def scan(text: str, names: list[str] | None = None) -> Scan:
    s = Scan()
    for kind, cls, pat in PATTERNS:
        for m in pat.finditer(text):
            s.findings.append({"kind": kind, "class": cls, "value": m.group(0)})
    for n in names or []:
        if n and n in text:
            s.findings.append({"kind": "person", "class": "PII", "value": n})
    seen, out = set(), []
    for f in sorted(s.findings, key=lambda f: -len(f["value"])):
        if f["value"] not in seen:
            seen.add(f["value"])
            out.append(f)
    s.findings = out
    return s


def mask(text: str, sc: Scan) -> tuple[str, dict[str, str]]:
    """Replace each sensitive value with a stable token like [EMAIL_1]."""
    mapping: dict[str, str] = {}
    counters: dict[str, int] = {}
    for f in sc.findings:  # longest first, so names inside emails don't double-mask
        if f["value"] not in text:
            continue
        counters[f["kind"]] = counters.get(f["kind"], 0) + 1
        token = f"[{f['kind'].upper()}_{counters[f['kind']]}]"
        mapping[token] = f["value"]
        text = text.replace(f["value"], token)
    return text, mapping


def unmask(text: str, mapping: dict[str, str]) -> str:
    for token, value in mapping.items():
        text = text.replace(token, value)
    return text
