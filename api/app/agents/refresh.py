"""Use case 1 — sandbox refresh, data seeding, org-to-org migration and reconciliation.

The deterministic layer builds the checklist, masking plan, seed order, field
mapping and reconciliation from org metadata. Claude then reviews that plan as an
architect: org-specific risks, mapping fixes, and an ordered runbook.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel

from ..connectors import current
from ..core import config, db, llm
from ..rules import refresh as rules

SYSTEM = """You are a Salesforce technical architect who runs sandbox refreshes and org-to-org migrations for
complex orgs (large data volume, many integrations, regulated data). You receive an org inventory and a
rules-generated plan. Add only what is specific to this org and missing from the plan; do not restate it.
For mapping rows with no target or low confidence, recommend a concrete target or a disposition (create field,
archive, do not migrate). The runbook must be ordered, each step verifiable."""


class ExtraCheck(BaseModel):
    category: str
    title: str
    detail: str
    risk: Literal["critical", "high", "medium", "low"]


class MappingReview(BaseModel):
    source_object: str
    source_field: str
    recommendation: str
    rationale: str


class RunbookStep(BaseModel):
    phase: Literal["pre-refresh", "refresh", "post-refresh", "seed", "migrate", "validate", "cutover"]
    action: str
    verification: str


class ArchitectReview(BaseModel):
    executive_summary: str
    extra_checks: list[ExtraCheck]
    mapping_reviews: list[MappingReview]
    risks: list[str]
    runbook: list[RunbookStep]


def build_plan(sample_pct: float = 2.0) -> dict:
    org = current()
    inv = org.inventory()
    return {
        "inventory": inv,
        "checklist": rules.post_refresh_checklist(inv),
        "pii": rules.pii_fields(inv),
        "seed_plan": rules.seed_plan(inv, sample_pct),
        "mapping": rules.field_mapping(org.source_schema(), org.target_schema()),
        "reconciliation": rules.reconcile(org.reconciliation()),
    }


def run(run_id: str, sample_pct: float) -> dict:
    plan = build_plan(sample_pct)
    db.push_progress(run_id, f"Inventory: {len(plan['inventory']['objects'])} objects, {len(plan['checklist'])} checklist items")
    db.audit("refresh-agent", "inventory", "Built rules-based refresh & migration plan",
             {"checklist": len(plan["checklist"]), "pii": len(plan["pii"]), "mapping": len(plan["mapping"])}, run_id=run_id)
    if not config.claude_configured():
        plan["review"] = None
        plan["engine"] = "rules"
        return plan

    db.push_progress(run_id, "Claude is reviewing the plan as an architect…")
    compact = {
        "inventory": {k: plan["inventory"][k] for k in ("org_name", "objects", "integrations", "data_storage_gb", "file_storage_gb")},
        "checklist": [c["title"] for c in plan["checklist"]],
        "pii_fields": [f"{p['object']}.{p['field']}" for p in plan["pii"]],
        "seed_plan": plan["seed_plan"],
        "mapping_gaps": [m for m in plan["mapping"] if m["confidence"] < 90],
        "reconciliation": plan["reconciliation"],
    }
    review = llm.structured(system=SYSTEM, prompt=json.dumps(compact, indent=1), schema=ArchitectReview,
                            run_id=run_id, actor="refresh-agent", effort="high", max_tokens=32000)
    db.push_progress(run_id, f"Architect review: {len(review.extra_checks)} extra checks, {len(review.runbook)} runbook steps")
    plan["review"] = review.model_dump()
    plan["engine"] = "claude"
    return plan
