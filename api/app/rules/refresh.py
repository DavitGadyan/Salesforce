"""Sandbox refresh, seeding, org-to-org mapping and reconciliation rules."""

from __future__ import annotations

import re

from rapidfuzz import fuzz

OBJECT_SYNONYMS = {
    "Donation__c": "GiftTransaction",
    "Membership__c": "MembershipRecord",
}
FIELD_SYNONYMS = {
    ("Donation__c", "Amount__c"): "OriginalAmount",
    ("Donation__c", "Donation_Date__c"): "TransactionDate",
    ("Donation__c", "Campaign__c"): "CampaignId",
    ("Donation__c", "Donor__c"): "DonorId",
    ("Membership__c", "Member__c"): "MemberId",
    ("Membership__c", "Level__c"): "MembershipLevel",
    ("Membership__c", "Membership_Status__c"): "Status",
}


def post_refresh_checklist(inv: dict) -> list[dict]:
    """Deterministic checklist of what must change after refreshing Production into a sandbox."""
    integ = inv.get("integrations", {})
    items: list[dict] = []

    def add(category: str, title: str, detail: str, risk: str, automated: bool) -> None:
        items.append({"id": f"chk-{len(items) + 1}", "category": category, "title": title, "detail": detail,
                      "risk": risk, "automatable": automated})

    add("Email", "Keep email deliverability at 'System email only'",
        f"Production setting was '{integ.get('email_deliverability', 'unknown')}'. Sandboxes default to system-only; verify no job re-enables it.",
        "critical", True)
    add("Email", "Scramble user & contact emails",
        "Append '.invalid' to Contact/Lead emails so automation can't reach real customers.", "critical", True)
    for nc in integ.get("named_credentials", []):
        add("Integrations", f"Repoint Named Credential {nc['name']}",
            f"Currently {nc.get('endpoint')} ({nc.get('env')}). Switch to the vendor's sandbox/test endpoint and test keys.",
            "critical", True)
    for ob in integ.get("outbound_messages", []):
        add("Integrations", f"Disable outbound message {ob['name']}", f"Targets {ob['endpoint']}.", "high", True)
    for url in integ.get("remote_site_settings", []):
        add("Integrations", f"Review remote site {url}", "Deactivate or point at a mock server.", "medium", True)
    for job in integ.get("scheduled_jobs", []):
        add("Scheduled jobs", f"Abort or re-schedule {job['name']}",
            f"{job.get('class') or 'Apex'} on '{job.get('cron')}' copied from Production.", "high", True)
    for app in integ.get("connected_apps", []):
        add("Integrations", f"Re-authorise connected app '{app}' against its sandbox", "OAuth tokens don't survive a refresh.", "medium", False)
    for s in integ.get("custom_settings_with_urls", []):
        add("Config", f"Update {s}", "Custom setting stores a Production URL.", "high", True)
    pii = [(obj, f["name"]) for obj, fields in inv.get("fields", {}).items() for f in fields if f.get("pii")]
    if pii:
        add("Data privacy", f"Mask {len(pii)} PII fields",
            ", ".join(f"{o}.{f}" for o, f in pii[:8]) + (" …" if len(pii) > 8 else ""), "critical", True)
    users = integ.get("users", {})
    add("Users", "Freeze non-team users; reset integration users",
        f"{users.get('active', '?')} active users copied ({users.get('integration_users', '?')} integration users).", "medium", True)
    add("Data", "Seed test & master data (Developer sandboxes copy no data)",
        "Load Products, Price Books, Territory config and a referentially-intact sample of Accounts/Contacts/Opportunities.",
        "high", True)
    return items


def pii_fields(inv: dict) -> list[dict]:
    rules = {"email": "append .invalid", "phone": "replace with +1-555-0100", "date": "shift ±180 days",
             "textarea": "replace with lorem ipsum", "string": "hash (SHA-256, keep last 2)"}
    out = []
    for obj, fields in inv.get("fields", {}).items():
        for f in fields:
            if f.get("pii"):
                out.append({"object": obj, "field": f["name"], "type": f["type"],
                            "strategy": rules.get(f["type"], "null out")})
    return out


def seed_plan(inv: dict, sample_pct: float = 2.0) -> list[dict]:
    """Referentially-ordered seeding plan for a Developer sandbox."""
    master = {"Product2", "Pricebook2", "Territory_Config__c", "Integration_Setting__mdt"}
    order = ["Pricebook2", "Product2", "Territory_Config__c", "Account", "Contact", "Lead", "Opportunity",
             "Membership__c", "Donation__c", "Case"]
    objects = {o["name"]: o for o in inv.get("objects", [])}
    plan = []
    for step, name in enumerate([n for n in order if n in objects], start=1):
        o = objects[name]
        is_master = name in master
        count = o["records"] if is_master else max(50, int(o["records"] * sample_pct / 100))
        plan.append({"step": step, "object": name, "kind": "master data (all)" if is_master else f"test data ({sample_pct:g}% sample)",
                     "records": min(count, o["records"]),
                     "depends_on": {"Contact": ["Account"], "Opportunity": ["Account", "Pricebook2"], "Case": ["Account", "Contact"],
                                    "Donation__c": ["Contact"], "Membership__c": ["Contact"], "Product2": ["Pricebook2"]}.get(name, [])})
    return plan


def _key(field: str) -> str:
    return re.sub(r"(__c|__r|id)$", "", field.lower().replace("_", ""))


def field_mapping(source: dict[str, list[str]], target: dict) -> list[dict]:
    target_objects = target.get("objects", {})
    rows = []
    for s_obj, s_fields in source.items():
        t_obj = s_obj if s_obj in target_objects else OBJECT_SYNONYMS.get(s_obj)
        t_fields = target_objects.get(t_obj, []) if t_obj else []
        for f in s_fields:
            syn = FIELD_SYNONYMS.get((s_obj, f))
            if syn and syn in t_fields:
                rows.append(_row(s_obj, f, t_obj, syn, 95, "known Nonprofit Cloud mapping"))
                continue
            best, best_score = None, 0.0
            for tf in t_fields:
                sc = 100.0 if _key(tf) == _key(f) else fuzz.ratio(_key(f), _key(tf))
                if sc > best_score:
                    best, best_score = tf, sc
            if best and best_score >= 75:
                rows.append(_row(s_obj, f, t_obj, best, int(best_score), "name match"))
            else:
                note = "PCI data — do not migrate" if "card" in f.lower() else "no target field — create or archive"
                rows.append(_row(s_obj, f, t_obj, None, 0, note))
    return rows


def _row(so, sf, to, tf, conf, note):
    return {"source_object": so, "source_field": sf, "target_object": to, "target_field": tf,
            "confidence": conf, "note": note}


def reconcile(counts: dict) -> list[dict]:
    rows = []
    for name, c in counts.items():
        src, tgt = c.get("source"), c.get("target")
        if tgt is None:
            rows.append({"object": name, "source": src, "target": None, "diff": None, "pct": None, "status": "pending"})
            continue
        diff = tgt - src
        pct = round(100 * tgt / src, 2) if src else 100.0
        status = "match" if diff == 0 else "minor gap" if pct >= 99.5 else "investigate"
        rows.append({"object": name, "source": src, "target": tgt, "diff": diff, "pct": pct, "status": status})
    return rows
