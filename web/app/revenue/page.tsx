"use client";

import { Copy, Play, X } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useStatus } from "@/components/shell";
import { Badge, Button, cx, Empty, EngineNote, ErrorNote, Field, PageHeader, Rich, RunLog, Section, Tabs, Tier } from "@/components/ui";
import { fmt, useResource, useRun, type Approval, type Lead } from "@/lib/api";

type Filter = "all" | "A" | "B" | "C" | "assessed";

export default function RevenuePage() {
  const leads = useResource<Lead[]>("/leads");
  const approvals = useResource<Approval[]>("/approvals");
  const { refresh } = useStatus();
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [batch, setBatch] = useState(8);
  const after = () => { leads.reload(); approvals.reload(); refresh(); };
  const agent = useRun<any>(after);
  const dedupe = useRun<any>(after);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (leads.data ?? []).filter((l) =>
      (filter === "all" || (filter === "assessed" ? l.assessed : l.tier === filter)) &&
      (!q || `${l.FirstName} ${l.LastName} ${l.Company} ${l.Email}`.toLowerCase().includes(q)));
  }, [leads.data, filter, query]);

  const tierCount = (t: string) => leads.data?.filter((l) => l.tier === t).length ?? 0;
  const lead = leads.data?.find((l) => l.Id === selected) ?? null;
  const pendingFor = (id: string) => approvals.data?.filter((a) => a.status === "pending" && (a.target === id || a.payload.record_ids?.includes(id))) ?? [];
  const activeRun = agent.run ?? dedupe.run;

  return (
    <>
      <PageHeader
        title="Revenue agent"
        lede="Works your leads like a careful SDR: scores and tiers each one, picks a next best action and drafts outreach. Every fact in a draft is checked against the CRM, and every send or update waits in Approvals."
        actions={<>
          <Button loading={dedupe.running} onClick={() => dedupe.start("/runs/dedupe")}>Find duplicates</Button>
          <label className="flex h-8 items-center gap-1.5 rounded-md border border-line-strong bg-surface pl-2.5 text-[13px] text-ink-2">
            Batch
            <select value={batch} onChange={(e) => setBatch(+e.target.value)} className="h-full rounded-r-md bg-transparent pr-1 font-mono text-ink" aria-label="Batch size">
              {[4, 8, 16, 32].map((n) => <option key={n}>{n}</option>)}
            </select>
          </label>
          <Button variant="primary" icon={<Play size={14} />} loading={agent.running} onClick={() => agent.start("/runs/revenue", { limit: batch })}>
            Run agent on next {batch}
          </Button>
        </>}
      />
      <ErrorNote message={agent.error ?? dedupe.error ?? leads.error} />
      {activeRun && <RunLog run={activeRun} />}
      {activeRun?.status === "done" && activeRun.result && (
        <div className="rise mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-accent/25 bg-accent-soft/60 px-4 py-2.5">
          <EngineNote engine={activeRun.result.engine} />
          <span className="min-w-0 flex-1 text-ink"><Rich text={activeRun.result.summary ?? `Queued ${activeRun.result.clusters} merge proposals.`} /></span>
          <Link href="/approvals" className="shrink-0 font-medium text-accent underline">Review in Approvals</Link>
        </div>
      )}

      <div className={cx("grid gap-6", lead && "xl:grid-cols-[minmax(0,1fr)_400px]")}>
        <Section title="Leads" aside={<span className="tabular">{rows.length} of {leads.data?.length ?? 0}</span>}>
          <div className="flex flex-col gap-2 border-b border-line md:flex-row md:items-center md:pr-3">
            <Tabs value={filter} onChange={setFilter} items={[
              { id: "all", label: "All" },
              { id: "A", label: `Tier A · ${tierCount("A")}` },
              { id: "B", label: `Tier B · ${tierCount("B")}` },
              { id: "C", label: `Tier C · ${tierCount("C")}` },
              { id: "assessed", label: "Assessed by agent" },
            ]} />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search name, company, email"
              className="mx-3 mb-2 h-8 rounded-md border border-line-strong bg-surface px-2.5 text-[13px] placeholder:text-ink-3 md:mx-0 md:mb-0 md:ml-auto md:w-64" />
          </div>
          {leads.loading && !leads.data ? <Empty title="Loading leads…" /> : rows.length === 0 ? <Empty title="No leads match">Clear the search or pick another tier.</Empty> : (
            <div className="max-h-[640px] overflow-auto">
              <table className="w-full text-left text-[13px]">
                <thead className="sticky top-0 z-10 bg-surface text-[12px] text-ink-3 shadow-[0_1px_0_var(--line)]">
                  <tr><th className="px-4 py-2 font-medium">Lead</th><th className="px-2 py-2 font-medium">Tier</th><th className="px-2 py-2 text-right font-medium">Score</th>
                    <th className="hidden px-3 py-2 font-medium md:table-cell">Next best action</th><th className="hidden px-3 py-2 font-medium lg:table-cell">Last active</th></tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {rows.map((l) => (
                    <tr key={l.Id} onClick={() => setSelected(l.Id)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && setSelected(l.Id)}
                      className={cx("cursor-pointer hover:bg-sunken/50", selected === l.Id && "bg-accent-soft/50")}>
                      <td className="px-4 py-2.5">
                        <p className="font-medium text-ink">{l.FirstName} {l.LastName}{!l.Email && <Badge tone="warn" className="ml-2">no email</Badge>}</p>
                        <p className="text-[12px] text-ink-3">{l.Title ?? "No title"} · {l.Company}</p>
                      </td>
                      <td className="px-2 py-2.5"><Tier tier={l.tier} /></td>
                      <td className="px-2 py-2.5 text-right font-mono tabular">{l.score}</td>
                      <td className="hidden max-w-[340px] px-3 py-2.5 text-ink-2 md:table-cell">
                        <span className="line-clamp-2">{l.next_best_action}</span>
                        {l.assessed && <span className="text-[11.5px] text-accent">{l.engine === "claude" ? "Claude" : "Rules"} assessment</span>}
                      </td>
                      <td className="hidden whitespace-nowrap px-3 py-2.5 text-ink-3 lg:table-cell">{fmt.ago(l.LastActivityDate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>

        {lead && (
          <aside className="rise min-w-0 xl:sticky xl:top-8 xl:self-start">
            <Section title={`${lead.FirstName} ${lead.LastName}`} aside={<button onClick={() => setSelected(null)} aria-label="Close" className="rounded p-1 hover:bg-sunken"><X size={15} /></button>}>
              <div className="space-y-4 px-4 py-4">
                <div className="flex items-center gap-3">
                  <Tier tier={lead.tier} />
                  <div>
                    <p className="font-medium">Score <span className="font-mono tabular">{lead.score}</span> / 100</p>
                    <p className="text-[12px] text-ink-3">{lead.assessed ? `Assessed by ${lead.engine === "claude" ? "Claude" : "the rules engine"}` : "Baseline (not yet worked by the agent)"}</p>
                  </div>
                </div>
                <div className="rounded-md bg-accent-soft/60 px-3 py-2.5">
                  <p className="text-[12px] font-medium text-accent">Next best action</p>
                  <p className="text-ink">{lead.next_best_action}</p>
                </div>
                <div>
                  <p className="mb-1 text-[12px] font-medium text-ink-3">Why</p>
                  <ul className="space-y-1 text-ink-2">{lead.reasons.map((r, i) => <li key={i} className="flex gap-2"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-ink-3" />{r}</li>)}</ul>
                  <p className="mt-2 flex flex-wrap items-center gap-1 text-[12px] text-ink-3">Evidence: {lead.sources.map((s) => <Field key={s} name={s} />)}</p>
                </div>
                <dl className="grid grid-cols-[96px_1fr] gap-x-3 gap-y-1.5 border-t border-line pt-3 text-[13px]">
                  {([["Email", lead.Email], ["Phone", lead.Phone], ["Industry", lead.Industry], ["Employees", fmt.n(lead.NumberOfEmployees)],
                    ["Source", lead.LeadSource], ["Status", lead.Status], ["Owner", lead.OwnerName], ["Record Id", lead.Id]] as const).map(([k, v]) => (
                    <div key={k} className="contents"><dt className="text-ink-3">{k}</dt><dd className={cx("min-w-0 truncate", (k === "Record Id" || k === "Email") && "font-mono text-[12px]")}>{v ?? <span className="text-ink-3">empty</span>}</dd></div>
                  ))}
                </dl>
                {lead.Activity?.length > 0 && (
                  <div className="border-t border-line pt-3">
                    <p className="mb-1 text-[12px] font-medium text-ink-3">Activity</p>
                    <ul className="space-y-0.5 text-ink-2">{lead.Activity.map((a) => <li key={a}>{a}</li>)}</ul>
                  </div>
                )}
                <div className="border-t border-line pt-3">
                  <p className="mb-2 text-[12px] font-medium text-ink-3">Waiting for approval</p>
                  {pendingFor(lead.Id).length === 0 ? <p className="text-ink-3">Nothing queued for this lead.</p> : pendingFor(lead.Id).map((a) => (
                    <div key={a.id} className="mb-2 rounded-md border border-line px-3 py-2">
                      <p className="flex items-center gap-2 font-medium"><Badge tone="accent">{a.kind.replace("_", " ")}</Badge>{a.title}</p>
                      {a.kind === "send_email" && <p className="mt-1 line-clamp-3 whitespace-pre-line text-ink-2">{a.payload.body}</p>}
                    </div>
                  ))}
                  <Link href="/approvals" className="text-[13px] font-medium text-accent underline">Open Approvals</Link>
                </div>
                <Button variant="ghost" icon={<Copy size={13} />} onClick={() => navigator.clipboard?.writeText(lead.Id)}>Copy record Id</Button>
              </div>
            </Section>
          </aside>
        )}
      </div>
    </>
  );
}

