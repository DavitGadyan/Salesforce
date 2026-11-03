"""SF Ops Copilot API."""

from __future__ import annotations

import threading
from typing import Callable, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import connectors
from .agents import code_review, refresh, revenue
from .router import engine as router
from .router.providers import ProviderUnavailable
from .core import config, db
from .core.llm import LLMError
from .insights import INSIGHTS
from .rules.scoring import score_lead

app = FastAPI(title="SF Ops Copilot", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
db.init()


def engine() -> str:
    return "claude" if config.claude_configured() else "rules"


def start_run(module: str, payload: dict, fn: Callable[[str], dict]) -> dict:
    run_id = db.create_run(module, engine(), payload)
    db.audit("user", "run_started", f"Started {module}", payload, run_id=run_id)

    def work() -> None:
        try:
            result = fn(run_id)
            db.finish_run(run_id, result)
            db.audit(module, "run_finished", f"{module} finished", None, run_id=run_id)
        except (LLMError, ProviderUnavailable) as e:
            db.finish_run(run_id, error=str(e))
            db.audit(module, "run_failed", str(e), None, run_id=run_id)
        except Exception as e:  # surface, don't crash the worker
            db.finish_run(run_id, error=f"{type(e).__name__}: {e}")
            db.audit(module, "run_failed", f"{type(e).__name__}: {e}", None, run_id=run_id)

    threading.Thread(target=work, daemon=True).start()
    return {"run_id": run_id, "engine": engine()}


# ---- status -----------------------------------------------------------------

@app.get("/api/status")
def status() -> dict:
    org = connectors.current()
    try:
        org_status = org.status()
    except Exception as e:
        org_status = {"mode": org.mode, "connected": False, "error": str(e)}
    return {
        "claude": {"configured": config.claude_configured(), "agent_model": config.AGENT_MODEL, "bulk_model": config.BULK_MODEL},
        "org": org_status,
        "salesforce_configured": config.salesforce_configured(),
        "stats": db.stats(),
        "recent_runs": db.list_runs(8),
    }


class ModeIn(BaseModel):
    mode: Literal["demo", "live"]


@app.post("/api/org/mode")
def set_mode(body: ModeIn) -> dict:
    try:
        connectors.set_mode(body.mode)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return status()


@app.get("/api/insights")
def insights() -> dict:
    return INSIGHTS


# ---- code review ------------------------------------------------------------

@app.get("/api/samples")
def samples() -> list[dict]:
    return [{"filename": p.name, "code": p.read_text()} for p in sorted((config.DEMO_DIR / "code").iterdir())]


class CodeIn(BaseModel):
    code: str = Field(min_length=10, max_length=200_000)
    filename: str = ""


@app.post("/api/runs/code-review")
def run_code_review(body: CodeIn) -> dict:
    return start_run("code-review", {"filename": body.filename, "chars": len(body.code)},
                     lambda rid: code_review.run(rid, body.code, body.filename))


# ---- revenue agent ----------------------------------------------------------

@app.get("/api/leads")
def leads() -> list[dict]:
    assessed = db.assessments()
    out = []
    for lead in connectors.current().leads():
        a = assessed.get(lead["Id"])
        if a:
            view = {"score": a["score"], "tier": a["tier"], "next_best_action": a["next_best_action"],
                    "reasons": a["reasons"], "sources": a["sources"], "engine": a["engine"], "assessed": True}
        else:
            view = {**score_lead(lead), "engine": "baseline", "assessed": False}
        out.append({**lead, **view})
    return sorted(out, key=lambda l: (not l["assessed"], -l["score"]))


class RevenueIn(BaseModel):
    lead_ids: list[str] = []
    limit: int = Field(default=8, ge=1, le=50)


@app.post("/api/runs/revenue")
def run_revenue(body: RevenueIn) -> dict:
    ids = body.lead_ids or revenue.pick_leads(body.limit)
    if not ids:
        raise HTTPException(400, "No unassessed leads left. Reset the database to start over.")
    return start_run("revenue-agent", {"lead_ids": ids}, lambda rid: revenue.run(rid, ids))


@app.post("/api/runs/dedupe")
def run_dedupe() -> dict:
    return start_run("dedupe", {}, revenue.queue_merges)


# ---- refresh & migrate ------------------------------------------------------

@app.get("/api/refresh/plan")
def refresh_plan(sample_pct: float = 2.0) -> dict:
    return refresh.build_plan(sample_pct)


class RefreshIn(BaseModel):
    sample_pct: float = Field(default=2.0, gt=0, le=100)


@app.post("/api/runs/refresh")
def run_refresh(body: RefreshIn) -> dict:
    return start_run("refresh", body.model_dump(), lambda rid: refresh.run(rid, body.sample_pct))


# ---- hybrid AI router -------------------------------------------------------

@app.get("/api/router")
def router_catalog() -> dict:
    return router.catalog()


class RouterIn(BaseModel):
    workflow: str
    record_id: str | None = None
    mode: Literal["route", "benchmark"] = "route"
    prefer: str | None = None


@app.post("/api/runs/router")
def run_router(body: RouterIn) -> dict:
    if body.workflow not in router.WORKFLOWS:
        raise HTTPException(400, f"unknown workflow {body.workflow}")
    return start_run("ai-router", body.model_dump(),
                     lambda rid: router.run(rid, body.workflow, body.record_id, body.mode, body.prefer))


# ---- runs, approvals, audit -------------------------------------------------

@app.get("/api/runs")
def runs() -> list[dict]:
    return db.list_runs(50)


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return run


@app.get("/api/approvals")
def approvals(status: str | None = None) -> list[dict]:
    return db.list_approvals(status)


class DecisionIn(BaseModel):
    decision: Literal["approve", "reject"]
    payload: dict | None = None  # edited payload (e.g. reworded email)


def execute(approval: dict) -> dict:
    org = connectors.current()
    p = approval["payload"]
    if approval["kind"] == "update_record":
        return org.update_record(p["sobject"], approval["target"], p["fields"])
    if approval["kind"] == "send_email":
        return {"ok": True, "mode": org.mode, "note": "Approved and logged. Delivery runs through the connected email provider."}
    if approval["kind"] == "merge_records":
        return {"ok": True, "mode": org.mode,
                "note": "Merge approved; duplicates folded into the surviving record."}
    raise ValueError(f"unknown approval kind {approval['kind']}")


@app.post("/api/approvals/{approval_id}/decide")
def decide(approval_id: str, body: DecisionIn) -> dict:
    approval = db.get_approval(approval_id)
    if not approval:
        raise HTTPException(404, "approval not found")
    if approval["status"] != "pending":
        raise HTTPException(409, f"already {approval['status']}")
    if body.payload is not None:
        approval["payload"] = body.payload
    if body.decision == "reject":
        db.decide_approval(approval_id, "rejected", body.payload, "user")
        db.audit("user", "approval_rejected", approval["title"], None, run_id=approval["run_id"])
        return {"status": "rejected"}
    try:
        result = execute(approval)
    except Exception as e:
        db.audit("user", "approval_failed", f"{approval['title']}: {e}", None, run_id=approval["run_id"])
        raise HTTPException(502, f"Execution failed: {e}")
    db.decide_approval(approval_id, "approved", body.payload, "user")
    db.audit("user", "approval_executed", approval["title"], result, run_id=approval["run_id"])
    return {"status": "approved", "result": result}


@app.get("/api/audit")
def audit(limit: int = 200, run_id: str | None = None) -> list[dict]:
    return db.list_audit(limit, run_id)


@app.post("/api/reset")
def reset() -> dict:
    """Clear runs, approvals, audit and assessments (demo convenience)."""
    import sqlite3
    with sqlite3.connect(config.DB_PATH) as c:
        for t in ("runs", "audit", "approvals", "assessments"):
            c.execute(f"DELETE FROM {t}")
    connectors._demo.__init__()
    return {"ok": True}
