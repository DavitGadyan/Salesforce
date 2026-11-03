"""Use case 3 — guardrail review of AI-generated (or human) Apex & Flows.

Pipeline: deterministic static checks → Claude confirms/rejects each finding,
adds what rules can't see (logic bugs, hallucinated APIs, weak tests) and
returns corrected code plus a bulk test class.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..core import config, db, llm
from ..rules.apex_checks import check

SYSTEM = """You are a principal Salesforce engineer reviewing Apex and Flow metadata before it reaches production.
Review standards: bulkification (200-record triggers), governor limits, sharing and FLS/CRUD (prefer WITH USER_MODE),
SOQL injection, secrets and Named Credentials, async patterns (Queueable over @future), test quality
(own data, bulk cases, real assertions), and APIs that do not exist in Apex (hallucinations).

You receive the code and the findings of a deterministic static analyser. For every static finding decide whether it
is real (confirmed=true) or a false positive (confirmed=false, explain in `message`). Then add issues the analyser
cannot see. Reference real line numbers from the provided code. Corrected code must compile, keep the original
behaviour, and fix every confirmed issue. If the input is a test class, return the improved test as corrected_code
and an empty test_class. Be precise and terse."""


class ReviewFinding(BaseModel):
    rule: str = Field(description="SCREAMING_SNAKE rule id, reuse the static id when confirming one")
    severity: Literal["critical", "high", "medium", "low"]
    line: int
    message: str
    fix: str
    source: Literal["static", "claude"]
    confirmed: bool


class ReviewResult(BaseModel):
    summary: str
    production_ready: bool
    findings: list[ReviewFinding]
    corrected_code: str
    test_class: str


def run(run_id: str, code: str, filename: str) -> dict:
    static = [f.to_dict() for f in check(code, filename)]
    db.push_progress(run_id, f"Static analysis: {len(static)} findings")
    db.audit("code-review", "static_analysis", f"{len(static)} findings in {filename or 'snippet'}",
             {"rules": [f["rule"] for f in static]}, run_id=run_id)

    if not config.claude_configured():
        return {"engine": "rules", "summary": f"{len(static)} issues found by static analysis, ranked by severity with the fix for each.",
                "production_ready": not any(f["severity"] in ("critical", "high") for f in static),
                "findings": [{**f, "confirmed": True} for f in static], "corrected_code": "", "test_class": ""}

    db.push_progress(run_id, "Claude is reviewing the code and writing fixes…")
    numbered = "\n".join(f"{i:>4}| {l}" for i, l in enumerate(code.splitlines(), start=1))
    static_txt = "\n".join(f"- {f['rule']} ({f['severity']}) line {f['line']}: {f['message']}" for f in static) or "- none"
    result = llm.structured(
        system=SYSTEM,
        prompt=f"File: {filename or 'snippet'}\n\n<code>\n{numbered}\n</code>\n\n<static_findings>\n{static_txt}\n</static_findings>",
        schema=ReviewResult, run_id=run_id, actor="code-review", effort="high", max_tokens=32000,
    )
    db.push_progress(run_id, f"Claude returned {len(result.findings)} findings")
    out = result.model_dump()
    out["engine"] = "claude"
    return out
