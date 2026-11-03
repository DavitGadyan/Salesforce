# Upwork Salesforce automation demand: what real clients pay for

Captured 2026-11-03 from 14 job posts. The same data is served at `GET /api/insights`
(source: `api/app/insights.py`) and shown on the app's "Why these three" page.

## Filter: real clients vs ghost posts

A post counts only if the client has **spend history** and the post shows **interviews or hires**.

| Tier | Rule | Posts |
|---|---|---|
| 1 | ≥ $100K spend + interviews + hires | Flosum sandbox-refresh tool test ($1.1M, 7 interviews, 2 hires, many repeat posts) · DMA AI sales platform ($796K, 11 interviews, 1 hire) |
| 2 | Hires on this post | Senior SF developer with AI tools, Toronto (2 hires) |
| 3 | Interviews or a credible paid test | Nonprofit Cloud org merge (8 interviews, 6% hire rate) · Cabot RevOps paid test · Glenso Claude sales agent · COO consult on CRM agents |
| 0 (excluded) | No spend, unverified payment, recruiters, zero interviews | AI-native CRM (new account) · Stripe Flows (new account) · Physician enrichment (unverified) · Dynamics migration · 2× recruiter posts · 1-hour AppExchange test |

## Top 3 use cases

1. **Org data lifecycle: refresh, seed, migrate, reconcile.** The highest-spend client re-runs this
   job. Needs: post-refresh checklist (email deliverability, Named Credentials, scheduled jobs, connected
   apps), PII masking, master + test data seeding for Developer sandboxes, org-to-org mapping (e.g. into
   Nonprofit Cloud), record reconciliation and dedupe.
2. **AI revenue agent on the CRM, human-in-the-loop.** Score and tier existing records, Next Best Action,
   personalised reactivation that cites only CRM facts, approval before any send or write, CRM write-back,
   an audit log of every AI decision.
3. **AI-accelerated Apex/Flow with guardrail review.** Catch SOQL/DML in loops, missing bulkification,
   sharing/FLS gaps, SOQL injection, hardcoded Ids and secrets, weak tests; return fixed code and tests.

**Every serious client also asked for:** a human approval step on writes, an audit log, client-owned
code and keys, and Claude Code / agent-SDK fluency with judgement over AI output.
