"use client";

import { ArrowRight, Check, Cloud, Database, Lock, Play, Scale, ShieldCheck, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Badge, Button, cx, Empty, ErrorNote, PageHeader, Rich, RunLog, SalesforceMark, Section, Tabs } from "@/components/ui";
import { fmt, useResource, useRun } from "@/lib/api";

interface Provider { id: string; label: string; kind: "native" | "external" | "private"; model: string; available: boolean; note: string; data_leaves_network: boolean; price_in: number; price_out: number }
interface Workflow { id: string; name: string; sobject: string; stakes: string; volume: string; latency: string; native: boolean; records: { id: string; label: string; sensitivity: string[] }[] }
interface Policy { id: string; when: string; route: string; fallback?: string; why: string }
interface Catalog { workflows: Workflow[]; policies: Policy[]; providers: Provider[] }
interface Result {
  workflow: string; record_id: string | null; policy: string; provider: string; model: string; masked: boolean; masked_values?: number;
  pii: { kind: string; class: string }[]; sent_prompt: string; answer: string; latency_ms: number; cost_usd: number;
  input_tokens: number; output_tokens: number; attempts: { provider: string; ok: boolean; reason?: string }[]; data_left_network: boolean; error?: string;
}
interface RouterRun { mode: "single" | "bulk" | "benchmark"; workflow: string; results: Result[] }
type Mode = "route" | "benchmark";

const ICON = { native: Database, external: Cloud, private: Lock };

