"""Deterministic Apex / Flow checks that run before (and independently of) Claude.

They catch the issues the high-value job posts list by name: SOQL/DML in loops,
missing bulkification, sharing/FLS gaps, SOQL injection, hardcoded IDs and
secrets, and tests that prove nothing.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

LOOP_RE = re.compile(r"\b(for|while)\s*\(")
SOQL_RE = re.compile(r"\[\s*SELECT\b|Database\.query\s*\(", re.I)
DML_RE = re.compile(r"^\s*(insert|update|delete|upsert|undelete)\s+\w|Database\.(insert|update|delete|upsert)\s*\(", re.I)
CALLOUT_RE = re.compile(r"\.send\s*\(|new\s+Http\s*\(", re.I)
SF_ID_RE = re.compile(r"'(0[0-9A-Za-z]{2}[0-9A-Za-z]{12}(?:[0-9A-Za-z]{3})?)'")
SECRET_RE = re.compile(r"(sk_live_|sk_test_|Bearer\s+[A-Za-z0-9_]{8,}|password\s*=\s*')", re.I)
ENDPOINT_RE = re.compile(r"setEndpoint\s*\(\s*'https?://", re.I)
CLASS_RE = re.compile(r"\bclass\s+\w+", re.I)
SHARING_RE = re.compile(r"\b(with|without|inherited)\s+sharing\b", re.I)


@dataclass
class Finding:
    rule: str
    severity: str  # critical | high | medium | low
    line: int
    message: str
    fix: str
    source: str = "static"

    def to_dict(self) -> dict:
        return asdict(self)


def _strip_comment(line: str) -> str:
    """Drop a trailing // comment, ignoring // inside string literals (e.g. URLs)."""
    in_str = False
    for i, ch in enumerate(line):
        if ch == "'" and (i == 0 or line[i - 1] != "\\"):
            in_str = not in_str
        elif not in_str and line.startswith("//", i):
            return line[:i]
    return line


def _loop_lines(lines: list[str]) -> set[int]:
    """1-based line numbers that sit inside a for/while body (header line excluded)."""
    inside: set[int] = set()
    depth = 0
    stack: list[int] = []
    pending: int | None = None
    for i, raw in enumerate(lines, start=1):
        line = _strip_comment(raw)
        if stack and i not in inside:
            inside.add(i)
        is_header = bool(LOOP_RE.search(line))
        if is_header:
            pending = depth
            inside.discard(i)
        for ch in line:
            if ch == "{":
                depth += 1
                if pending is not None:
                    stack.append(pending)
                    pending = None
            elif ch == "}":
                depth -= 1
                while stack and depth <= stack[-1]:
                    stack.pop()
    return inside


