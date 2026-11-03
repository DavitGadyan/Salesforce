# SF Ops Copilot — product context

**What it is.** One app that does the three Salesforce automation jobs high-value Upwork clients keep paying for
(see docs/market-analysis.md): sandbox refresh / seeding / org-to-org migration, an AI revenue agent with
human approval, and guardrail review of AI-generated Apex & Flows.

**Key value proposition.** Salesforce stays the system of record while any model can work on its data:
a policy router sends each request to Salesforce itself, Claude, ChatGPT or a private LLM by sensitivity,
stakes and cost, and masks sensitive data before it leaves the network.

**Who uses it.** Salesforce admins, architects and RevOps leads at mid-size orgs (large data volume, many
integrations). Also: the freelancer demoing it to prospective clients on a screen share.

**Use scene.** Daytime desk work in a browser next to Salesforce Setup. Long sessions reading tables, then
deliberate decisions (approve a CRM write, sign off a refresh). Trust and legibility beat spectacle.

**Mode.** Operate (app UI). The Insights page is Read.

**Tone.** Calm, exact, accountable. Every AI output shows its evidence (fields used, rule ids, line numbers)
and every write waits for a human.

**Visual direction (chosen by the user).** "Calm ops console": paper-white surfaces, ink text, one deep teal
accent, monospace only for ids, code and numbers, dense tables.

**Assumptions (not confirmed by the user).** English only; desktop-first but usable on a phone; no login.
