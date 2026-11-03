# Upwork portfolio item: SF Ops Copilot

**Project title** (max 70):
Hybrid AI for Salesforce: Claude, ChatGPT & private LLMs, one router

**Your role:**
Solo developer: product, architecture, backend, AI agents, UI

**Project description** (≤ 600 characters):
Use AI on your Salesforce data without moving off Salesforce, overpaying for one model, or leaking customer data. A router sends each request to Salesforce itself, Claude, ChatGPT or a private LLM in your network, chosen by sensitivity, stakes and cost; PII is masked before it leaves. On top: Apex/Flow review that returns fixed code and tests, a revenue agent that works dormant leads with fact-checked drafts, and a sandbox refresh and migration planner. Nothing is written to Salesforce until a person approves it, and every AI decision is logged.

**Alternative description, shorter and outcome-first** (≤ 600 characters):
Your team wants AI on Salesforce data, but legal worries about customer data, finance about model bills, and admins about AI-written code breaking production. This app handles all three: each request goes to the cheapest safe option (Salesforce itself, Claude, ChatGPT or a private LLM), sensitive fields are masked or kept in-network, and AI-generated Apex is reviewed and fixed before deploy. Agents only propose; people approve, and everything is audit-logged.

**Skills** (pick 5):
Salesforce · AI Agent Development · API Integration · Apex · Python
(alternates: LLM, OpenAI API, Salesforce Lightning, Next.js, Data Migration)

## Content blocks (in this order)

1. Video: `video/sf-ops-copilot-walkthrough.mp4` (real-time runs; model waits shown at 8×)
2. Image `images/17-router-private-llm.jpg`, caption: *Patient data is routed to a private LLM and never leaves the network*
3. Image `images/16-router-masked-prompt.jpg`, caption: *PII is tokenised before Claude sees it, then restored in the answer*
4. Image `images/18-router-benchmark.jpg`, caption: *The same Salesforce record across Claude Opus, Claude Haiku and a private model*
5. Image `images/04-code-review-corrected-diff.jpg`, caption: *Apex review: 14 findings, then corrected Queueable code and a bulk test*
6. Image `images/07-approvals-email.jpg`, caption: *Revenue agent drafts are fact-checked against the CRM and wait for approval*
7. Image `images/13-refresh-architect-review.jpg`, caption: *Sandbox refresh plan with Claude's architect review and runbook*
8. Text block, "Why this matters for your business" (full text in the section below)
9. Text block:
   Stack: Claude Opus 5.5 and Haiku 5.5 (structured outputs, tool-use agent loop, prompt caching), OpenAI SDK
   for ChatGPT and any OpenAI-compatible private model (Ollama/vLLM), Python/FastAPI, Next.js + Tailwind,
   Salesforce REST & Tooling APIs, SQLite audit log. A deterministic rules engine runs underneath the AI,
   so every result is grounded and testable.

Thumbnail: `images/00-thumbnail-hybrid-ai.jpg` (business-case cover; source `thumbnail.html`, re-render with Playwright at 1600×1200).
Per-module clips: `video/ai-router.mp4`, `video/code-review.mp4`, `video/revenue-agent.mp4`, `video/refresh.mp4`.

## Business case text block (paste as block 8)

**Why this matters for your business**

Teams hiring for Salesforce + AI work keep describing the same problems. This project answers each one with something working, not slides.

**1. "We want AI on our CRM data, but it can't leak."**
Clinics, recruiters and financial-services teams hold patient, candidate and payment data in Salesforce. The router finds sensitive fields in every record. Medical and card data goes only to a model inside your network; names, emails and phones are replaced with tokens before any outside model sees them, then restored in the answer. You keep Salesforce as the system of record and still use the best model for each job.

**2. "AI is getting expensive, and we're locked into one vendor."**
Not every question needs a large model. In this build a pipeline question is answered by Salesforce itself for $0; a case summary costs under a cent on Claude Opus; the same deal-risk assessment cost $0.007 on Claude Opus, $0.0001 on Claude Haiku, and nothing per call on the private model. A compare view runs the same record across every connected model, so the routing choice rests on your data, not a vendor's pitch. Adding or swapping a provider is a setting, not a rebuild.

**3. "Our team ships Apex and Flows written with AI, and it breaks in production."**
AI-written Salesforce code often looks fine and fails at scale: queries inside loops, missing sharing and field security, hard-coded IDs and keys. Every file is checked by fixed rules first, then reviewed by Claude, which returns fixed code and a bulk test class. On one sample payment class it confirmed 8 rule findings and found 4 more that rules can't see, including a callout-after-DML error that stops the job after the first record.

**4. "We have thousands of old leads nobody works."**
The revenue agent scores and tiers each lead, picks a next best action and drafts a short, specific email. Every fact in a draft is checked against the record, and drafts citing anything that isn't in the CRM go back for rewrite. Nothing is sent or updated until a person approves it.

**5. "Sandbox refreshes and org migrations eat days of admin time."**
After each refresh someone has to mask personal data, point integrations at test endpoints, stop scheduled jobs and reload test data, usually from memory. The planner builds that checklist from the org's own metadata, orders the data seeding so lookups resolve, maps fields for an org-to-org move, reconciles record counts, and has Claude review the plan and write the runbook.

**What you get if we work together:** the same approach applied to your org. Your models, your data rules, your approval steps, with code and keys in your accounts from day one.
