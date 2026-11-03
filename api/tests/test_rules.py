from pathlib import Path

from app.connectors.demo import DemoOrg
from app.core.llm import strict_schema
from app.agents.code_review import ReviewResult
from app.rules import refresh
from app.rules.apex_checks import check
from app.rules.dedupe import find_duplicates
from app.rules.scoring import score_lead

CODE = Path(__file__).resolve().parents[2] / "demo_data" / "code"

EXPECTED = {
    "01_ContactTrigger.trigger": {"SOQL_IN_LOOP", "DML_IN_LOOP", "LOGIC_IN_TRIGGER"},
    "02_OpportunityService.cls": {"WITHOUT_SHARING", "SOQL_INJECTION", "HARDCODED_ID", "NO_FLS"},
    "03_StripeCallout.cls": {"SOQL_IN_LOOP", "DML_IN_LOOP", "CALLOUT_IN_LOOP", "HARDCODED_SECRET",
                             "HARDCODED_ENDPOINT", "FUTURE_WITHOUT_CALLOUT"},
    "04_LeadRouter.cls": {"SOQL_IN_LOOP", "DML_IN_LOOP", "IGNORED_PARTIAL_DML"},
    "05_LeadRouterTest.cls": {"SEE_ALL_DATA", "TRIVIAL_ASSERT", "NO_TEST_DATA"},
    "06_Lead_Assignment.flow-meta.xml": {"FLOW_GET_IN_LOOP", "FLOW_DML_IN_LOOP", "HARDCODED_ID"},
}


def test_static_checks_catch_seeded_issues():
    for name, expected in EXPECTED.items():
        rules = {f.rule for f in check((CODE / name).read_text(), name)}
        assert expected <= rules, f"{name}: missing {expected - rules}"


def test_clean_apex_has_no_critical_findings():
    clean = """public with sharing class AccountService {
    public static void touch(Set<Id> ids) {
        List<Account> accs = [SELECT Id, Name FROM Account WHERE Id IN :ids WITH USER_MODE];
        for (Account a : accs) { a.Description = 'ok'; }
        update accs;
    }
}"""
    assert not [f for f in check(clean, "AccountService.cls") if f.severity in ("critical", "high")]


def test_soql_for_loop_header_is_not_flagged():
    code = "public with sharing class X { void m() { for (Account a : [SELECT Id FROM Account WITH USER_MODE]) { a.Name = 'x'; } } }"
    assert "SOQL_IN_LOOP" not in {f.rule for f in check(code)}


def test_dedupe_finds_seeded_duplicates():
    leads = DemoOrg().leads()
    clusters = find_duplicates(leads)
    seeded = {leads[i]["Id"] for i in [3, 17, 42, 58, 91, 120, 150, 199]}
    found = {rid for c in clusters for rid in c["record_ids"]}
    assert seeded <= found


def test_scoring_is_bounded_and_explained():
    for lead in DemoOrg().leads():
        s = score_lead(lead)
        assert 0 <= s["score"] <= 100 and s["tier"] in "ABC" and s["next_best_action"]


def test_refresh_plan_covers_integrations_and_pii():
    org = DemoOrg()
    titles = " ".join(c["title"] for c in refresh.post_refresh_checklist(org.inventory()))
    assert "Stripe_API" in titles and "Nightly_Invoice_Sync" in titles and "PII" in titles
    mapping = {(m["source_object"], m["source_field"]): m for m in refresh.field_mapping(org.source_schema(), org.target_schema())}
    assert mapping[("Donation__c", "Amount__c")]["target_field"] == "OriginalAmount"
    assert mapping[("Donation__c", "Card_Last4__c")]["target_field"] is None
    statuses = {r["object"]: r["status"] for r in refresh.reconcile(org.reconciliation())}
    assert statuses["Account"] == "match" and statuses["Attachments/Files"] == "investigate"


def test_strict_schema_closes_every_object():
    def walk(n):
        if isinstance(n, dict):
            if n.get("type") == "object" and "properties" in n:
                assert n["additionalProperties"] is False and set(n["required"]) == set(n["properties"])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(strict_schema(ReviewResult))
