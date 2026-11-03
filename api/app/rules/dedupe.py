"""Duplicate detection (entity resolution) for Leads/Contacts.

Match rules, strongest first: same normalised email; same phone; same
last name + similar company + first-name prefix. Survivor = oldest record.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz

COMPANY_NOISE = re.compile(r"\b(inc|llc|ltd|co|corp|corporation|gmbh|bv)\b\.?", re.I)


def _norm_email(e: str | None) -> str | None:
    return e.strip().lower() if e else None


def _norm_phone(p: str | None) -> str | None:
    digits = re.sub(r"\D", "", p or "")
    return digits[-10:] if len(digits) >= 7 else None


def _norm_company(c: str | None) -> str:
    return re.sub(r"\s+", " ", COMPANY_NOISE.sub("", (c or "").lower())).strip(" .")


def find_duplicates(records: list[dict]) -> list[dict]:
    parent = {r["Id"]: r["Id"] for r in records}
    reasons: list[tuple[str, str, str, int]] = []

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str, why: str, conf: int) -> None:
        reasons.append((a, b, why, conf))
        parent[find(a)] = find(b)

    by_email: dict[str, str] = {}
    by_phone: dict[str, str] = {}
    by_last: dict[str, list[dict]] = {}
    for r in records:
        e, p = _norm_email(r.get("Email")), _norm_phone(r.get("Phone"))
        if e:
            if e in by_email:
                union(r["Id"], by_email[e], "Same email (case-insensitive)", 98)
            else:
                by_email[e] = r["Id"]
        if p:
            if p in by_phone:
                union(r["Id"], by_phone[p], "Same phone number", 90)
            else:
                by_phone[p] = r["Id"]
        by_last.setdefault((r.get("LastName") or "").strip().lower(), []).append(r)

    for group in by_last.values():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if find(a["Id"]) == find(b["Id"]):
                    continue
                fa, fb = (a.get("FirstName") or "").lower(), (b.get("FirstName") or "").lower()
                if not fa or not fb or not (fa.startswith(fb) or fb.startswith(fa)):
                    continue
                score = fuzz.token_sort_ratio(_norm_company(a.get("Company")), _norm_company(b.get("Company")))
                if score >= 88:
                    union(a["Id"], b["Id"], f"Same last name, first-name prefix, company match {score:.0f}%", int(min(95, score - 5)))

    clusters: dict[str, list[dict]] = {}
    for r in records:
        clusters.setdefault(find(r["Id"]), []).append(r)
    out = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        ids = {m["Id"] for m in members}
        why = [{"a": a, "b": b, "reason": w, "confidence": c} for a, b, w, c in reasons if a in ids]
        survivor = min(members, key=lambda m: m.get("CreatedDate") or "")
        out.append({
            "survivor_id": survivor["Id"],
            "record_ids": sorted(ids),
            "records": members,
            "confidence": max(w["confidence"] for w in why) if why else 80,
            "reasons": why,
        })
    return sorted(out, key=lambda c: -c["confidence"])