def check_apex(code: str, filename: str = "") -> list[Finding]:
    lines = code.splitlines()
    in_loop = _loop_lines(lines)
    is_test = bool(re.search(r"@isTest", code, re.I))
    is_trigger = bool(re.match(r"\s*trigger\s+", code, re.I)) or filename.endswith(".trigger")
    has_aura = bool(re.search(r"@AuraEnabled|@RemoteAction|@RestResource|global\s+class", code, re.I))
    findings: list[Finding] = []

    for i, line in enumerate(lines, start=1):
        code_part = _strip_comment(line)
        if i in in_loop and SOQL_RE.search(code_part):
            findings.append(Finding("SOQL_IN_LOOP", "critical", i, "SOQL query inside a loop — hits the 100-query governor limit with >100 records.",
                                    "Collect Ids first, run one query outside the loop, and use a Map<Id, SObject> for lookups."))
        if i in in_loop and DML_RE.search(code_part):
            findings.append(Finding("DML_IN_LOOP", "critical", i, "DML statement inside a loop — hits the 150-DML limit and is slow.",
                                    "Add records to a List inside the loop and perform a single DML after it."))
        if i in in_loop and CALLOUT_RE.search(code_part):
            findings.append(Finding("CALLOUT_IN_LOOP", "high", i, "HTTP callout inside a loop — max 100 callouts per transaction.",
                                    "Batch the payload into one request, or move to Queueable/Batch Apex with Database.AllowsCallouts."))
        if re.search(r"\bwithout\s+sharing\b", code_part, re.I):
            findings.append(Finding("WITHOUT_SHARING", "high", i, "Class runs `without sharing`, bypassing record-level security.",
                                    "Use `with sharing` (or `inherited sharing`) and isolate any elevated logic in a small, documented class."))
        if SOQL_RE.search(code_part) and not re.search(r"WITH\s+(USER_MODE|SECURITY_ENFORCED)|AccessLevel\.USER_MODE", code_part, re.I) and not is_test:
            sev = "high" if has_aura else "medium"
            findings.append(Finding("NO_FLS", sev, i, "Query does not enforce field/object-level security.",
                                    "Add `WITH USER_MODE` to the SOQL (or Database.query(q, AccessLevel.USER_MODE)), or use Security.stripInaccessible."))
        if (re.search(r"'\s*SELECT\b", code_part, re.I) and re.search(r"'\s*\+\s*\w+", code_part)
                and re.search(r"Database\.query\s*\(", code, re.I) and "escapeSingleQuotes" not in code):
            findings.append(Finding("SOQL_INJECTION", "critical", i, "Dynamic SOQL built by concatenating input into the query string.",
                                    "Use bind variables (`:term`) with Database.queryWithBinds, or String.escapeSingleQuotes."))
        for m in SF_ID_RE.finditer(code_part):
            findings.append(Finding("HARDCODED_ID", "high", i, f"Hardcoded record Id {m.group(1)} — differs between sandboxes and production.",
                                    "Look the record up by a stable key (DeveloperName, Custom Metadata, Custom Setting)."))
        if SECRET_RE.search(code_part):
            findings.append(Finding("HARDCODED_SECRET", "critical", i, "Credential/API key embedded in code.",
                                    "Move it to a Named Credential + External Credential and call `callout:Name/...`. Rotate the leaked key."))
        if ENDPOINT_RE.search(code_part):
            findings.append(Finding("HARDCODED_ENDPOINT", "medium", i, "Endpoint URL hardcoded instead of a Named Credential.",
                                    "Use `req.setEndpoint('callout:Stripe_API/v1/charges')`; it also survives sandbox refreshes."))
        if re.search(r"SeeAllData\s*=\s*true", code_part, re.I):
            findings.append(Finding("SEE_ALL_DATA", "high", i, "Test uses SeeAllData=true — depends on org data and breaks in fresh sandboxes.",
                                    "Create test data with a @TestSetup method / test data factory."))
        if re.search(r"System\.assert\s*\(\s*true\s*\)", code_part, re.I):
            findings.append(Finding("TRIVIAL_ASSERT", "high", i, "Assertion always passes — the test verifies nothing.",
                                    "Assert on real outcomes, e.g. Assert.areEqual(expectedOwner, lead.OwnerId)."))
        if re.search(r"Database\.(update|insert|upsert|delete)\s*\([^)]*,\s*false\s*\)", code_part, re.I) and "SaveResult" not in code:
            findings.append(Finding("IGNORED_PARTIAL_DML", "medium", i, "allOrNone=false but SaveResults are never inspected — failures are silent.",
                                    "Iterate the Database.SaveResult[] and log/handle errors."))
        if re.search(r"System\.debug\s*\(.*(serialize|json)", code_part, re.I):
            findings.append(Finding("DEBUG_RECORD_DATA", "low", i, "Debug-logs serialized records (may leak PII into logs).",
                                    "Remove or log only Ids/counts."))
        if re.search(r"@future\b(?!\s*\(\s*callout\s*=\s*true)", code_part, re.I) and CALLOUT_RE.search(code):
            findings.append(Finding("FUTURE_WITHOUT_CALLOUT", "high", i, "@future method makes callouts but lacks (callout=true) — fails at runtime.",
                                    "Use @future(callout=true), or better a Queueable implementing Database.AllowsCallouts."))

    first_class = next((i for i, l in enumerate(lines, start=1) if CLASS_RE.search(l)), None)
    if first_class and not is_test and not SHARING_RE.search(lines[first_class - 1]):
        findings.append(Finding("NO_SHARING_DECLARATION", "medium", first_class, "Class has no sharing declaration; it inherits the caller's mode unpredictably.",
                                "Declare `with sharing` or `inherited sharing` explicitly."))
    if is_trigger and re.search(r"\bfor\s*\(", code):
        findings.append(Finding("LOGIC_IN_TRIGGER", "medium", 1, "Business logic lives in the trigger body.",
                                "Use one trigger per object delegating to a handler class (bulk-safe, testable, orderable)."))
    if is_test and not re.search(r"\binsert\b|TestDataFactory|@TestSetup", code, re.I):
        findings.append(Finding("NO_TEST_DATA", "medium", 1, "Test creates no data of its own.",
                                "Insert the records the test needs (200+ for bulk tests) inside the test."))
    if is_test and not re.search(r"Assert\.\w+|System\.assert(Equals|NotEquals)?\s*\((?!\s*true\s*\))", code):
        findings.append(Finding("NO_REAL_ASSERTS", "high", 1, "No meaningful assertions in the test class.",
                                "Assert expected field values, counts and error paths."))
    return _dedupe(findings)


