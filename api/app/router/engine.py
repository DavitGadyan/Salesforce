"""Hybrid AI router: Salesforce is the system of record; each request is routed to
the right place by data sensitivity, stakes, volume and latency.

Policy (first match wins), then a fallback chain over providers that are up:
  1. Answerable from data alone            → Salesforce native (no model)
  2. Contains PHI/PCI                       → private model; else mask + Claude
  3. Contains PII and policy = private-first→ private model; else mask + external
  4. High-stakes narrative                  → Claude Opus (fallback ChatGPT)
  5. Bulk / real-time                       → Claude Haiku (fallback ChatGPT, private)
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass

from ..connectors import current
from ..core import db
from . import trust
from .providers import Completion, ProviderUnavailable, registry


@dataclass
class Workflow:
    id: str
    name: str
    sobject: str
    task: str            # what the model is asked to do
    stakes: str          # low | high
    volume: str          # single | bulk
    latency: str         # realtime | standard
    native: bool = False  # answerable without a model
    max_tokens: int = 350
    system: str = ""


WORKFLOWS = {
    "case-summary": Workflow(
        "case-summary", "Summarise a support case", "Case",
        "Summarise this case for the next agent in 3 bullets: problem, impact, next action.",
        stakes="low", volume="single", latency="standard", max_tokens=380,
        system="You are a Salesforce Service Cloud assistant. Be factual and brief; never invent details."),
    "deal-risk": Workflow(
        "deal-risk", "Deal risk narrative", "Opportunity",
        "Write a 4-sentence deal-risk assessment for the account executive: risk level, the evidence, and the single best next step.",
        stakes="high", volume="single", latency="standard", max_tokens=300,
        system="You are a sales manager reviewing a Salesforce Opportunity. Use only the record's facts."),
    "case-triage": Workflow(
        "case-triage", "Triage all open cases", "Case",
        "Classify the case into one of: Billing, Access, Clinical, Donations, Compliance. Reply as JSON {\"queue\": ..., \"urgency\": 1-5}.",
        stakes="low", volume="bulk", latency="realtime", max_tokens=60,
        system="You classify Salesforce cases. Reply with JSON only."),
    "pipeline-count": Workflow(
        "pipeline-count", "Open pipeline by stage", "Opportunity",
        "Count open opportunities and total amount by stage.", stakes="low", volume="single", latency="realtime", native=True),
}

POLICIES = [
    {"id": "P1", "when": "Question is answerable from data alone", "route": "native", "why": "No model needed: cheaper, exact, zero data exposure"},
    {"id": "P2", "when": "Record contains PHI or card data", "route": "private", "fallback": "mask → claude", "why": "Regulated data stays inside the network (HIPAA/PCI)"},
    {"id": "P3", "when": "Record contains PII", "route": "mask → claude", "fallback": "mask → openai, private", "why": "Names, emails and phones are tokenised before leaving the network"},
    {"id": "P4", "when": "High-stakes narrative", "route": "claude", "fallback": "openai, private", "why": "Best reasoning quality where a wrong answer is costly"},
    {"id": "P5", "when": "Bulk or real-time", "route": "claude-fast", "fallback": "openai, private", "why": "Lowest cost and latency per record"},
]


def records(wf: Workflow) -> list[dict]:
    org = current()
    return org.cases() if wf.sobject == "Case" else org.opportunities()


def _record_text(rec: dict) -> str:
    keep = {k: v for k, v in rec.items() if v not in (None, "") and k not in ("Id", "ContainsPHI", "ContainsPII")}
    return "\n".join(f"{k}: {v}" for k, v in keep.items())


def _names(rec: dict) -> list[str]:
    return [rec.get("ContactName") or ""]


def decide(wf: Workflow, text: str, sc: trust.Scan, prefer: str | None = None) -> dict:
    if wf.native:
        return {"policy": "P1", "chain": ["native"], "mask": False}
    if prefer:
        external = registry()[prefer].data_leaves_network
        return {"policy": "manual", "chain": [prefer], "mask": external and bool(sc.findings)}
    if sc.classes & {"PHI", "PCI"}:
        return {"policy": "P2", "chain": ["private", "claude", "openai"], "mask_external": True}
    if "PII" in sc.classes:
        base = "claude" if wf.stakes == "high" else "claude-fast" if wf.volume == "bulk" else "claude"
        return {"policy": "P3", "chain": [base, "openai", "private"], "mask_external": True}
    if wf.stakes == "high":
        return {"policy": "P4", "chain": ["claude", "openai", "private"], "mask_external": False}
    return {"policy": "P5", "chain": ["claude-fast", "openai", "private"], "mask_external": False}


def _native_answer(wf: Workflow) -> dict:
    opps = [o for o in current().opportunities() if not str(o.get("StageName", "")).startswith("Closed")]
    by = Counter()
    amt = Counter()
    for o in opps:
        by[o["StageName"]] += 1
        amt[o["StageName"]] += o.get("Amount") or 0
    lines = [f"{s}: {by[s]} opportunities, ${amt[s]:,.0f}" for s in sorted(by, key=lambda s: -amt[s])]
    return {"text": "\n".join(lines) + f"\nTotal open: {len(opps)} opportunities, ${sum(amt.values()):,.0f}",
            "soql": "SELECT StageName, COUNT(Id), SUM(Amount) FROM Opportunity WHERE IsClosed = false GROUP BY StageName"}


def run_one(run_id: str | None, wf: Workflow, rec: dict | None, prefer: str | None = None) -> dict:
    providers = registry()
    if wf.native:
        ans = _native_answer(wf)
        db.audit("ai-router", "route", f"{wf.name} → Salesforce native (P1)", {"soql": ans["soql"]}, run_id=run_id)
        return {"workflow": wf.id, "record_id": None, "policy": "P1", "provider": "native", "model": "SOQL",
                "masked": False, "pii": [], "sent_prompt": ans["soql"], "answer": ans["text"], "latency_ms": 40,
                "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0, "attempts": [{"provider": "native", "ok": True}],
                "data_left_network": False}

    text = _record_text(rec)
    sc = trust.scan(text, _names(rec))
    decision = decide(wf, text, sc, prefer)
    attempts = []
    for pid in decision["chain"]:
        p = providers[pid]
        ok, note = p.available()
        if not ok:
            attempts.append({"provider": pid, "ok": False, "reason": note})
            continue
        must_mask = p.data_leaves_network and bool(sc.findings) and (decision.get("mask_external") or decision.get("mask"))
        payload, mapping = trust.mask(text, sc) if must_mask else (text, {})
        note = "\nSome values are masked as tokens like [EMAIL_1]; copy tokens exactly when you refer to them." if mapping else ""
        prompt = f"{wf.task}{note}\n\n<salesforce_record sobject=\"{wf.sobject}\">\n{payload}\n</salesforce_record>"
        try:
            c: Completion = p.complete(wf.system, prompt, wf.max_tokens)
        except ProviderUnavailable as e:
            attempts.append({"provider": pid, "ok": False, "reason": str(e)})
            continue
        attempts.append({"provider": pid, "ok": True})
        answer = trust.unmask(c.text, mapping)
        db.audit("ai-router", "route", f"{wf.name} → {p.label} ({decision['policy']}{', masked' if mapping else ''})",
                 {"record": rec.get("Id"), "pii": [f["kind"] for f in sc.findings], "attempts": attempts,
                  "cost_usd": c.cost_usd, "latency_ms": c.latency_ms},
                 run_id=run_id, model=c.model, input_tokens=c.input_tokens, output_tokens=c.output_tokens)
        return {"workflow": wf.id, "record_id": rec.get("Id"), "policy": decision["policy"], "provider": pid,
                "model": c.model, "masked": bool(mapping), "masked_values": len(mapping),
                "pii": [{"kind": f["kind"], "class": f["class"]} for f in sc.findings],
                "sent_prompt": prompt, "answer": answer, "raw_answer": c.text, "latency_ms": c.latency_ms,
                "cost_usd": c.cost_usd, "input_tokens": c.input_tokens, "output_tokens": c.output_tokens,
                "attempts": attempts, "data_left_network": p.data_leaves_network}
    raise ProviderUnavailable("No provider in the route is available: " + json.dumps(attempts))


def run(run_id: str, workflow_id: str, record_id: str | None, mode: str, prefer: str | None) -> dict:
    wf = WORKFLOWS[workflow_id]
    if mode == "benchmark":
        rec = _find(wf, record_id)
        out = []
        for pid, p in registry().items():
            if pid == "native" or not p.available()[0]:
                continue
            db.push_progress(run_id, f"Benchmark: {p.label}")
            try:
                out.append(run_one(run_id, wf, rec, prefer=pid))
            except ProviderUnavailable as e:
                out.append({"provider": pid, "error": str(e)})
        return {"mode": "benchmark", "workflow": wf.id, "results": out}
    if wf.volume == "bulk":
        results = []
        for rec in records(wf):
            db.push_progress(run_id, f"Routing {rec.get('CaseNumber') or rec['Id']}")
            results.append(run_one(run_id, wf, rec, prefer))
        return {"mode": "bulk", "workflow": wf.id, "results": results}
    rec = None if wf.native else _find(wf, record_id)
    db.push_progress(run_id, f"Routing {wf.name}")
    return {"mode": "single", "workflow": wf.id, "results": [run_one(run_id, wf, rec, prefer)]}


def _find(wf: Workflow, record_id: str | None) -> dict:
    recs = records(wf)
    return next((r for r in recs if r["Id"] == record_id), recs[0])


def catalog() -> dict:
    out = []
    for wf in WORKFLOWS.values():
        recs = [] if wf.native else records(wf)
        out.append({"id": wf.id, "name": wf.name, "sobject": wf.sobject, "stakes": wf.stakes, "volume": wf.volume,
                    "latency": wf.latency, "native": wf.native,
                    "records": [{"id": r["Id"], "label": r.get("Subject") or r.get("Name"),
                                 "sensitivity": sorted(trust.scan(_record_text(r), _names(r)).classes)} for r in recs]})
    return {"workflows": out, "policies": POLICIES, "providers": [p.info() for p in registry().values()]}
