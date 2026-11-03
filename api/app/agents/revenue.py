"""Use case 2 — AI revenue agent on top of the CRM, human-in-the-loop.

For each lead the agent reads the record, scores and tiers it, picks a Next Best
Action and drafts outreach. It cannot change the CRM or send anything: write
tools only create approvals. Drafts are fact-checked against the record — any
claimed fact that is not in the CRM is rejected back to the model.
"""

from __future__ import annotations

from ..connectors import current
from ..core import config, db, llm
from ..rules.dedupe import find_duplicates
from ..rules.scoring import score_lead

ALLOWED_UPDATE_FIELDS = {"Status", "Rating", "LeadSource", "Title", "Industry", "Description"}

SYSTEM = """You are a revenue operations agent working inside the company's Salesforce org.
Goal: turn dormant and open leads into booked meetings, without ever inventing facts.

For EACH lead id you are given:
1. Call get_lead to read the record and its rules-based baseline score.
2. Call record_assessment with your score (0-100), tier (A/B/C), one concrete next best action, short reasons,
   and the CRM field names you relied on. Stay close to the baseline unless the record justifies a change.
3. For tier A and B leads that have an email, call draft_outreach: a short, specific, plain-text email
   (max 110 words, no hype, one clear ask). Every personal detail you mention must be listed in facts_used with the
   exact CRM field and value; anything not in the record must not be in the email.
4. If a field is clearly wrong or should change (e.g. Status, Rating), call propose_crm_update with a reason.

Write tools only queue items for human approval. When every lead is done, reply with a summary of at most 3 short lines in plain text (no markdown), one line per key action."""

TOOLS = [
    {"name": "get_lead", "description": "Read a lead record, its activity, duplicates and the rules-based baseline score.",
     "input_schema": {"type": "object", "properties": {"lead_id": {"type": "string"}}, "required": ["lead_id"],
                      "additionalProperties": False}},
    {"name": "record_assessment", "description": "Save the score, tier and next best action for a lead.",
     "input_schema": {"type": "object", "properties": {
         "lead_id": {"type": "string"}, "score": {"type": "integer"}, "tier": {"type": "string", "enum": ["A", "B", "C"]},
         "next_best_action": {"type": "string"}, "reasons": {"type": "array", "items": {"type": "string"}},
         "sources": {"type": "array", "items": {"type": "string"}, "description": "CRM field names used"}},
         "required": ["lead_id", "score", "tier", "next_best_action", "reasons", "sources"], "additionalProperties": False}},
    {"name": "draft_outreach", "description": "Queue a personalised email for human approval. Facts are verified against the CRM.",
     "input_schema": {"type": "object", "properties": {
         "lead_id": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"},
         "facts_used": {"type": "array", "items": {"type": "object", "properties": {
             "field": {"type": "string"}, "value": {"type": "string"}}, "required": ["field", "value"], "additionalProperties": False}}},
         "required": ["lead_id", "subject", "body", "facts_used"], "additionalProperties": False}},
    {"name": "propose_crm_update", "description": "Queue a field update on the lead for human approval.",
     "input_schema": {"type": "object", "properties": {
         "lead_id": {"type": "string"}, "reason": {"type": "string"},
         "changes": {"type": "array", "items": {"type": "object", "properties": {
             "field": {"type": "string", "enum": sorted(ALLOWED_UPDATE_FIELDS)}, "value": {"type": "string"}},
             "required": ["field", "value"], "additionalProperties": False}}},
         "required": ["lead_id", "reason", "changes"], "additionalProperties": False}},
]


def _verify_facts(lead: dict, facts: list[dict]) -> list[str]:
    problems = []
    for f in facts:
        field, value = f["field"], str(f["value"]).strip().lower()
        if field == "Activity":
            if not any(value in a.lower() or a.lower() in value for a in lead.get("Activity") or []):
                problems.append(f"Activity '{f['value']}' is not in the record")
            continue
        actual = lead.get(field)
        if actual is None:
            problems.append(f"Field {field} is empty or does not exist")
        elif value not in str(actual).lower() and str(actual).lower() not in value:
            problems.append(f"{field} is '{actual}', not '{f['value']}'")
    return problems


def _name(lead: dict) -> str:
    return f"{lead.get('FirstName') or ''} {lead.get('LastName') or ''}".strip()


def pick_leads(limit: int) -> list[str]:
    """Default worklist: best baseline scores first, skipping leads already assessed."""
    done = db.assessments()
    scored = [(score_lead(l)["score"], l["Id"]) for l in current().leads() if l["Id"] not in done]
    return [i for _, i in sorted(scored, reverse=True)[:limit]]


