"use client";

import { Check, Download, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Badge, Button, cx, Empty, EngineNote, ErrorNote, Field, PageHeader, RunLog, Section, SeverityBadge } from "@/components/ui";
import { fmt, useResource, useRun, type Severity } from "@/lib/api";

interface Plan {
  inventory: { org_name: string; objects: { name: string; label: string; custom: boolean; records: number }[]; integrations: any; data_storage_gb: number; file_storage_gb: number };
  checklist: { id: string; category: string; title: string; detail: string; risk: Severity; automatable: boolean }[];
  pii: { object: string; field: string; type: string; strategy: string }[];
  seed_plan: { step: number; object: string; kind: string; records: number; depends_on: string[] }[];
  mapping: { source_object: string; source_field: string; target_object: string | null; target_field: string | null; confidence: number; note: string }[];
  reconciliation: { object: string; source: number; target: number | null; diff: number | null; pct: number | null; status: string }[];
  review?: { executive_summary: string; extra_checks: { category: string; title: string; detail: string; risk: Severity }[];
    mapping_reviews: { source_object: string; source_field: string; recommendation: string; rationale: string }[];
    risks: string[]; runbook: { phase: string; action: string; verification: string }[] } | null;
  engine?: string;
}

const STEPS = [
  { id: "inventory", label: "Inventory", hint: "What's in Production" },
  { id: "checklist", label: "Post-refresh", hint: "Neutralise & mask" },
  { id: "seed", label: "Seed data", hint: "Developer sandboxes" },
  { id: "mapping", label: "Org mapping", hint: "Org-to-org move" },
  { id: "reconcile", label: "Reconcile", hint: "Prove nothing was lost" },
] as const;
type Step = (typeof STEPS)[number]["id"];

export default function RefreshPage() {
  const [pct, setPct] = useState(2);
  const base = useResource<Plan>(`/refresh/plan?sample_pct=${pct}`);
  const review = useRun<Plan>();
  const [step, setStep] = useState<Step>("inventory");
  const [done, setDone] = useState<Set<string>>(new Set());
  useEffect(() => { try { setDone(new Set(JSON.parse(localStorage.getItem("refresh-done") ?? "[]"))); } catch {} }, []);
  const toggle = (id: string) => setDone((d) => {
    const n = new Set(d);
    if (n.has(id)) n.delete(id); else n.add(id);
    try { localStorage.setItem("refresh-done", JSON.stringify([...n])); } catch {}
    return n;
  });

  const plan = (review.run?.status === "done" && review.run.result) || base.data;
  const ai = review.run?.status === "done" ? review.run.result?.review : null;

  return (
    <>
      <PageHeader
        title="Refresh & migrate"
        lede="Everything that has to happen when Production is copied into a sandbox, or one org is merged into another, built from the org's own metadata. Claude then reviews the plan as an architect and writes an ordered runbook."
        actions={<>
          <Button icon={<Download size={14} />} disabled={!plan} onClick={() => plan && download(plan)}>Export runbook</Button>
          <Button variant="primary" icon={<Sparkles size={14} />} loading={review.running} onClick={() => review.start("/runs/refresh", { sample_pct: pct })}>Architect review</Button>
        </>}
      />
      <ErrorNote message={base.error ?? review.error} />
      {review.run && review.run.status !== "done" && <RunLog run={review.run} />}

      <nav aria-label="Steps" className="mb-5 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-5">
        {STEPS.map((s, i) => (
          <button key={s.id} onClick={() => setStep(s.id)} aria-current={step === s.id ? "step" : undefined}
            className={cx("flex items-center gap-2.5 bg-surface px-3 py-2.5 text-left transition-colors", step === s.id ? "bg-accent-soft/60" : "hover:bg-sunken/50")}>
            <span className={cx("flex h-6 w-6 shrink-0 items-center justify-center rounded-full font-mono text-[12px]", step === s.id ? "bg-accent text-accent-ink" : "bg-sunken text-ink-2")}>{i + 1}</span>
            <span className="min-w-0"><span className="block text-[13px] font-medium">{s.label}</span><span className="block truncate text-[11.5px] text-ink-3">{s.hint}</span></span>
          </button>
        ))}
      </nav>

      {!plan ? <Section title="Loading"><Empty title="Reading org metadata…" /></Section> : (
        <div className="rise space-y-6" key={step}>
          {step === "inventory" && <Inventory plan={plan} />}
          {step === "checklist" && <Checklist plan={plan} done={done} toggle={toggle} />}
          {step === "seed" && <Seed plan={plan} pct={pct} setPct={setPct} />}
          {step === "mapping" && <Mapping plan={plan} />}
          {step === "reconcile" && <Reconcile plan={plan} />}
          {ai ? <Review review={ai} engine={review.run?.result?.engine} /> : (
            <p className="text-[13px] text-ink-3">Run <span className="font-medium text-ink-2">Architect review</span> for org-specific risks, mapping fixes and an ordered runbook.</p>
          )}
        </div>
      )}
    </>
  );
}

