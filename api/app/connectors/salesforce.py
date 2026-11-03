"""Live org over the Salesforce REST + Tooling APIs (httpx, no extra SDK).

Auth: SF_INSTANCE_URL + SF_ACCESS_TOKEN, or the OAuth username-password flow
(SF_CLIENT_ID / SF_CLIENT_SECRET / SF_USERNAME / SF_PASSWORD).
"""

from __future__ import annotations

import re

import httpx

from ..core import config

PII_HINTS = re.compile(r"(email|phone|mobile|birth|ssn|street|address|passport|card|insurance|diagnos|dob|tax)", re.I)
INVENTORY_OBJECTS = ["Account", "Contact", "Lead", "Opportunity", "Case", "Task", "EmailMessage", "Product2", "Pricebook2"]


class SalesforceOrg:
    mode = "live"

    def __init__(self) -> None:
        self.instance_url = config.SF_INSTANCE_URL.rstrip("/")
        self.token = config.SF_ACCESS_TOKEN
        if not self.token:
            self._login()
        self.http = httpx.Client(base_url=f"{self.instance_url}/services/data/{config.SF_API_VERSION}",
                                 headers={"Authorization": f"Bearer {self.token}"}, timeout=60)

    def _login(self) -> None:
        r = httpx.post(f"{config.SF_LOGIN_URL}/services/oauth2/token", data={
            "grant_type": "password", "client_id": config.SF_CLIENT_ID, "client_secret": config.SF_CLIENT_SECRET,
            "username": config.SF_USERNAME, "password": config.SF_PASSWORD}, timeout=30)
        r.raise_for_status()
        body = r.json()
        self.token, self.instance_url = body["access_token"], body["instance_url"].rstrip("/")

    def _get(self, path: str, **params) -> dict:
        r = self.http.get(path, params=params)
        r.raise_for_status()
        return r.json()

    def _query(self, soql: str, tooling: bool = False) -> list[dict]:
        path = "/tooling/query" if tooling else "/query"
        body = self._get(path, q=soql)
        records = body["records"]
        while not body.get("done", True):
            r = self.http.get(body["nextRecordsUrl"].split(config.SF_API_VERSION, 1)[1])
            r.raise_for_status()
            body = r.json()
            records += body["records"]
        for rec in records:
            rec.pop("attributes", None)
        return records

    def _safe(self, fn, default):
        try:
            return fn()
        except httpx.HTTPError:
            return default

    # ---- interface ----------------------------------------------------------

    def status(self) -> dict:
        org = self._safe(lambda: self._query("SELECT Name, OrganizationType, IsSandbox FROM Organization")[0], {})
        return {"mode": "live", "connected": bool(org), "org_name": org.get("Name", "Unknown org"),
                "edition": org.get("OrganizationType"), "is_sandbox": org.get("IsSandbox"),
                "instance_url": self.instance_url}

    def inventory(self) -> dict:
        sobjects = self._get("/sobjects")["sobjects"]
        custom = [s["name"] for s in sobjects if s["custom"] and s["queryable"] and s["name"].endswith("__c")][:40]
        names = INVENTORY_OBJECTS + custom
        counts = self._safe(lambda: {c["name"]: c["count"] for c in
                                     self._get("/limits/recordCount", sObjects=",".join(names))["sObjects"]}, {})
        labels = {s["name"]: s["label"] for s in sobjects}
        objects = [{"name": n, "label": labels.get(n, n), "custom": n.endswith("__c"), "records": counts.get(n, 0)}
                   for n in names if n in labels]
        fields: dict[str, list[dict]] = {}
        for name in ["Contact", "Lead"] + custom[:10]:
            desc = self._safe(lambda n=name: self._get(f"/sobjects/{n}/describe"), None)
            if not desc:
                continue
            flagged = [{"name": f["name"], "type": f["type"], "pii": bool(PII_HINTS.search(f["name"])) or f["type"] in ("email", "phone")}
                       for f in desc["fields"]]
            fields[name] = [f for f in flagged if f["pii"] or f["name"].endswith("__c")][:25]
        integrations = {
            "named_credentials": self._safe(lambda: [{"name": r["DeveloperName"], "endpoint": r.get("Endpoint"), "env": "?"}
                                                     for r in self._query("SELECT DeveloperName, Endpoint FROM NamedCredential")], []),
            "remote_site_settings": self._safe(lambda: [r["EndpointUrl"] for r in self._query("SELECT EndpointUrl FROM RemoteProxy", tooling=True)], []),
            "scheduled_jobs": self._safe(lambda: [{"name": r["CronJobDetail"]["Name"], "class": "", "cron": r["CronExpression"]}
                                                  for r in self._query("SELECT CronExpression, CronJobDetail.Name FROM CronTrigger WHERE State != 'DELETED'")], []),
            "outbound_messages": [],
            "email_deliverability": "unknown (not exposed by API)",
            "connected_apps": self._safe(lambda: [r["Name"] for r in self._query("SELECT Name FROM ConnectedApplication")], []),
            "users": self._safe(lambda: {"active": self._get("/query", q="SELECT COUNT() FROM User WHERE IsActive = true")["totalSize"]}, {}),
        }
        limits = self._safe(lambda: self._get("/limits"), {})
        data_mb = limits.get("DataStorageMB", {})
        file_mb = limits.get("FileStorageMB", {})
        return {"org_name": self.status()["org_name"], "edition": "live", "objects": objects, "fields": fields,
                "integrations": integrations,
                "data_storage_gb": round((data_mb.get("Max", 0) - data_mb.get("Remaining", 0)) / 1024, 2),
                "file_storage_gb": round((file_mb.get("Max", 0) - file_mb.get("Remaining", 0)) / 1024, 2)}

    def leads(self, limit: int = 500) -> list[dict]:
        rows = self._query(
            "SELECT Id, FirstName, LastName, Title, Company, Website, Email, Phone, Industry, NumberOfEmployees, "
            "AnnualRevenue, Country, LeadSource, Status, LastActivityDate, CreatedDate, Owner.Name "
            f"FROM Lead WHERE IsConverted = false ORDER BY LastModifiedDate DESC LIMIT {int(limit)}")
        for r in rows:
            r["OwnerName"] = (r.pop("Owner", None) or {}).get("Name")
            r["Activity"] = []
        return rows

    def accounts(self) -> list[dict]:
        return self._query("SELECT Id, Name, Website, Industry, NumberOfEmployees, AnnualRevenue, BillingCountry, ParentId FROM Account LIMIT 2000")

    def get_lead(self, lead_id: str) -> dict | None:
        if not re.fullmatch(r"[a-zA-Z0-9]{15,18}", lead_id):
            return None
        rows = self._query(
            "SELECT Id, FirstName, LastName, Title, Company, Website, Email, Phone, Industry, NumberOfEmployees, "
            f"AnnualRevenue, Country, LeadSource, Status, LastActivityDate, CreatedDate FROM Lead WHERE Id = '{lead_id}'")
        if not rows:
            return None
        lead = rows[0]
        lead["Activity"] = [t["Subject"] for t in self._safe(lambda: self._query(
            f"SELECT Subject FROM Task WHERE WhoId = '{lead_id}' ORDER BY ActivityDate DESC LIMIT 5"), [])]
        return lead

    def source_schema(self) -> dict[str, list[str]]:
        out = {}
        for name in ["Account", "Contact"]:
            out[name] = [f["name"] for f in self._get(f"/sobjects/{name}/describe")["fields"] if f["updateable"]][:40]
        return out

    def target_schema(self) -> dict:
        # The target of an org-to-org move is a second org; the demo target is used until one is configured.
        from .demo import DemoOrg
        return DemoOrg().target_schema()

    def cases(self) -> list[dict]:
        rows = self._query("SELECT Id, CaseNumber, Subject, Type, Priority, Status, Description, Account.Name, Contact.Name, "
                           "Contact.Email, CreatedDate FROM Case ORDER BY CreatedDate DESC LIMIT 50")
        for r in rows:
            r["AccountName"] = (r.pop("Account", None) or {}).get("Name")
            c = r.pop("Contact", None) or {}
            r["ContactName"], r["ContactEmail"] = c.get("Name"), c.get("Email")
        return rows

    def opportunities(self) -> list[dict]:
        rows = self._query("SELECT Id, Name, StageName, Amount, CloseDate, Probability, NextStep, Description, Account.Name "
                           "FROM Opportunity WHERE IsClosed = false ORDER BY Amount DESC NULLS LAST LIMIT 50")
        for r in rows:
            r["AccountName"] = (r.pop("Account", None) or {}).get("Name")
            r["Notes"] = r.pop("Description", None)
        return rows

    def reconciliation(self) -> dict:
        inv = self.inventory()
        return {o["name"]: {"source": o["records"], "target": None} for o in inv["objects"]}

    def update_record(self, sobject: str, record_id: str, fields: dict) -> dict:
        r = self.http.patch(f"/sobjects/{sobject}/{record_id}", json=fields)
        r.raise_for_status()
        return {"ok": True, "mode": "live"}