def check_flow(xml: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = xml.splitlines()

    def line_of(pattern: str) -> int:
        for i, l in enumerate(lines, start=1):
            if re.search(pattern, l):
                return i
        return 1

    elements: dict[str, tuple[str, str]] = {}  # name -> (element type, body)
    for kind, body in re.findall(r"<(loops|recordLookups|recordUpdates|recordCreates|recordDeletes|assignments|decisions|actionCalls)>(.*?)</\1>", xml, re.S):
        name = re.search(r"<name>(\w+)</name>", body)
        if name:
            elements[name.group(1)] = (kind, body)

    def target(body: str, tag: str = "connector") -> str | None:
        m = re.search(rf"<{tag}>\s*<targetReference>(\w+)</targetReference>", body)
        return m.group(1) if m else None

    loops = [(n, target(b, "nextValueConnector")) for n, (k, b) in elements.items() if k == "loops"]
    lookups = {n for n, (k, _) in elements.items() if k == "recordLookups"}
    updates = {n for n, (k, _) in elements.items() if k in ("recordUpdates", "recordDeletes")}
    creates = {n for n, (k, _) in elements.items() if k == "recordCreates"}
    # follow connectors from each loop's first element back to the loop
    connectors = {n: target(b) for n, (k, b) in elements.items() if k != "loops"}
    for loop_name, first in loops:
        node, seen = first, set()
        while node and node != loop_name and node not in seen:
            seen.add(node)
            if node in lookups:
                findings.append(Finding("FLOW_GET_IN_LOOP", "critical", line_of(f"<name>{node}</name>"),
                                        f"Get Records '{node}' runs inside loop '{loop_name}' (one SOQL per iteration).",
                                        "Move the Get Records before the loop and use a collection filter / assignment inside it."))
            if node in updates or node in creates:
                findings.append(Finding("FLOW_DML_IN_LOOP", "critical", line_of(f"<name>{node}</name>"),
                                        f"'{node}' writes records inside loop '{loop_name}'.",
                                        "Assign changed records to a collection variable in the loop; one Update/Create after it."))
            node = connectors.get(node)
    for m in SF_ID_RE.finditer(xml.replace("<stringValue>", "'").replace("</stringValue>", "'")):
        findings.append(Finding("HARDCODED_ID", "high", line_of(m.group(1)), f"Hardcoded Id {m.group(1)} in Flow.",
                                "Use a Custom Metadata record, Custom Label or a Get Records by DeveloperName."))
    if re.search(r"<triggerType>RecordAfterSave</triggerType>", xml) and re.search(r"<recordUpdates>.*?<inputReference>\$Record", xml, re.S):
        findings.append(Finding("FLOW_AFTER_SAVE_SELF_UPDATE", "medium", line_of("RecordAfterSave"),
                                "After-save flow updates the triggering record.", "Use a before-save (Fast Field Update) flow instead."))
    if re.search(r"<triggerType>RecordAfterSave</triggerType>", xml) and not re.search(r"<filters>|<filterFormula>", xml.split("</start>")[0]):
        findings.append(Finding("FLOW_NO_ENTRY_CRITERIA", "medium", line_of("<start>"),
                                "Record-triggered flow has no entry criteria — runs on every save.",
                                "Add entry conditions (e.g. only when Status changed)."))
    if not re.search(r"<faultConnector>", xml) and (updates or creates):
        findings.append(Finding("FLOW_NO_FAULT_PATH", "low", line_of("<recordUpdates>|<recordCreates>"),
                                "DML elements have no fault path.", "Add fault connectors that log the error and notify an admin."))
    return _dedupe(findings)


def check(code: str, filename: str = "") -> list[Finding]:
    if filename.endswith(".xml") or code.lstrip().startswith("<?xml") or "<Flow" in code[:400]:
        return check_flow(code)
    return check_apex(code, filename)


def _dedupe(findings: list[Finding]) -> list[Finding]:
    seen, out = set(), []
    for f in findings:
        key = (f.rule, f.line)
        if key not in seen:
            seen.add(key)
            out.append(f)
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(out, key=lambda f: (order[f.severity], f.line))