export default function RouterPage() {
  const cat = useResource<Catalog>("/router");
  const [wfId, setWfId] = useState("case-summary");
  const [recId, setRecId] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("route");
  const { run, error, start, running } = useRun<RouterRun>();
  const result = run?.status === "done" ? run.result : null;

  const wf = cat.data?.workflows.find((w) => w.id === wfId);
  useEffect(() => { setRecId(wf?.records[0]?.id ?? null); }, [wfId, wf?.records]);
  const providers = useMemo(() => Object.fromEntries((cat.data?.providers ?? []).map((p) => [p.id, p])), [cat.data]);
  const matched = result?.mode !== "benchmark" ? result?.results[0]?.policy : null;
  const canBenchmark = wf && !wf.native && wf.volume !== "bulk";

  return (
    <>
      <PageHeader
        title="AI router"
        lede="Salesforce stays the system of record. Each request goes to the right place: Salesforce itself, Claude, ChatGPT or a private model inside your network, chosen by data sensitivity, stakes and cost. Sensitive values are masked before anything leaves the network."
        actions={<Button variant="primary" icon={mode === "benchmark" ? <Scale size={14} /> : <Play size={14} />} loading={running}
          disabled={!wf || (mode === "benchmark" && !canBenchmark)}
          onClick={() => start("/runs/router", { workflow: wfId, record_id: recId, mode })}>{mode === "benchmark" ? "Compare models" : "Route & run"}</Button>}
      />
      <ErrorNote message={error ?? cat.error} />

      <section aria-label="Providers" className="mb-6 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line md:grid-cols-5">
        {cat.data?.providers.map((p) => {
          const Icon = ICON[p.kind];
          return (
            <div key={p.id} className={cx("bg-surface px-3.5 py-3", !p.available && "bg-sunken/60")}>
              <p className="flex items-center gap-2 font-semibold text-heading">
                {p.kind === "native" ? <SalesforceMark size={22} /> : <Icon size={16} className={p.kind === "private" ? "text-ok" : "text-accent"} />}
                {p.label}
              </p>
              <p className="mt-0.5 truncate font-mono text-[12px] text-ink-2">{p.model}</p>
              <p className="mt-1.5 flex items-center gap-1.5 text-[12px]">
                <span className={cx("h-1.5 w-1.5 shrink-0 rounded-full", p.available ? "bg-ok" : "bg-line-strong")} />
                <span className={p.available ? "text-ink-2" : "text-ink-3"}>{p.available ? (p.data_leaves_network ? "Connected · external" : p.kind === "private" ? "Connected · in network" : "Built in") : p.note}</span>
              </p>
            </div>
          );
        })}
      </section>

      <div className="mb-6 grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <Section title="Request">
          <div className="space-y-4 px-4 py-4">
            <div>
              <p className="mb-1.5 text-[12px] font-medium text-ink-3">Workflow</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {cat.data?.workflows.map((w) => (
                  <button key={w.id} onClick={() => setWfId(w.id)} aria-pressed={wfId === w.id}
                    className={cx("rounded-md border px-3 py-2.5 text-left transition-colors", wfId === w.id ? "border-accent bg-accent-soft/70" : "border-line hover:border-line-strong")}>
                    <span className="block font-semibold text-heading">{w.name}</span>
                    <span className="block text-[12px] text-ink-3">{w.sobject} · {w.native ? "answered from data" : `${w.stakes} stakes · ${w.volume}`}</span>
                  </button>
                ))}
              </div>
            </div>
            {wf && !wf.native && wf.volume !== "bulk" && (
              <div>
                <p className="mb-1.5 text-[12px] font-medium text-ink-3">Salesforce record</p>
                <ul className="divide-y divide-line rounded-md border border-line">
                  {wf.records.slice(0, 6).map((r) => (
                    <li key={r.id}>
                      <label className={cx("flex cursor-pointer items-center gap-3 px-3 py-2", recId === r.id && "bg-accent-soft/50")}>
                        <input type="radio" name="rec" checked={recId === r.id} onChange={() => setRecId(r.id)} className="accent-[var(--accent)]" />
                        <span className="min-w-0 flex-1 truncate">{r.label}</span>
                        <span className="flex shrink-0 gap-1">{r.sensitivity.length ? r.sensitivity.map((s) => <Badge key={s} tone={s === "PII" ? "warn" : "danger"}>{s}</Badge>) : <Badge tone="ok">no PII</Badge>}</span>
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {wf?.volume === "bulk" && <p className="text-ink-2">Runs over all {wf.records.length} open cases; each one is routed by its own sensitivity.</p>}
            <div>
              <p className="mb-1.5 text-[12px] font-medium text-ink-3">Mode</p>
              <div role="radiogroup" className="inline-flex rounded-md border border-line-strong p-0.5">
                {([["route", "Route by policy"], ["benchmark", "Compare all models"]] as const).map(([m, label]) => (
                  <button key={m} role="radio" aria-checked={mode === m} onClick={() => setMode(m)}
                    className={cx("rounded px-3 py-1 text-[13px] font-medium", mode === m ? "bg-accent text-accent-ink" : "text-ink-2 hover:text-ink")}>{label}</button>
                ))}
              </div>
              {mode === "benchmark" && !canBenchmark && <p className="mt-1.5 text-[12.5px] text-ink-3">Pick a single-record workflow to compare models.</p>}
            </div>
          </div>
        </Section>

        <Section title="Routing policy" aside={<span>first match wins</span>}>
          <ol className="divide-y divide-line">
            {cat.data?.policies.map((p) => (
              <li key={p.id} className={cx("grid grid-cols-[36px_1fr] gap-2 px-4 py-2.5 transition-colors", matched === p.id && "bg-accent-soft/70")}>
                <span className={cx("mt-0.5 flex h-6 w-8 items-center justify-center rounded font-mono text-[11.5px] font-semibold", matched === p.id ? "bg-accent text-accent-ink" : "bg-sunken text-ink-2")}>{p.id}</span>
                <span className="min-w-0">
                  <span className="flex flex-wrap items-center gap-x-2 font-medium text-ink">{p.when}<ArrowRight size={13} className="text-ink-3" /><code className="font-mono text-[12.5px] text-accent">{p.route}</code></span>
                  <span className="block text-[12.5px] text-ink-3">{p.why}{p.fallback && <> · fallback <code className="font-mono">{p.fallback}</code></>}</span>
                </span>
              </li>
            ))}
          </ol>
        </Section>
      </div>

      {run && run.status !== "done" && <RunLog run={run} />}
      {result && (result.mode === "benchmark"
        ? <Benchmark results={result.results} providers={providers} />
        : <div className="space-y-6">{result.results.map((r, i) => <Trace key={i} r={r} providers={providers} compact={result.mode === "bulk"} />)}</div>)}
      {!result && !running && <p className="text-[13px] text-ink-3">Pick a workflow and record, then route it. The trace shows what was read from Salesforce, what was detected, which policy matched, what was actually sent, and what it cost.</p>}
    </>
  );
}

function Trace({ r, providers, compact }: { r: Result; providers: Record<string, Provider>; compact?: boolean }) {
  const [tab, setTab] = useState<"answer" | "sent">("answer");
  const p = providers[r.provider];
  const highlight = (s: string) => s.split(/(\[[A-Z_]+_\d+\])/g).map((part, i) =>
    /^\[[A-Z_]+_\d+\]$/.test(part) ? <mark key={i} className="rounded bg-high-soft px-0.5 text-high">{part}</mark> : part);
  return (
    <Section title={compact ? `${r.record_id ?? ""}` : "Decision trace"} className="rise" aside={<>
      <span className="font-mono tabular">{fmt.n(r.latency_ms)} ms</span><span>·</span>
      <span className="font-mono tabular">${r.cost_usd.toFixed(4)}</span><span>·</span>
      <span className="font-mono tabular">{fmt.n(r.input_tokens)} / {fmt.n(r.output_tokens)} tok</span>
    </>}>
      <ol className="grid gap-px bg-line md:grid-cols-4">
        <Step n={1} title="Read from Salesforce">{r.record_id ? <code className="font-mono text-[12px]">{r.record_id}</code> : "Aggregate query"}</Step>
        <Step n={2} title="Trust scan">
          {r.pii.length === 0 ? <Badge tone="ok">nothing sensitive</Badge> : <span className="flex flex-wrap gap-1">{[...new Set(r.pii.map((x) => `${x.class} · ${x.kind}`))].map((x) => <Badge key={x} tone={x.startsWith("PII") ? "warn" : "danger"}>{x}</Badge>)}</span>}
        </Step>
        <Step n={3} title={`Policy ${r.policy}`}>
          <span className="flex flex-wrap items-center gap-1.5">
            {r.attempts.map((a, i) => (
              <span key={i} className="inline-flex items-center gap-1" title={a.reason}>
                {i > 0 && <ArrowRight size={12} className="text-ink-3" />}
                <Badge tone={a.ok ? "accent" : "neutral"} className={a.ok ? "" : "line-through"}>{a.ok ? <Check size={11} /> : <X size={11} />}{providers[a.provider]?.label ?? a.provider}</Badge>
              </span>
            ))}
          </span>
          {r.attempts.some((a) => !a.ok) && <span className="mt-1 block text-[12px] text-ink-3">Skipped: {r.attempts.filter((a) => !a.ok).map((a) => `${providers[a.provider]?.label}: ${a.reason}`).join("; ")}</span>}
        </Step>
        <Step n={4} title="Data exposure">
          {r.data_left_network
            ? <span className="flex items-center gap-1.5"><ShieldCheck size={15} className="text-accent" />{r.masked ? `${r.masked_values} values masked before sending` : "Sent as is (nothing sensitive)"}</span>
            : <span className="flex items-center gap-1.5"><Lock size={15} className="text-ok" />Stayed inside your network</span>}
        </Step>
      </ol>
      <Tabs value={tab} onChange={setTab} items={[{ id: "answer", label: `Answer · ${p?.label ?? r.provider}` }, { id: "sent", label: r.provider === "native" ? "Query" : r.masked ? "What the model saw (masked)" : "What the model saw" }]} />
      {tab === "answer"
        ? <div className="max-w-[80ch] px-4 py-4 leading-relaxed text-ink"><Rich text={r.answer} className="space-y-1" /><p className="mt-3 font-mono text-[11.5px] text-ink-3">{r.model}</p></div>
        : <pre className="max-h-[340px] overflow-auto whitespace-pre-wrap px-4 py-4 font-mono text-[12.5px] leading-[1.6] text-ink-2">{highlight(r.sent_prompt)}</pre>}
    </Section>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="bg-surface px-4 py-3">
      <p className="mb-1.5 flex items-center gap-2 text-[12px] font-medium text-ink-3"><span className="flex h-5 w-5 items-center justify-center rounded-full bg-sunken font-mono text-[11px] text-ink-2">{n}</span>{title}</p>
      <div className="text-[13px] text-ink">{children}</div>
    </li>
  );
}

function Benchmark({ results, providers }: { results: Result[]; providers: Record<string, Provider> }) {
  const ok = results.filter((r) => !r.error);
  const fastest = Math.min(...ok.map((r) => r.latency_ms));
  const cheapest = Math.min(...ok.map((r) => r.cost_usd));
  const skipped = Object.values(providers).filter((p) => p.kind !== "native" && !p.available);
  return (
    <Section title="Model comparison on the same Salesforce record" className="rise" aside={skipped.length > 0 && <span>not connected: {skipped.map((p) => p.label).join(", ")}</span>}>
      <div className="grid gap-px bg-line" style={{ gridTemplateColumns: `repeat(${Math.max(1, ok.length)}, minmax(0, 1fr))` }}>
        {ok.map((r) => {
          const p = providers[r.provider];
          return (
            <div key={r.provider} className="flex min-w-0 flex-col bg-surface">
              <div className="border-b border-line px-4 py-3">
                <p className="flex items-center gap-2 font-semibold text-heading">{p?.kind === "private" ? <Lock size={15} className="text-ok" /> : <Cloud size={15} className="text-accent" />}{p?.label}</p>
                <p className="font-mono text-[12px] text-ink-3">{r.model}</p>
                <dl className="mt-2 grid grid-cols-3 gap-2 text-[12px]">
                  <div><dt className="text-ink-3">Latency</dt><dd className={cx("font-mono tabular", r.latency_ms === fastest && "font-semibold text-ok")}>{(r.latency_ms / 1000).toFixed(1)}s</dd></div>
                  <div><dt className="text-ink-3">Cost</dt><dd className={cx("font-mono tabular", r.cost_usd === cheapest && "font-semibold text-ok")}>${r.cost_usd.toFixed(4)}</dd></div>
                  <div><dt className="text-ink-3">Data</dt><dd>{r.data_left_network ? (r.masked ? "masked" : "external") : "in network"}</dd></div>
                </dl>
              </div>
              <div className="px-4 py-3 text-[13px] leading-relaxed"><Rich text={r.answer} className="space-y-1" /></div>
            </div>
          );
        })}
        {ok.length === 0 && <Empty title="No connected models to compare" />}
      </div>
    </Section>
  );
}