def run(run_id: str, lead_ids: list[str]) -> dict:
    org = current()
    dupes = {rid: c for c in find_duplicates(org.leads()) for rid in c["record_ids"]}
    engine = "claude" if config.claude_configured() else "rules"
    counters = {"assessed": 0, "drafts": 0, "updates": 0, "rejected_drafts": 0}

    def get_lead(inp: dict) -> dict:
        lead = org.get_lead(inp["lead_id"])
        if not lead:
            raise ValueError("lead not found")
        cluster = dupes.get(lead["Id"])
        return {"lead": lead, "baseline": score_lead(lead),
                "possible_duplicates": [i for i in cluster["record_ids"] if i != lead["Id"]] if cluster else []}

    def record_assessment(inp: dict) -> str:
        db.save_assessment(inp["lead_id"], run_id, max(0, min(100, inp["score"])), inp["tier"], inp["next_best_action"],
                           inp["reasons"], inp["sources"], engine)
        counters["assessed"] += 1
        db.push_progress(run_id, f"Scored {inp['lead_id']} → tier {inp['tier']} ({inp['score']})")
        return "saved"

    def draft_outreach(inp: dict) -> str:
        lead = org.get_lead(inp["lead_id"])
        if not lead or not lead.get("Email"):
            raise ValueError("lead has no email; propose enrichment instead")
        problems = _verify_facts(lead, inp["facts_used"])
        if problems:
            counters["rejected_drafts"] += 1
            db.audit("revenue-agent", "guardrail", f"Draft for {inp['lead_id']} rejected: unverified facts", problems, run_id=run_id)
            raise ValueError("Unverified facts — rewrite without them: " + "; ".join(problems))
        db.create_approval("send_email", inp["lead_id"], f"Email to {_name(lead)} ({lead['Company']})",
                           {"to": lead["Email"], "subject": inp["subject"], "body": inp["body"], "facts_used": inp["facts_used"]},
                           "Drafted by revenue agent; all facts verified against CRM.", run_id)
        counters["drafts"] += 1
        db.push_progress(run_id, f"Drafted email to {_name(lead)}")
        return "queued for approval"

    def propose_crm_update(inp: dict) -> str:
        lead = org.get_lead(inp["lead_id"])
        if not lead:
            raise ValueError("lead not found")
        fields = {c["field"]: c["value"] for c in inp["changes"] if c["field"] in ALLOWED_UPDATE_FIELDS}
        db.create_approval("update_record", inp["lead_id"], f"Update {_name(lead)}: {', '.join(fields)}",
                           {"sobject": "Lead", "fields": fields, "before": {k: lead.get(k) for k in fields}},
                           inp["reason"], run_id)
        counters["updates"] += 1
        return "queued for approval"

    if config.claude_configured():
        db.push_progress(run_id, f"Claude agent started on {len(lead_ids)} leads")
        summary = llm.tool_loop(
            system=SYSTEM, prompt="Work these lead ids in order:\n" + "\n".join(lead_ids),
            tools=TOOLS, run_id=run_id, actor="revenue-agent",
            handlers={"get_lead": get_lead, "record_assessment": record_assessment,
                      "draft_outreach": draft_outreach, "propose_crm_update": propose_crm_update},
            max_turns=12 + 5 * len(lead_ids), on_progress=lambda m: db.push_progress(run_id, m))
        return {"engine": "claude", "summary": summary, **counters}

    # Rules engine (no API key): same tools, deterministic content.
    db.push_progress(run_id, f"Rules engine started on {len(lead_ids)} leads")
    for lead_id in lead_ids:
        data = get_lead({"lead_id": lead_id})
        lead, base = data["lead"], data["baseline"]
        record_assessment({"lead_id": lead_id, "score": base["score"], "tier": base["tier"],
                           "next_best_action": base["next_best_action"], "reasons": base["reasons"], "sources": base["sources"]})
        if base["tier"] in ("A", "B") and lead.get("Email"):
            hook = next((a for a in lead.get("Activity") or [] if a != "No activity"), None)
            facts = [{"field": "Company", "value": lead["Company"]}, {"field": "Title", "value": lead.get("Title") or ""}]
            line = f"I noticed: {hook.lower()}." if hook else f"As {lead.get('Title') or 'a leader'} at {lead['Company']}, this may be timely."
            if hook:
                facts.append({"field": "Activity", "value": hook})
            draft_outreach({"lead_id": lead_id, "subject": f"Quick idea for {lead['Company']}",
                            "body": f"Hi {lead.get('FirstName') or 'there'},\n\n{line} We help teams like {lead['Company']} "
                                    "automate Salesforce data work so reps spend time selling.\n\nWorth a 20-minute call next week?\n\nBest,\nDana",
                            "facts_used": facts})
        if base["tier"] == "A" and lead.get("Status") == "Open - Not Contacted":
            propose_crm_update({"lead_id": lead_id, "reason": "High-fit lead never contacted; flag as hot for the owner.",
                                "changes": [{"field": "Rating", "value": "Hot"}, {"field": "Status", "value": "Working - Contacted"}]})
    return {"engine": "rules", "summary": f"Assessed {counters['assessed']} leads, queued {counters['drafts']} emails and "
                                          f"{counters['updates']} updates for approval.", **counters}


def queue_merges(run_id: str) -> dict:
    clusters = find_duplicates(current().leads())
    for c in clusters:
        names = sorted({_name(r) for r in c["records"]})
        db.create_approval("merge_records", c["survivor_id"], f"Merge {len(c['record_ids'])} records: {' / '.join(names)}",
                           {"sobject": "Lead", "survivor_id": c["survivor_id"], "record_ids": c["record_ids"],
                            "records": c["records"], "confidence": c["confidence"]},
                           "; ".join(sorted({r['reason'] for r in c["reasons"]})), run_id)
    db.push_progress(run_id, f"Queued {len(clusters)} merge proposals")
    return {"engine": "rules", "clusters": len(clusters)}
