"""Generate the deterministic demo org in ../demo_data (run once; output is committed).

The data is deliberately dirty: duplicate leads, missing fields, stale records,
PII in custom fields, integrations that must be neutralised after a refresh.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "demo_data"
rng = random.Random(42)
TODAY = date(2026, 11, 3)

INDUSTRIES = ["SaaS", "Healthcare", "Manufacturing", "Financial Services", "Nonprofit", "Retail", "Energy"]
COMPANY_ROOTS = [
    "Northwind", "Bluepeak", "Helix", "Ironclad", "Lumen", "Meridian", "Novacore", "Orbital",
    "Pinecrest", "Quantis", "Redwood", "Silverline", "Tidal", "Umbra", "Vantage", "Westbrook",
    "Atlas", "Brightwave", "Cobalt", "Driftwood", "Evergreen", "Foundry", "Granite", "Harbor",
    "Keystone", "Larkspur", "Monarch", "Nimbus", "Oakridge", "Prairie",
]
SUFFIX = ["Labs", "Health", "Systems", "Capital", "Foundation", "Group", "Energy", "Retail Co"]
FIRST = ["Ava", "Liam", "Mia", "Noah", "Zoe", "Ethan", "Ivy", "Lucas", "Nora", "Owen", "Ruby",
         "Theo", "Elena", "Marco", "Priya", "Kenji", "Sofia", "Omar", "Hana", "Daniel"]
LAST = ["Garcia", "Chen", "Patel", "Novak", "Okafor", "Silva", "Kowalski", "Haddad", "Larsen",
        "Moreau", "Tanaka", "Brennan", "Duarte", "Ivanova", "Singh", "Muller"]
TITLES = ["VP Sales", "Head of RevOps", "CFO", "Director of IT", "Salesforce Admin",
          "COO", "Marketing Manager", "CEO", "Operations Lead", "Procurement Manager"]
SOURCES = ["Web Form", "Webinar", "Referral", "Paid Search", "LinkedIn", "Trade Show", "Cold Outbound", None]
STATUSES = ["Open - Not Contacted", "Working - Contacted", "Nurturing", "Closed - Not Converted"]
ACTIVITY = [
    "Downloaded pricing guide", "Attended webinar: Salesforce sandbox best practices",
    "Asked for a demo, no follow-up logged", "Opened 3 of last 4 emails",
    "Replied: 'circle back next quarter'", "Visited pricing page twice this week",
    "Requested data migration quote", "No activity",
]


B62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_id_rng = random.Random(7)


def sfid(prefix: str, n: int) -> str:
    """Realistic 18-char Salesforce Id: key prefix + pod + 9-char record part + 3-char checksum suffix."""
    body = prefix + "5g00000" + "".join(_id_rng.choice(B62) for _ in range(5))
    suffix = ""
    for i in range(3):  # standard 15→18 case-sensitivity checksum
        chunk = body[i * 5:(i + 1) * 5]
        bits = sum(1 << j for j, ch in enumerate(chunk) if ch.isupper())
        suffix += "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"[bits]
    return body + suffix


def gen_accounts() -> list[dict]:
    accounts = []
    for i, root in enumerate(COMPANY_ROOTS):
        name = f"{root} {rng.choice(SUFFIX)}"
        domain = f"{root.lower()}.com"
        accounts.append({
            "Id": sfid("001", i + 1),
            "Name": name,
            "Website": domain,
            "Industry": rng.choice(INDUSTRIES),
            "NumberOfEmployees": rng.choice([12, 45, 120, 380, 950, 2400, 8000]),
            "AnnualRevenue": rng.choice([1.2e6, 4.5e6, 12e6, 48e6, 150e6, 600e6]),
            "BillingCountry": rng.choice(["United States", "Canada", "United Kingdom", "Netherlands", "Germany"]),
            "ParentId": None,
        })
    # small hierarchy
    accounts[3]["ParentId"] = accounts[0]["Id"]
    accounts[7]["ParentId"] = accounts[0]["Id"]
    return accounts


def gen_leads(accounts: list[dict]) -> list[dict]:
    leads = []
    n = 0
    for _ in range(240):
        n += 1
        acc = rng.choice(accounts)
        first, last = rng.choice(FIRST), rng.choice(LAST)
        last_activity = TODAY - timedelta(days=rng.choice([2, 6, 14, 30, 75, 140, 260, 400, 700]))
        email = f"{first.lower()}.{last.lower()}@{acc['Website']}"
        if rng.random() < 0.06:
            email = None
        leads.append({
            "Id": sfid("00Q", n),
            "FirstName": first,
            "LastName": last,
            "Title": rng.choice(TITLES),
            "Company": acc["Name"],
            "Website": acc["Website"],
            "Email": email,
            "Phone": f"+1-555-{rng.randint(100, 999)}-{rng.randint(1000, 9999)}" if rng.random() > 0.2 else None,
            "Industry": acc["Industry"] if rng.random() > 0.15 else None,
            "NumberOfEmployees": acc["NumberOfEmployees"],
            "AnnualRevenue": acc["AnnualRevenue"],
            "Country": acc["BillingCountry"],
            "LeadSource": rng.choice(SOURCES),
            "Status": rng.choice(STATUSES),
            "LastActivityDate": last_activity.isoformat(),
            "CreatedDate": (last_activity - timedelta(days=rng.randint(10, 400))).isoformat(),
            "Activity": rng.sample(ACTIVITY, k=rng.randint(1, 3)),
            "OwnerName": rng.choice(["Dana Reyes", "Sam Whitfield", "Unassigned"]),
        })
    # Seed duplicates: exact email, case/whitespace variants, nickname + same company
    for src_idx in [3, 17, 42, 58, 91, 120, 150, 199]:
        src = dict(leads[src_idx])
        n += 1
        dup = dict(src)
        dup["Id"] = sfid("00Q", n)
        variant = src_idx % 3
        if variant == 0 and src["Email"]:
            dup["Email"] = src["Email"].upper()
        elif variant == 1:
            dup["FirstName"] = src["FirstName"][:3]
            dup["Company"] = src["Company"] + " Inc."
        else:
            dup["LastName"] = src["LastName"] + " "
            dup["Phone"] = None
        dup["LeadSource"] = "Web Form"
        dup["CreatedDate"] = TODAY.isoformat()
        leads.append(dup)
    return leads


def gen_metadata(accounts, leads) -> dict:
    objects = [
        {"name": "Account", "label": "Account", "custom": False, "records": 18_400},
        {"name": "Contact", "label": "Contact", "custom": False, "records": 96_200},
        {"name": "Lead", "label": "Lead", "custom": False, "records": 30_150},
        {"name": "Opportunity", "label": "Opportunity", "custom": False, "records": 22_700},
        {"name": "Case", "label": "Case", "custom": False, "records": 140_300},
        {"name": "Task", "label": "Task", "custom": False, "records": 1_250_000},
        {"name": "EmailMessage", "label": "Email Message", "custom": False, "records": 610_000},
        {"name": "Product2", "label": "Product", "custom": False, "records": 340},
        {"name": "Pricebook2", "label": "Price Book", "custom": False, "records": 6},
        {"name": "Membership__c", "label": "Membership", "custom": True, "records": 41_000},
        {"name": "Donation__c", "label": "Donation", "custom": True, "records": 212_000},
        {"name": "Patient_Intake__c", "label": "Patient Intake", "custom": True, "records": 8_900},
        {"name": "Territory_Config__c", "label": "Territory Config", "custom": True, "records": 48},
        {"name": "Integration_Setting__mdt", "label": "Integration Setting", "custom": True, "records": 12},
    ]
    fields = {
        "Contact": [
            {"name": "Email", "type": "email", "pii": True},
            {"name": "Phone", "type": "phone", "pii": True},
            {"name": "MobilePhone", "type": "phone", "pii": True},
            {"name": "Birthdate", "type": "date", "pii": True},
            {"name": "SSN_Last4__c", "type": "string", "pii": True},
            {"name": "MailingStreet", "type": "textarea", "pii": True},
            {"name": "Preferred_Language__c", "type": "picklist", "pii": False},
            {"name": "Donor_Tier__c", "type": "picklist", "pii": False},
        ],
        "Lead": [
            {"name": "Email", "type": "email", "pii": True},
            {"name": "Phone", "type": "phone", "pii": True},
            {"name": "Company", "type": "string", "pii": False},
            {"name": "LeadSource", "type": "picklist", "pii": False},
        ],
        "Patient_Intake__c": [
            {"name": "Diagnosis_Notes__c", "type": "textarea", "pii": True},
            {"name": "Insurance_Member_Id__c", "type": "string", "pii": True},
            {"name": "Date_Of_Birth__c", "type": "date", "pii": True},
        ],
        "Donation__c": [
            {"name": "Card_Last4__c", "type": "string", "pii": True},
            {"name": "Amount__c", "type": "currency", "pii": False},
            {"name": "Campaign__c", "type": "reference", "pii": False},
        ],
    }
    integrations = {
        "named_credentials": [
            {"name": "Stripe_API", "endpoint": "https://api.stripe.com", "env": "production"},
            {"name": "NetSuite_ERP", "endpoint": "https://1234.suitetalk.api.netsuite.com", "env": "production"},
            {"name": "ModMed_EMA", "endpoint": "https://ema.modmed.com/api", "env": "production"},
        ],
        "remote_site_settings": ["https://api.stripe.com", "https://hooks.slack.com"],
        "outbound_messages": [{"name": "Send_Order_To_ERP", "endpoint": "https://erp.example.com/inbound"}],
        "scheduled_jobs": [
            {"name": "Nightly_Invoice_Sync", "class": "InvoiceSyncBatch", "cron": "0 0 2 * * ?"},
            {"name": "Lead_Score_Refresh", "class": "LeadScoreScheduler", "cron": "0 0 * * * ?"},
            {"name": "Donor_Receipt_Email", "class": "DonorReceiptJob", "cron": "0 30 7 * * ?"},
        ],
        "email_deliverability": "All email",
        "connected_apps": ["HubSpot Sync", "DocuSign", "Conga Composer", "Outreach.io"],
        "platform_event_triggers": ["OrderPlacedEvent__e"],
        "users": {"active": 412, "integration_users": 7, "admins": 9},
        "custom_settings_with_urls": ["Payment_Gateway__c.Endpoint__c", "Portal_Config__c.Base_URL__c"],
    }
    return {"org_name": "Acme Corp", "edition": "Enterprise Edition", "objects": objects,
            "fields": fields, "integrations": integrations, "data_storage_gb": 38.6, "file_storage_gb": 412.0}


def gen_target_schema() -> dict:
    """A Nonprofit Cloud target org (org-to-org consolidation scenario)."""
    return {
        "org_name": "Acme Foundation (Nonprofit Cloud)",
        "objects": {
            "Account": ["Name", "Website", "Industry", "NumberOfEmployees", "AnnualRevenue", "BillingCountry", "ParentId"],
            "Contact": ["FirstName", "LastName", "Email", "Phone", "MobilePhone", "Birthdate", "MailingStreet", "PreferredLanguage"],
            "GiftTransaction": ["Name", "OriginalAmount", "TransactionDate", "CampaignId", "DonorId", "PaymentMethod"],
            "MembershipRecord": ["Name", "StartDate", "EndDate", "MemberId", "MembershipLevel", "Status"],
        },
    }


def gen_source_schema() -> dict:
    return {
        "Account": ["Name", "Website", "Industry", "NumberOfEmployees", "AnnualRevenue", "BillingCountry", "ParentId", "Legacy_Region__c"],
        "Contact": ["FirstName", "LastName", "Email", "Phone", "MobilePhone", "Birthdate", "MailingStreet", "Preferred_Language__c", "Donor_Tier__c"],
        "Donation__c": ["Name", "Amount__c", "Donation_Date__c", "Campaign__c", "Donor__c", "Card_Last4__c"],
        "Membership__c": ["Name", "Start_Date__c", "End_Date__c", "Member__c", "Level__c", "Membership_Status__c"],
    }


def gen_reconciliation() -> dict:
    return {
        "Account": {"source": 18_400, "target": 18_400},
        "Contact": {"source": 96_200, "target": 96_143},
        "Donation__c→GiftTransaction": {"source": 212_000, "target": 211_520},
        "Membership__c→MembershipRecord": {"source": 41_000, "target": 41_000},
        "Attachments/Files": {"source": 58_210, "target": 57_902},
    }


CASES = [
    ("Billing portal shows wrong invoice total after plan change", "Billing", "Medium", False,
     "Customer reports invoice INV-20931 shows $4,820 instead of $3,950 after moving to the Growth plan on Oct 28. "
     "Contact: {name}, {email}, {phone}. Asked for a corrected invoice before their AP run on Friday."),
    ("Patient intake form lost medication notes", "Patient Intake", "High", True,
     "Clinic coordinator {name} ({email}, {phone}) says the intake for patient DOB 1974-03-12, insurance member ID "
     "HMO-883104552, lost the medication list (metformin 500mg, lisinopril 10mg) after sync from ModMed EMA. "
     "Patient visit is tomorrow 9:00; needs notes restored and confirmation of consent form on file."),
    ("SSO login loop after password reset", "Access", "High", False,
     "{name} ({email}) cannot log in since the password reset at 08:15. Redirect loop between Okta and Salesforce, "
     "11 users affected in the finance team. Workaround needed before quarter-close."),
    ("Donor asks to update card and receipt address", "Donations", "Low", True,
     "Donor {name} ({email}, {phone}) wants to replace card ending 4417 and send the 2026 tax receipt to "
     "221 Harbor Street, Apt 5, Portland OR 97201. Recurring gift of $250/month."),
    ("Data export of all contacts requested by customer", "Compliance", "Medium", True,
     "{name} ({email}) submitted a GDPR data-subject access request for all records held about them. "
     "Legal deadline: 30 days from Nov 1. Includes email history and call recordings."),
]
OPP_STAGES = ["Prospecting", "Qualification", "Proposal", "Negotiation", "Closed Won", "Closed Lost"]


def gen_cases(accounts, leads) -> list[dict]:
    out = []
    for i, (subject, typ, prio, sensitive, body) in enumerate(CASES):
        person = leads[i * 7 + 2]
        acc = accounts[i * 3 % len(accounts)]
        out.append({"Id": sfid("500", i + 1), "CaseNumber": f"0001{2840 + i}", "Subject": subject, "Type": typ,
                    "Priority": prio, "Status": "New" if i % 2 else "Working", "AccountName": acc["Name"],
                    "ContactName": f"{person['FirstName']} {person['LastName']}", "ContactEmail": person["Email"],
                    "Description": body.format(name=f"{person['FirstName']} {person['LastName']}",
                                               email=person["Email"] or "no email", phone=person["Phone"] or "no phone"),
                    "ContainsPHI": sensitive and typ == "Patient Intake", "ContainsPII": sensitive or True,
                    "CreatedDate": (TODAY - timedelta(days=i + 1)).isoformat()})
    return out


def gen_opportunities(accounts) -> list[dict]:
    out = []
    for i, acc in enumerate(accounts[:24]):
        stage = OPP_STAGES[i % len(OPP_STAGES)]
        out.append({"Id": sfid("006", i + 1), "Name": f"{acc['Name']} - Data Platform {2026 + i % 2}",
                    "AccountName": acc["Name"], "StageName": stage, "Amount": rng.choice([18_000, 42_000, 96_000, 180_000, 420_000]),
                    "CloseDate": (TODAY + timedelta(days=rng.randint(-40, 90))).isoformat(),
                    "Probability": {"Prospecting": 10, "Qualification": 25, "Proposal": 50, "Negotiation": 75, "Closed Won": 100, "Closed Lost": 0}[stage],
                    "NextStep": rng.choice(["Security review with IT", "Send revised pricing", "Exec sponsor call", "Legal redlines", "None"]),
                    "Competitor": rng.choice(["Incumbent CRM", "In-house build", None, "Large SI partner"]),
                    "DaysInStage": rng.choice([4, 12, 27, 45, 70]),
                    "Notes": rng.choice([
                        "Champion left the company last month; new VP has not engaged.",
                        "Pricing approved by finance; waiting on procurement paperwork.",
                        "Competitor offered 30% discount; customer asked us to match.",
                        "Strong technical fit; security questionnaire outstanding for 3 weeks.",
                        "Expansion of existing contract; usage up 40% QoQ."])})
    return out


def main() -> None:
    OUT.mkdir(exist_ok=True)
    accounts = gen_accounts()
    leads = gen_leads(accounts)
    files = {
        "accounts.json": accounts,
        "leads.json": leads,
        "metadata.json": gen_metadata(accounts, leads),
        "source_schema.json": gen_source_schema(),
        "target_schema.json": gen_target_schema(),
        "reconciliation.json": gen_reconciliation(),
        "cases.json": gen_cases(accounts, leads),
        "opportunities.json": gen_opportunities(accounts),
    }
    for name, data in files.items():
        (OUT / name).write_text(json.dumps(data, indent=2))
    print(f"wrote {len(files)} files, {len(leads)} leads, {len(accounts)} accounts → {OUT}")


if __name__ == "__main__":
    main()
