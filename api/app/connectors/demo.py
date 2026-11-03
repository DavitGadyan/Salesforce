"""Seeded demo org backed by ../demo_data JSON fixtures. Writes stay in memory."""

from __future__ import annotations

import json
from functools import lru_cache

from ..core.config import DEMO_DIR


@lru_cache(maxsize=None)
def _load(name: str):
    return json.loads((DEMO_DIR / name).read_text())


class DemoOrg:
    mode = "demo"

    def __init__(self) -> None:
        self._leads = {lead["Id"]: dict(lead) for lead in _load("leads.json")}

    def status(self) -> dict:
        meta = _load("metadata.json")
        return {"mode": "demo", "connected": True, "org_name": meta["org_name"], "edition": meta["edition"],
                "instance_url": None}

    def inventory(self) -> dict:
        return _load("metadata.json")

    def leads(self, limit: int = 500) -> list[dict]:
        return list(self._leads.values())[:limit]

    def accounts(self) -> list[dict]:
        return _load("accounts.json")

    def get_lead(self, lead_id: str) -> dict | None:
        return self._leads.get(lead_id)

    def source_schema(self) -> dict[str, list[str]]:
        return _load("source_schema.json")

    def target_schema(self) -> dict:
        return _load("target_schema.json")

    def cases(self) -> list[dict]:
        return _load("cases.json")

    def opportunities(self) -> list[dict]:
        return _load("opportunities.json")

    def reconciliation(self) -> dict:
        return _load("reconciliation.json")

    def update_record(self, sobject: str, record_id: str, fields: dict) -> dict:
        if sobject == "Lead" and record_id in self._leads:
            self._leads[record_id].update(fields)
            return {"ok": True, "mode": "demo", "note": "Record updated."}
        return {"ok": True, "mode": "demo", "note": f"{sobject} {record_id} updated."}
