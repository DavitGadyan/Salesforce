"""Market analysis of 14 Upwork Salesforce/AI job posts (captured 2026-11-03).

Filter: keep posts where the client is real (spend history, interviews or hires
on this post). Ghost / unproven posts are listed but excluded from the patterns.
"""

JOBS = [
    {"title": "Test automated sandbox refresh & data migration tool", "client": "Flosum (US)", "spend": "$1.1M", "hires_total": 490,
     "interviews": 7, "hires": 2, "budget": "$150 fixed ×many", "tier": 1, "pattern": 1,
     "why": "Repeat-hiring, $1.1M spent, 4.87★ over 318 reviews; running the same test job dozens of times."},
    {"title": "AI sales & revenue platform (CRM reactivation + website AI seller)", "client": "DMA (Naples, US)", "spend": "$796K",
     "hires_total": 751, "interviews": 11, "hires": 1, "budget": "Open, V1 1–3 months", "tier": 1, "pattern": 2,
     "why": "Biggest interview count; detailed spec; 30K-record CRM to reactivate."},
    {"title": "Senior Salesforce Developer (Apex, LWC, Flow) with AI tools", "client": "Toronto, CA", "spend": "$1.1K",
     "hires_total": 15, "interviews": 6, "hires": 2, "budget": "Hourly, 30+ hrs/wk, 6+ months", "tier": 2, "pattern": 3,
     "why": "Two hires already; tests candidates on 5 AI-generated code samples."},
    {"title": "Nonprofit Cloud org consolidation + workflows", "client": "Sherman Oaks, US", "spend": "$1.1K", "hires_total": 7,
     "interviews": 8, "hires": 0, "budget": "$25–35/hr", "tier": 3, "pattern": 1,
     "why": "Interviews happening, but 6% hire rate and 39 open jobs (staffing pattern)."},
    {"title": "RevOps (Salesforce + HubSpot) paid test", "client": "Cabot Insights (IE)", "spend": "$3K", "hires_total": 13,
     "interviews": 1, "hires": 0, "budget": "$180 test → client work", "tier": 3, "pattern": 1,
     "why": "Real agency, 69% hire rate; test covers dedupe, lead routing Flow, reconciliation."},
    {"title": "Semi-autonomous AI sales agent with Claude Code", "client": "Glenso (NL)", "spend": "$700", "hires_total": 3,
     "interviews": 2, "hires": 0, "budget": "$19–35/hr", "tier": 3, "pattern": 2,
     "why": "Small but concrete: approval step per email, CRM logging, no invented facts."},
    {"title": "1-hour consult: AI agents connected to a CRM (MCP)", "client": "Fractional COO (CA)", "spend": "$11K", "hires_total": 49,
     "interviews": 0, "hires": 0, "budget": "Hourly consult", "tier": 3, "pattern": 2, "why": "Fresh post; scoping a client build."},
    {"title": "AI-native CRM replacing Salesforce (HIPAA, 4 weeks)", "client": "New account", "spend": "$0", "hires_total": 0,
     "interviews": 7, "hires": 0, "budget": "Not stated", "tier": 0, "pattern": 2, "why": "No spend history; scope far beyond a 4-week budget."},
    {"title": "Salesforce + Stripe complex Flows", "client": "New account", "spend": "$0", "hires_total": 0, "interviews": 4,
     "hires": 0, "budget": "$5–40/hr", "tier": 0, "pattern": 3, "why": "New account, no spend."},
    {"title": "Physician data enrichment into Salesforce", "client": "Unverified payment", "spend": "$0", "hires_total": 0,
     "interviews": 0, "hires": 0, "budget": "$18–75/hr", "tier": 0, "pattern": 2, "why": "Payment not verified, 132 proposals, 0 interviews."},
    {"title": "Dynamics 365 replacement for Salesforce Marketing Cloud", "client": "Dubai", "spend": "$22K", "hires_total": 9,
     "interviews": 0, "hires": 0, "budget": "Hourly", "tier": 0, "pattern": 1, "why": "No interviews after a week."},
    {"title": "Revenue Cloud consultants", "client": "Recruiter (DE)", "spend": "$47K", "hires_total": 14, "interviews": 0,
     "hires": 0, "budget": "Hourly", "tier": 0, "pattern": None, "why": "Recruiter, 3% hire rate."},
    {"title": "Marketing Cloud Personalization experts", "client": "Recruiter (DE)", "spend": "$47K", "hires_total": 14,
     "interviews": 0, "hires": 0, "budget": "Hourly", "tier": 0, "pattern": None, "why": "Recruiter, 3% hire rate."},
    {"title": "Admin to test a new AppExchange app (1 hour)", "client": "Laramie, US", "spend": "$349", "hires_total": 9,
     "interviews": 0, "hires": 0, "budget": "$10–50/hr", "tier": 0, "pattern": None, "why": "1-hour usability test, not automation work."},
]

PATTERNS = [
    {"id": 1, "name": "Org data lifecycle: refresh, seed, migrate, reconcile", "module": "refresh",
     "demand": "Flosum ($1.1M spend) runs this test job repeatedly; Nonprofit org merge, Cabot RevOps test, AI-CRM migration.",
     "needs": ["Post-refresh checklist: email deliverability, Named Credentials, scheduled jobs, connected apps",
               "Mask PII before developers touch the data", "Seed master + referentially-intact test data into Developer sandboxes",
               "Org-to-org field mapping (e.g. into Nonprofit Cloud)", "Record-count reconciliation and duplicate handling"]},
    {"id": 2, "name": "AI revenue agent on the CRM, human-in-the-loop", "module": "revenue",
     "demand": "DMA ($796K spend, 11 interviews) plus Glenso, the COO consult, physician enrichment and the AI-CRM post.",
     "needs": ["Score and tier existing records (A/B/C) with reasons", "Next Best Action per record",
               "Personalised reactivation drafts that cite only CRM facts", "Approval queue before anything is sent or written",
               "CRM write-back and an audit log of every AI decision"]},
    {"id": 3, "name": "AI-accelerated Apex/Flow with guardrail review", "module": "code-review",
     "demand": "Toronto client hired 2 and screens with 5 AI-generated samples; Stripe/Flows and Cabot's lead-routing Flow.",
     "needs": ["Catch SOQL/DML in loops and missing bulkification", "Sharing, FLS/CRUD and SOQL-injection checks",
               "Hardcoded Ids/secrets → Named Credentials, Custom Metadata", "Fix the code and generate real bulk tests"]},
]

CROSS_CUTTING = [
    "Every write needs a human approval step (sends, merges, payment changes)",
    "Audit log of every lookup, tool call and AI decision",
    "Client owns the code, keys and data; runs in their accounts",
    "Fluency with Claude Code / agent SDKs, but with judgement over AI output",
]

INSIGHTS = {"captured": "2026-11-03", "jobs": JOBS, "patterns": PATTERNS, "cross_cutting": CROSS_CUTTING,
            "filter_rule": "Real = client has spend history AND this post shows interviews or hires. "
                           "Tier 1: ≥$100K spend + interviews + hires. Tier 2: hires on this post. Tier 3: interviews or a credible paid test. "
                           "Tier 0 (excluded): no spend, unverified payment, recruiter spam or zero interviews."}
