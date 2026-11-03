from app.connectors.demo import DemoOrg
from app.router import engine, trust
from app.router.providers import Completion


def test_mask_roundtrip_hides_every_sensitive_value():
    case = DemoOrg().cases()[0]
    text = engine._record_text(case)
    sc = trust.scan(text, engine._names(case))
    masked, mapping = trust.mask(text, sc)
    for value in mapping.values():
        assert value not in masked
    assert trust.unmask(masked, mapping) == text


def test_no_false_positive_on_dates_and_amounts():
    assert not trust.scan("CloseDate: 2026-12-01\nAmount: 180000\nInvoice INV-20931").findings


def test_policy_routes_by_sensitivity():
    cases = {c["Type"]: c for c in DemoOrg().cases()}
    wf = engine.WORKFLOWS["case-summary"]
    phi = engine._record_text(cases["Patient Intake"])
    assert engine.decide(wf, phi, trust.scan(phi))["chain"][0] == "private"
    pii = engine._record_text(cases["Billing"])
    d = engine.decide(wf, pii, trust.scan(pii, [cases["Billing"]["ContactName"]]))
    assert d["policy"] == "P3" and d["mask_external"]
    opp = engine._record_text(DemoOrg().opportunities()[0])
    assert engine.decide(engine.WORKFLOWS["deal-risk"], opp, trust.scan(opp))["policy"] == "P4"
    assert engine.decide(engine.WORKFLOWS["pipeline-count"], "", trust.Scan())["chain"] == ["native"]


def test_external_provider_never_sees_pii_and_falls_back(monkeypatch):
    """OpenAI unavailable -> skipped; Claude receives masked text only; answer is unmasked."""
    from app.router import providers
    seen = {}

    class Fake(providers.ClaudeProvider):
        def available(self):
            return True, "ok"

        def complete(self, system, prompt, max_tokens):
            seen["prompt"] = prompt
            return Completion("Reply to [EMAIL_1] today.", "claude-opus-5-5", 10, 5, 12, 0.0001)

    reg = providers.registry()
    reg["claude"] = Fake("claude", "Claude Opus", "claude-opus-5-5", "medium")
    monkeypatch.setattr(engine, "registry", lambda: reg)
    case = next(c for c in DemoOrg().cases() if c["Type"] == "Billing")
    out = engine.run_one(None, engine.WORKFLOWS["case-summary"], case)
    assert case["ContactEmail"] not in seen["prompt"] and case["ContactName"] not in seen["prompt"]
    assert case["ContactEmail"] in out["answer"] and out["masked"] and out["provider"] == "claude"
