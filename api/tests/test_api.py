import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core import config, llm
from app.main import app

client = TestClient(app)


def wait(run_id):
    for _ in range(100):
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_rules_engine_end_to_end():
    client.post("/api/reset")
    run = wait(client.post("/api/runs/revenue", json={"limit": 4}).json()["run_id"])
    assert run["status"] == "done" and run["result"]["assessed"] == 4
    pending = client.get("/api/approvals?status=pending").json()
    assert pending and all(a["status"] == "pending" for a in pending)


def test_approval_gate_executes_once():
    client.post("/api/reset")
    wait(client.post("/api/runs/dedupe").json()["run_id"])
    approval = client.get("/api/approvals?status=pending").json()[0]
    assert client.post(f"/api/approvals/{approval['id']}/decide", json={"decision": "approve"}).status_code == 200
    assert client.post(f"/api/approvals/{approval['id']}/decide", json={"decision": "approve"}).status_code == 409
    kinds = [e["kind"] for e in client.get("/api/audit").json()]
    assert "approval_executed" in kinds


def _block(**kw):
    return SimpleNamespace(**kw)


def test_claude_tool_loop_with_fact_guardrail(monkeypatch):
    """Mock Claude: first draft cites a fake fact (rejected), second is clean (queued)."""
    client.post("/api/reset")
    lead = client.get("/api/leads").json()[0]
    lid = lead["Id"]
    script = [
        [_block(type="tool_use", id="t1", name="get_lead", input={"lead_id": lid})],
        [_block(type="tool_use", id="t2", name="record_assessment", input={
            "lead_id": lid, "score": 77, "tier": "A", "next_best_action": "Call", "reasons": ["r"], "sources": ["Title"]})],
        [_block(type="tool_use", id="t3", name="draft_outreach", input={
            "lead_id": lid, "subject": "s", "body": "b", "facts_used": [{"field": "Company", "value": "Totally Fake Corp"}]})],
        [_block(type="tool_use", id="t4", name="draft_outreach", input={
            "lead_id": lid, "subject": "s", "body": "b", "facts_used": [{"field": "Company", "value": lead["Company"]}]})],
        [_block(type="text", text="done")],
    ]
    calls = []

    def fake_call(**kwargs):
        calls.append(kwargs)
        content = script[len(calls) - 1]
        stop = "tool_use" if content[0].type == "tool_use" else "end_turn"
        return SimpleNamespace(content=content, stop_reason=stop, model=kwargs["model"],
                               usage=SimpleNamespace(input_tokens=100, output_tokens=20))

    monkeypatch.setattr(llm, "_call", fake_call)
    monkeypatch.setattr(config, "claude_configured", lambda: True)
    run = wait(client.post("/api/runs/revenue", json={"lead_ids": [lid]}).json()["run_id"])
    assert run["status"] == "done", run["error"]
    assert run["result"]["rejected_drafts"] == 1 and run["result"]["drafts"] == 1
    # rejected draft was returned to Claude as an error tool_result
    results = [b for m in calls[-1]["messages"] if m["role"] == "user" and isinstance(m["content"], list)
               for b in m["content"]]
    rejected = [r for r in results if r["is_error"]]
    assert len(rejected) == 1 and "Unverified" in rejected[0]["content"]
    assert calls[0]["model"] == "claude-opus-5-5" and calls[0]["fallbacks"] == "default"
    assert all(t["strict"] for t in calls[0]["tools"])
