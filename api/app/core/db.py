"""SQLite persistence for runs, the audit log and the approval queue.

Every agent decision and tool call lands in `audit`; every write to the CRM is an
`approvals` row that only executes after a human approves it.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from .config import DB_PATH

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY, module TEXT NOT NULL, status TEXT NOT NULL,
    engine TEXT NOT NULL, input TEXT, result TEXT, error TEXT,
    progress TEXT DEFAULT '[]', created_at TEXT NOT NULL, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, at TEXT NOT NULL,
    actor TEXT NOT NULL, kind TEXT NOT NULL, summary TEXT NOT NULL,
    detail TEXT, model TEXT, input_tokens INTEGER, output_tokens INTEGER
);
CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY, run_id TEXT, created_at TEXT NOT NULL, kind TEXT NOT NULL,
    target TEXT NOT NULL, title TEXT NOT NULL, payload TEXT NOT NULL,
    rationale TEXT, status TEXT NOT NULL DEFAULT 'pending', decided_at TEXT, decided_by TEXT
);
CREATE TABLE IF NOT EXISTS assessments (
    lead_id TEXT PRIMARY KEY, run_id TEXT, score INTEGER, tier TEXT,
    next_best_action TEXT, reasons TEXT, sources TEXT, engine TEXT, updated_at TEXT
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with _lock, _conn() as c:
        c.executescript(SCHEMA)


def _rows(sql: str, args: tuple = ()) -> list[dict]:
    with _lock, _conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def _exec(sql: str, args: tuple = ()) -> None:
    with _lock, _conn() as c:
        c.execute(sql, args)


def _loads(row: dict, *keys: str) -> dict:
    for k in keys:
        if row.get(k):
            row[k] = json.loads(row[k])
    return row


# ---- runs -------------------------------------------------------------------

def create_run(module: str, engine: str, payload: Any) -> str:
    run_id = uuid.uuid4().hex[:12]
    _exec("INSERT INTO runs (id, module, status, engine, input, created_at) VALUES (?,?,?,?,?,?)",
          (run_id, module, "running", engine, json.dumps(payload), now()))
    return run_id


def push_progress(run_id: str, message: str) -> None:
    with _lock, _conn() as c:
        row = c.execute("SELECT progress FROM runs WHERE id=?", (run_id,)).fetchone()
        progress = json.loads(row["progress"]) if row else []
        progress.append({"at": now(), "message": message})
        c.execute("UPDATE runs SET progress=? WHERE id=?", (json.dumps(progress), run_id))


def finish_run(run_id: str, result: Any = None, error: str | None = None) -> None:
    _exec("UPDATE runs SET status=?, result=?, error=?, finished_at=? WHERE id=?",
          ("failed" if error else "done", json.dumps(result) if result is not None else None, error, now(), run_id))


def get_run(run_id: str) -> dict | None:
    rows = _rows("SELECT * FROM runs WHERE id=?", (run_id,))
    return _loads(rows[0], "input", "result", "progress") if rows else None


def list_runs(limit: int = 20) -> list[dict]:
    rows = _rows("SELECT id, module, status, engine, created_at, finished_at, error FROM runs ORDER BY created_at DESC LIMIT ?", (limit,))
    return rows


# ---- audit ------------------------------------------------------------------

def audit(actor: str, kind: str, summary: str, detail: Any = None, run_id: str | None = None,
          model: str | None = None, input_tokens: int | None = None, output_tokens: int | None = None) -> None:
    _exec("INSERT INTO audit (run_id, at, actor, kind, summary, detail, model, input_tokens, output_tokens) VALUES (?,?,?,?,?,?,?,?,?)",
          (run_id, now(), actor, kind, summary, json.dumps(detail, default=str) if detail is not None else None,
           model, input_tokens, output_tokens))


def list_audit(limit: int = 200, run_id: str | None = None) -> list[dict]:
    if run_id:
        rows = _rows("SELECT * FROM audit WHERE run_id=? ORDER BY id DESC LIMIT ?", (run_id, limit))
    else:
        rows = _rows("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,))
    return [_loads(r, "detail") for r in rows]


# ---- approvals --------------------------------------------------------------

def create_approval(kind: str, target: str, title: str, payload: dict, rationale: str, run_id: str | None) -> str:
    approval_id = uuid.uuid4().hex[:12]
    _exec("INSERT INTO approvals (id, run_id, created_at, kind, target, title, payload, rationale) VALUES (?,?,?,?,?,?,?,?)",
          (approval_id, run_id, now(), kind, target, title, json.dumps(payload), rationale))
    return approval_id


def get_approval(approval_id: str) -> dict | None:
    rows = _rows("SELECT * FROM approvals WHERE id=?", (approval_id,))
    return _loads(rows[0], "payload") if rows else None


def list_approvals(status: str | None = None) -> list[dict]:
    if status:
        rows = _rows("SELECT * FROM approvals WHERE status=? ORDER BY created_at DESC", (status,))
    else:
        rows = _rows("SELECT * FROM approvals ORDER BY created_at DESC")
    return [_loads(r, "payload") for r in rows]


def decide_approval(approval_id: str, status: str, payload: dict | None, by: str) -> None:
    if payload is not None:
        _exec("UPDATE approvals SET status=?, payload=?, decided_at=?, decided_by=? WHERE id=?",
              (status, json.dumps(payload), now(), by, approval_id))
    else:
        _exec("UPDATE approvals SET status=?, decided_at=?, decided_by=? WHERE id=?", (status, now(), by, approval_id))


# ---- lead assessments -------------------------------------------------------

def save_assessment(lead_id: str, run_id: str | None, score: int, tier: str, nba: str,
                    reasons: list[str], sources: list[str], engine: str) -> None:
    _exec("""INSERT INTO assessments (lead_id, run_id, score, tier, next_best_action, reasons, sources, engine, updated_at)
             VALUES (?,?,?,?,?,?,?,?,?)
             ON CONFLICT(lead_id) DO UPDATE SET run_id=excluded.run_id, score=excluded.score, tier=excluded.tier,
               next_best_action=excluded.next_best_action, reasons=excluded.reasons, sources=excluded.sources,
               engine=excluded.engine, updated_at=excluded.updated_at""",
          (lead_id, run_id, score, tier, nba, json.dumps(reasons), json.dumps(sources), engine, now()))


def assessments() -> dict[str, dict]:
    return {r["lead_id"]: _loads(r, "reasons", "sources") for r in _rows("SELECT * FROM assessments")}


def stats() -> dict:
    def count(sql: str, args: tuple = ()) -> int:
        return _rows(sql, args)[0]["n"]
    return {
        "runs": count("SELECT COUNT(*) n FROM runs"),
        "pending_approvals": count("SELECT COUNT(*) n FROM approvals WHERE status='pending'"),
        "approved": count("SELECT COUNT(*) n FROM approvals WHERE status='approved'"),
        "audit_events": count("SELECT COUNT(*) n FROM audit"),
        "assessed_leads": count("SELECT COUNT(*) n FROM assessments"),
        "tokens_in": _rows("SELECT COALESCE(SUM(input_tokens),0) n FROM audit")[0]["n"],
        "tokens_out": _rows("SELECT COALESCE(SUM(output_tokens),0) n FROM audit")[0]["n"],
    }
