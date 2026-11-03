"""Deterministic lead scoring: fit + intent + recency − data-quality gaps.

Used as the no-API-key engine and as a grounded baseline that the Claude agent
can adjust (with reasons) rather than invent from scratch.
"""

from __future__ import annotations

from datetime import date

SENIOR = ("ceo", "cfo", "coo", "vp", "head", "director", "chief", "founder")
INTENT = {
    "demo": 18, "quote": 18, "pricing": 12, "webinar": 8, "opened": 5, "downloaded": 6, "circle back": 4,
}
FIT_INDUSTRIES = {"SaaS", "Financial Services", "Healthcare", "Nonprofit"}


def _days_since(iso: str | None, today: date) -> int | None:
    if not iso:
        return None
    try:
        return (today - date.fromisoformat(iso[:10])).days
    except ValueError:
        return None


def score_lead(lead: dict, today: date | None = None) -> dict:
    today = today or date(2026, 11, 3)
    pts, reasons, sources = 0, [], []

    title = (lead.get("Title") or "").lower()
    if any(s in title for s in SENIOR):
        pts += 20; reasons.append(f"Senior buyer ({lead['Title']})"); sources.append("Title")
    elif title:
        pts += 8; reasons.append(f"Practitioner role ({lead['Title']})"); sources.append("Title")

    emp = lead.get("NumberOfEmployees") or 0
    if emp >= 200:
        pts += 15; reasons.append(f"{emp:,} employees — mid/large account"); sources.append("NumberOfEmployees")
    elif emp >= 40:
        pts += 8; reasons.append(f"{emp:,} employees"); sources.append("NumberOfEmployees")

    if lead.get("Industry") in FIT_INDUSTRIES:
        pts += 10; reasons.append(f"Target industry: {lead['Industry']}"); sources.append("Industry")

    activity = [a for a in (lead.get("Activity") or []) if a != "No activity"]
    intent = 0
    for a in activity:
        for kw, w in INTENT.items():
            if kw in a.lower():
                intent += w
                reasons.append(f"Intent signal: {a}")
                sources.append("Activity")
                break
    pts += min(intent, 30)

    days = _days_since(lead.get("LastActivityDate"), today)
    if days is not None:
        sources.append("LastActivityDate")
        if days <= 14:
            pts += 15; reasons.append(f"Active {days} days ago")
        elif days <= 60:
            pts += 8; reasons.append(f"Last active {days} days ago")
        elif days > 365:
            pts -= 5; reasons.append(f"Dormant for {days} days — reactivation candidate")

    if not lead.get("Email"):
        pts -= 15; reasons.append("No email on record"); sources.append("Email")
    if lead.get("Status") == "Closed - Not Converted":
        pts -= 5; reasons.append("Previously closed as not converted"); sources.append("Status")

    score = max(0, min(100, pts))
    tier = "A" if score >= 60 else "B" if score >= 38 else "C"
    return {"score": score, "tier": tier, "next_best_action": next_best_action(lead, tier, days),
            "reasons": reasons, "sources": sorted(set(sources))}


def next_best_action(lead: dict, tier: str, days: int | None) -> str:
    if not lead.get("Email"):
        return "Enrich: find a verified business email before any outreach"
    if tier == "A" and days is not None and days <= 30:
        return "Call today and offer a meeting slot (warm, high-fit)"
    if tier == "A":
        return "Personalised reactivation email from the owner, propose a 20-min call"
    if tier == "B" and days is not None and days > 180:
        return "Add to reactivation sequence (3 touches, value-first content)"
    if tier == "B":
        return "Send relevant case study and follow up in 3 days"
    return "Nurture: monthly newsletter; re-score on next activity"