function Inventory({ plan }: { plan: Plan }) {
  const inv = plan.inventory, integ = inv.integrations;
  const total = inv.objects.reduce((s, o) => s + o.records, 0);
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <Section title={`Objects in ${inv.org_name}`} aside={<span className="tabular">{fmt.n(total)} records · {inv.data_storage_gb} GB data · {inv.file_storage_gb} GB files</span>}>
        <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <tbody className="divide-y divide-line">
            {[...inv.objects].sort((a, b) => b.records - a.records).map((o) => (
              <tr key={o.name}>
                <td className="px-4 py-2"><span className="font-medium">{o.label}</span> <span className="ml-1 hidden font-mono text-[12px] text-ink-3 sm:inline">{o.name}</span></td>
                <td className="px-2">{o.custom && <Badge>custom</Badge>}</td>
                <td className="w-[40%] px-4">
                  <div className="flex items-center gap-3">
                    <div className="hidden h-1.5 flex-1 rounded-full bg-sunken sm:block"><div className="h-full rounded-full bg-accent/70" style={{ width: `${Math.max(1, (Math.log10(o.records + 1) / 6.2) * 100)}%` }} /></div>
                    <span className="w-20 text-right font-mono tabular">{fmt.n(o.records)}</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </Section>
      <Section title="Things that point outside the org">
        <dl className="divide-y divide-line text-[13px]">
          {[
            ["Named Credentials", integ.named_credentials?.map((n: any) => n.name)],
            ["Scheduled jobs", integ.scheduled_jobs?.map((j: any) => j.name)],
            ["Outbound messages", integ.outbound_messages?.map((o: any) => o.name)],
            ["Connected apps", integ.connected_apps],
            ["Remote sites", integ.remote_site_settings],
          ].map(([k, v]) => (
            <div key={k as string} className="px-4 py-2.5">
              <dt className="text-[12px] font-medium text-ink-3">{k as string} · <span className="tabular">{(v as string[] | undefined)?.length ?? 0}</span></dt>
              <dd className="mt-1 flex flex-wrap gap-1">{(v as string[] | undefined)?.map((x) => <Field key={x} name={x} />) ?? <span className="text-ink-3">none</span>}</dd>
            </div>
          ))}
          <div className="px-4 py-2.5"><dt className="text-[12px] font-medium text-ink-3">Email deliverability in Production</dt><dd className="mt-0.5">{integ.email_deliverability}</dd></div>
        </dl>
      </Section>
    </div>
  );
}

function Checklist({ plan, done, toggle }: { plan: Plan; done: Set<string>; toggle: (id: string) => void }) {
  const finished = plan.checklist.filter((c) => done.has(c.id)).length;
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      <Section title="Post-refresh checklist" aside={<span className="tabular">{finished} / {plan.checklist.length} done</span>}>
        <div className="h-1 bg-sunken"><div className="h-full bg-accent transition-[width] duration-500" style={{ width: `${(100 * finished) / plan.checklist.length}%` }} /></div>
        <ul className="divide-y divide-line">
          {plan.checklist.map((c) => (
            <li key={c.id}>
              <label className="flex cursor-pointer gap-3 px-4 py-3 hover:bg-sunken/40">
                <input type="checkbox" checked={done.has(c.id)} onChange={() => toggle(c.id)} className="peer sr-only" />
                <span className={cx("mt-0.5 flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded border peer-focus-visible:ring-2 peer-focus-visible:ring-accent",
                  done.has(c.id) ? "border-accent bg-accent text-accent-ink" : "border-line-strong bg-surface")}>{done.has(c.id) && <Check size={12} strokeWidth={3} />}</span>
                <span className="min-w-0 flex-1">
                  <span className={cx("flex flex-wrap items-center gap-2 font-medium", done.has(c.id) && "text-ink-3 line-through")}>{c.title}</span>
                  <span className="mt-0.5 block text-ink-2">{c.detail}</span>
                  <span className="mt-1.5 flex items-center gap-2"><SeverityBadge severity={c.risk} /><span className="text-[12px] text-ink-3">{c.category}{c.automatable ? " · scriptable post-copy" : " · manual"}</span></span>
                </span>
              </label>
            </li>
          ))}
        </ul>
      </Section>
      <Section title="PII masking plan" aside={<span className="tabular">{plan.pii.length} fields</span>}>
        <table className="w-full text-[13px]">
          <tbody className="divide-y divide-line">
            {plan.pii.map((p) => (
              <tr key={p.object + p.field}>
                <td className="px-4 py-2">
                  <span className="block break-all font-mono text-[12px] text-ink">{p.object}.{p.field}</span>
                  <span className="block text-[12.5px] text-ink-2">{p.strategy}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
    </div>
  );
}

function Seed({ plan, pct, setPct }: { plan: Plan; pct: number; setPct: (n: number) => void }) {
  return (
    <Section title="Seed plan, in load order" aside={
      <label className="flex items-center gap-2">Sample of transactional data
        <select value={pct} onChange={(e) => setPct(+e.target.value)} className="h-7 rounded-md border border-line-strong bg-surface px-1.5 font-mono text-ink">
          {[0.5, 1, 2, 5, 10].map((n) => <option key={n} value={n}>{n}%</option>)}
        </select>
      </label>}>
      <ol className="divide-y divide-line">
        {plan.seed_plan.map((s) => (
          <li key={s.object} className="grid grid-cols-[32px_1fr_auto] items-center gap-3 px-4 py-2.5">
            <span className="font-mono text-[12px] text-ink-3 tabular">{s.step}</span>
            <span>
              <span className="font-medium">{s.object}</span> <span className="text-ink-3">· {s.kind}</span>
              {s.depends_on.length > 0 && <span className="mt-0.5 flex flex-wrap items-center gap-1 text-[12px] text-ink-3">after {s.depends_on.map((d) => <Field key={d} name={d} />)}</span>}
            </span>
            <span className="font-mono tabular">{fmt.n(s.records)}</span>
          </li>
        ))}
      </ol>
      <p className="border-t border-line px-4 py-2.5 text-[12.5px] text-ink-3">Parents load before children so lookups resolve; Production Ids are kept in an external-id field for traceability.</p>
    </Section>
  );
}

function Mapping({ plan }: { plan: Plan }) {
  const [gapsOnly, setGapsOnly] = useState(false);
  const rows = useMemo(() => plan.mapping.filter((m) => !gapsOnly || m.confidence < 90), [plan.mapping, gapsOnly]);
  const gaps = plan.mapping.filter((m) => !m.target_field).length;
  return (
    <Section title="Field mapping into Nonprofit Cloud" aside={<>
      <span className="tabular">{plan.mapping.length - gaps} mapped · {gaps} need a decision</span>
      <label className="ml-2 flex items-center gap-1.5"><input type="checkbox" checked={gapsOnly} onChange={(e) => setGapsOnly(e.target.checked)} className="accent-[var(--accent)]" />gaps only</label>
    </>}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-[13px]">
          <thead className="text-left text-[12px] text-ink-3"><tr className="border-b border-line"><th className="px-4 py-2 font-medium">Source</th><th className="px-4 py-2 font-medium">Target</th><th className="px-4 py-2 text-right font-medium">Confidence</th><th className="px-4 py-2 font-medium">Note</th></tr></thead>
          <tbody className="divide-y divide-line">
            {rows.map((m) => (
              <tr key={m.source_object + m.source_field} className={cx(!m.target_field && "bg-high-soft/40")}>
                <td className="px-4 py-2 font-mono text-[12px]">{m.source_object}.{m.source_field}</td>
                <td className="px-4 py-2 font-mono text-[12px]">{m.target_field ? `${m.target_object}.${m.target_field}` : <span className="text-high">no target</span>}</td>
                <td className="px-4 py-2 text-right font-mono tabular">{m.confidence ? `${m.confidence}%` : "—"}</td>
                <td className="px-4 py-2 text-ink-2">{m.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  );
}

function Reconcile({ plan }: { plan: Plan }) {
  const tone = { match: "ok", "minor gap": "warn", investigate: "danger", pending: "neutral" } as const;
  return (
    <Section title="Record reconciliation: source vs target">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-[13px]">
          <thead className="text-left text-[12px] text-ink-3"><tr className="border-b border-line"><th className="px-4 py-2 font-medium">Object</th><th className="px-4 py-2 text-right font-medium">Source</th><th className="px-4 py-2 text-right font-medium">Target</th><th className="px-4 py-2 text-right font-medium">Diff</th><th className="px-4 py-2 font-medium">Status</th></tr></thead>
          <tbody className="divide-y divide-line">
            {plan.reconciliation.map((r) => (
              <tr key={r.object}>
                <td className="px-4 py-2.5 font-medium">{r.object}</td>
                <td className="px-4 py-2.5 text-right font-mono tabular">{fmt.n(r.source)}</td>
                <td className="px-4 py-2.5 text-right font-mono tabular">{fmt.n(r.target)}</td>
                <td className={cx("px-4 py-2.5 text-right font-mono tabular", r.diff ? "text-critical" : "text-ink-3")}>{r.diff == null ? "—" : r.diff === 0 ? "0" : fmt.n(r.diff)}{r.pct != null && r.diff !== 0 && <span className="ml-1 text-ink-3">({r.pct}%)</span>}</td>
                <td className="px-4 py-2.5"><Badge tone={tone[r.status as keyof typeof tone] ?? "neutral"}>{r.status}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="border-t border-line px-4 py-2.5 text-[12.5px] text-ink-3">Gaps are re-checked by external id: failed rows are exported with their error and retried; nothing is marked done until every object matches or has a signed-off exception.</p>
    </Section>
  );
}

function Review({ review, engine }: { review: NonNullable<Plan["review"]>; engine?: string }) {
  return (
    <Section title="Architect review" aside={<EngineNote engine={engine} />} className="rise">
      <div className="grid gap-px bg-line lg:grid-cols-2">
        <div className="bg-surface px-4 py-4">
          <p className="max-w-[70ch] text-ink">{review.executive_summary}</p>
          {review.risks.length > 0 && <>
            <p className="mb-1 mt-4 text-[12px] font-medium text-ink-3">Risks</p>
            <ul className="space-y-1 text-ink-2">{review.risks.map((r, i) => <li key={i} className="flex gap-2"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-critical" />{r}</li>)}</ul>
          </>}
          {review.extra_checks.length > 0 && <>
            <p className="mb-1 mt-4 text-[12px] font-medium text-ink-3">Missing from the checklist</p>
            <ul className="space-y-2">{review.extra_checks.map((c, i) => <li key={i}><span className="flex items-center gap-2 font-medium"><SeverityBadge severity={c.risk} />{c.title}</span><span className="text-ink-2">{c.detail}</span></li>)}</ul>
          </>}
          {review.mapping_reviews.length > 0 && <>
            <p className="mb-1 mt-4 text-[12px] font-medium text-ink-3">Mapping decisions</p>
            <ul className="space-y-2">{review.mapping_reviews.map((m, i) => <li key={i}><span className="font-mono text-[12px]">{m.source_object}.{m.source_field}</span> → <span className="font-medium">{m.recommendation}</span><span className="block text-ink-2">{m.rationale}</span></li>)}</ul>
          </>}
        </div>
        <div className="bg-surface px-4 py-4">
          <p className="mb-2 text-[12px] font-medium text-ink-3">Runbook</p>
          <ol className="space-y-3">
            {review.runbook.map((s, i) => (
              <li key={i} className="grid grid-cols-[28px_1fr] gap-2">
                <span className="font-mono text-[12px] text-ink-3 tabular">{i + 1}</span>
                <span><Badge className="mr-1.5">{s.phase}</Badge>{s.action}<span className="mt-0.5 block text-[12.5px] text-ink-3">Verify: {s.verification}</span></span>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </Section>
  );
}

function download(plan: Plan) {
  const lines = [`# Refresh & migration runbook — ${plan.inventory.org_name}`, "", "## Post-refresh checklist", "",
    ...plan.checklist.map((c) => `- [ ] **${c.title}** (${c.risk}) — ${c.detail}`), "", "## PII masking", "",
    ...plan.pii.map((p) => `- ${p.object}.${p.field}: ${p.strategy}`), "", "## Seed order", "",
    ...plan.seed_plan.map((s) => `${s.step}. ${s.object} — ${s.kind}, ${s.records} records`), "", "## Field mapping", "",
    "| Source | Target | Confidence | Note |", "|---|---|---|---|",
    ...plan.mapping.map((m) => `| ${m.source_object}.${m.source_field} | ${m.target_field ? `${m.target_object}.${m.target_field}` : "—"} | ${m.confidence}% | ${m.note} |`)];
  if (plan.review) lines.push("", "## Architect runbook", "", ...plan.review.runbook.map((s, i) => `${i + 1}. [${s.phase}] ${s.action} — verify: ${s.verification}`));
  const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/markdown" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: "refresh-runbook.md" });
  a.click(); URL.revokeObjectURL(url);
}
