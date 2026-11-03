"use client";

import { ArrowRight, KeyRound, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useStatus } from "@/components/shell";
import { Badge, Button, cx, Empty, ErrorNote, PageHeader, SalesforceMark, Section } from "@/components/ui";
import { api, fmt, MODULES, useResource, type AuditEvent } from "@/lib/api";

const JOBS = [
  {
    href: "/refresh", module: "refresh", name: "Refresh & migrate",
    does: "Post-refresh checklist, PII masking, sandbox seed plan, org-to-org field mapping and record reconciliation.",
    evidence: "Sandboxes · data · migration",
  },
  {
    href: "/revenue", module: "revenue-agent", name: "Revenue agent",
    does: "Scores and tiers leads, picks a next best action, drafts outreach that cites only CRM facts, proposes updates and merges.",
    evidence: "Leads · outreach · hygiene",
  },
  {
    href: "/router", module: "ai-router", name: "AI router",
    does: "Salesforce as the data source for any model: routes each request to Salesforce itself, Claude, ChatGPT or a private LLM by sensitivity, stakes and cost, and masks PII before it leaves your network.",
    evidence: "Claude · ChatGPT · private LLM",
  },
  {
    href: "/review", module: "code-review", name: "Code review",
    does: "Static guardrails plus Claude review of Apex and Flows: governor limits, sharing/FLS, injection, secrets, tests. Returns fixed code.",
    evidence: "Apex · Flow · tests",
  },
];

export default function Overview() {
  const { status, refresh } = useStatus();
  const audit = useResource<AuditEvent[]>("/audit?limit=12");
  const [modeError, setModeError] = useState<string | null>(null);
  const [switching, setSwitching] = useState(false);

  const setMode = async (mode: "demo" | "live") => {
    setSwitching(true); setModeError(null);
    try { await api("/org/mode", { method: "POST", json: { mode } }); refresh(); }
    catch (e) { setModeError((e as Error).message); }
    finally { setSwitching(false); }
  };

  const lastRun = (module: string) => status?.recent_runs.find((r) => r.module === module || (module === "revenue-agent" && r.module === "dedupe"));
  const s = status?.stats;

  return (
    <>
      <PageHeader
        title="Overview"
        lede="Salesforce as the system of record for any AI model, plus refresh and migration planning, a revenue agent and Apex/Flow review. Agents propose; nothing touches the org until you approve it."
      />
      <ErrorNote message={modeError} />

      <section className="mb-6 grid gap-px overflow-hidden rounded-lg border border-line bg-line md:grid-cols-[1.4fr_1fr_1fr]">
        <div className="flex items-center gap-3.5 bg-surface px-4 py-3.5">
          <SalesforceMark size={40} />
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium">{status?.org.org_name ?? "Connecting to API…"}</p>
            <p className="text-[12.5px] text-ink-3">{status?.org.mode === "live" ? status.org.instance_url : `${status?.org.edition ?? ""} · 248 leads · 14 objects · 3 integrations`}</p>
          </div>
          {status?.salesforce_configured && <div role="radiogroup" aria-label="Org" className="flex rounded-md border border-line-strong p-0.5">
            {(["demo", "live"] as const).map((m) => (
              <button key={m} role="radio" aria-checked={status?.org.mode === m} disabled={switching}
                onClick={() => setMode(m)}
                title={m === "live" && !status?.salesforce_configured ? "Add SF_* credentials to api/.env first" : undefined}
                className={cx("rounded px-2.5 py-1 text-[12.5px] font-medium capitalize",
                  status?.org.mode === m ? "bg-accent text-accent-ink" : "text-ink-2 hover:text-ink")}>{m === "demo" ? "Acme Corp" : "Connected org"}</button>
            ))}
          </div>}
        </div>
        <div className="flex items-center gap-3 bg-surface px-4 py-3.5">
          <KeyRound size={18} className="text-accent" />
          <div>
            <p className="font-medium">{status?.claude.configured ? "Claude agents" : "Rules engine"}</p>
            <p className="text-[12.5px] text-ink-3">
              {status?.claude.configured ? <span className="font-mono">{status.claude.agent_model}</span> : "Deterministic checks, scoring and plans"}
            </p>
          </div>
        </div>
        <Link href="/approvals" className="group flex items-center gap-3 bg-surface px-4 py-3.5 hover:bg-sunken/40">
          <ShieldCheck size={18} className="text-accent" />
          <div className="flex-1">
            <p className="font-medium"><span className="font-mono tabular">{s?.pending_approvals ?? 0}</span> waiting for approval</p>
            <p className="text-[12.5px] text-ink-3"><span className="tabular">{fmt.n(s?.approved)}</span> approved · <span className="tabular">{fmt.n(s?.audit_events)}</span> audit events</p>
          </div>
          <ArrowRight size={15} className="text-ink-3 transition-transform group-hover:translate-x-0.5" />
        </Link>
      </section>

      <div className="grid items-start gap-6 lg:grid-cols-[1fr_360px]">
        <Section title="Automations">
          <ul className="divide-y divide-line">
            {JOBS.map((j) => {
              const run = lastRun(j.module);
              return (
                <li key={j.href}>
                  <Link href={j.href} className="group grid gap-2 px-4 py-4 hover:bg-sunken/40 md:grid-cols-[180px_1fr_auto] md:items-center md:gap-5">
                    <div>
                      <p className="font-semibold text-ink">{j.name}</p>
                      <p className="text-[12px] text-ink-3">{j.evidence}</p>
                    </div>
                    <p className="text-ink-2">{j.does}</p>
                    <div className="flex items-center gap-3 md:justify-end">
                      <span className="text-[12px] text-ink-3">
                        {run ? <>Last run {fmt.dateTime(run.created_at)}{run.status === "failed" && <Badge tone="danger" className="ml-1">failed</Badge>}</> : "Not run yet"}
                      </span>
                      <ArrowRight size={15} className="text-ink-3 transition-transform group-hover:translate-x-0.5 group-hover:text-accent" />
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        </Section>

        <Section title="Recent activity" aside={<Link href="/approvals?tab=audit" className="hover:text-ink">Full audit log</Link>}>
          {audit.data && audit.data.length > 0 ? (
            <ol className="divide-y divide-line">
              {audit.data.map((e) => (
                <li key={e.id} className="px-4 py-2.5">
                  <p className="truncate text-[13px] text-ink">{e.summary}</p>
                  <p className="text-[11.5px] text-ink-3">
                    <span className="font-mono tabular">{fmt.time(e.at)}</span> · {MODULES[e.actor] ?? e.actor} · {e.kind.replaceAll("_", " ")}
                  </p>
                </li>
              ))}
            </ol>
          ) : (
            <Empty title="Nothing has run yet">Start with Code review: pick a file from the library and run it. It takes a few seconds.</Empty>
          )}
          {audit.error && <p className="px-4 pb-3 text-critical">{audit.error}</p>}
          <div className="border-t border-line px-4 py-2.5">
            <Button variant="ghost" onClick={async () => { if (confirm("Clear all runs, approvals and audit events?")) { await api("/reset", { method: "POST" }); audit.reload(); refresh(); } }}>
              Reset workspace
            </Button>
          </div>
        </Section>
      </div>
    </>
  );
}
