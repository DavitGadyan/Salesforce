# SF Ops Copilot

One product for the three Salesforce automations that high-spend Upwork clients keep hiring for
(analysis: [docs/market-analysis.md](docs/market-analysis.md)):

| Module | What it does |
|---|---|
| **Refresh & migrate** | Inventories the org, builds the post-refresh checklist, PII masking plan, Developer-sandbox seed order, org-to-org field mapping and record reconciliation. Claude reviews it as an architect and writes an ordered runbook. |
| **Revenue agent** | Claude tool-use agent that scores and tiers leads, picks a Next Best Action, drafts outreach and proposes CRM updates. Every fact in a draft is checked against the record, and false claims go back to the model. Duplicate scan proposes merges. |
| **Code review** | Deterministic Apex/Flow guardrails (SOQL/DML/callouts in loops, sharing, FLS, injection, hardcoded Ids/secrets, test quality), then Claude confirms each finding, adds new ones, and returns corrected code plus a bulk test class. |
| **AI router** | Treats Salesforce as the data source for *any* model. Each request is routed by policy to Salesforce itself (SOQL, no model), Claude Opus, Claude Haiku, ChatGPT or a private LLM in your network (Ollama/vLLM). The trust layer detects PII/PHI/PCI and masks it before anything leaves the network; providers that are down are skipped with a fallback, and a compare mode runs one record across every connected model. |
| **Approvals & audit** | Agents can't write to Salesforce or send anything. Each proposed action waits here (editable), and every run, model call, tool call and decision is logged with tokens. |

Runs fully on a **seeded demo org** with no keys at all (the rules engine). Add an Anthropic key for the
Claude agents, and Salesforce credentials to switch to a **live org**. For the AI router, set
`OPENAI_API_KEY` for ChatGPT and point `PRIVATE_LLM_BASE_URL`/`PRIVATE_LLM_MODEL` at any OpenAI-compatible
server. The default is Ollama on `localhost:11434` with `qwen2.5:7b`.

## Run it

```bash
make setup                 # venv + npm install, creates api/.env
# put ANTHROPIC_API_KEY in api/.env (optional)
make api                   # http://localhost:8000  (FastAPI, docs at /docs)
make web                   # http://localhost:3210  (Next.js, proxies /api)
make test                  # backend tests
```

Requires Python 3.12 and Node 20+.

## Architecture

```
web/  Next.js 15 + Tailwind v4 ── /api/* rewrite ──▶ api/  FastAPI
                                                     ├─ agents/      refresh · revenue (tool loop) · code_review
                                                     ├─ router/      providers · trust (PII masking) · engine (policy, fallback, benchmark)
                                                     ├─ rules/       apex_checks · dedupe · scoring · refresh
                                                     ├─ connectors/  demo (demo_data/*.json) | salesforce (REST/Tooling via httpx)
                                                     └─ core/        llm (Anthropic SDK) · db (SQLite: runs, audit, approvals)
```

- Claude: `claude-opus-5-5` with structured outputs (Pydantic → strict JSON schema) and a manual,
  append-only tool loop with `strict` tools. Server-side refusal fallback is on (`fallbacks: "default"`),
  and system prompts are prompt-cached. Every call is audited with token counts and cost.
- Runs execute in background threads; the UI polls `/api/runs/{id}` for progress.
- Write actions (`update_record`, `send_email`, `merge_records`) only exist as approvals. In demo mode, sends
  and merges are simulated. In live mode, approved updates PATCH the record over the REST API.

## Branding

- Styling follows developer.salesforce.com: navy `#032D60` headings, `#0176D3` actions, SLDS grays and
  borders, a pale blue page wash. Salesforce Sans and ITC Avant Garde aren't licensed for reuse, so the open
  fonts Source Sans 3 (body) and Poppins (headings) stand in for them.
- `web/public/salesforce.svg` is the Salesforce logo from salesforce.com. It's used only to mark the
  connected org (nominative use); the app keeps its own name and favicon. Salesforce and the cloud logo are
  trademarks of Salesforce, Inc. Check their trademark guidelines before shipping this commercially.
- The built-in workspace org is "Acme Corp" (fictional data in `demo_data/`, regenerate with `make seed`).
