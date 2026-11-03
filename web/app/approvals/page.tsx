"use client";

import { Check, X } from "lucide-react";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useStatus } from "@/components/shell";
import { Badge, Button, Empty, ErrorNote, Field, PageHeader, Section, Tabs } from "@/components/ui";
import { api, fmt, MODULES, useResource, type Approval, type AuditEvent } from "@/lib/api";

type Tab = "pending" | "decided" | "audit";
const KIND = { send_email: "Send email", update_record: "Update record", merge_records: "Merge duplicates" };

export default function Page() {
  return <Suspense><Approvals /></Suspense>;
}

function Approvals() {
  const params = useSearchParams();
  const [tab, setTab] = useState<Tab>((params.get("tab") as Tab) ?? "pending");
  const approvals = useResource<Approval[]>("/approvals");
  const audit = useResource<AuditEvent[]>("/audit?limit=300");
  const { refresh } = useStatus();
  const [error, setError] = useState<string | null>(null);

  const pending = approvals.data?.filter((a) => a.status === "pending") ?? [];
  const decided = approvals.data?.filter((a) => a.status !== "pending") ?? [];

  const decide = async (a: Approval, decision: "approve" | "reject", payload?: Record<string, any>) => {
    setError(null);
    try {
      await api(`/approvals/${a.id}/decide`, { method: "POST", json: { decision, payload } });
      approvals.setData((list) => list?.map((x) => (x.id === a.id ? { ...x, status: decision === "approve" ? "approved" : "rejected", decided_at: new Date().toISOString(), payload: payload ?? x.payload } : x)) ?? null);
      audit.reload(); refresh();
    } catch (e) { setError((e as Error).message); }
  };

  return (
    <>
      <PageHeader
        title="Approvals & audit"
        lede="Agents never write to Salesforce or send anything on their own. Each proposed action lands here with its evidence; you edit, approve or reject it, and every step is logged."
      />
      <ErrorNote message={error ?? approvals.error} />
      <Section title={tab === "audit" ? "Audit log" : "Queue"} aside={tab === "audit" && <span className="tabular">{audit.data?.length ?? 0} events</span>}>
        <Tabs value={tab} onChange={setTab} items={[
          { id: "pending", label: `Waiting · ${pending.length}` },
          { id: "decided", label: `Decided · ${decided.length}` },
          { id: "audit", label: "Audit log" },
        ]} />
        {tab === "pending" && (pending.length === 0
          ? <Empty title="Nothing is waiting">Run the Revenue agent or Find duplicates; their proposals appear here.</Empty>
          : <ul className="divide-y divide-line">{pending.map((a) => <PendingItem key={a.id} a={a} onDecide={decide} />)}</ul>)}
        {tab === "decided" && (decided.length === 0 ? <Empty title="No decisions yet" /> : (
          <ul className="divide-y divide-line">
            {decided.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
                <Badge tone={a.status === "approved" ? "ok" : "neutral"}>{a.status}</Badge>
                <span className="min-w-0 flex-1 truncate">{a.title}</span>
                <span className="text-[12px] text-ink-3">{KIND[a.kind]} · {a.decided_at && fmt.dateTime(a.decided_at)}</span>
              </li>
            ))}
          </ul>
        ))}
        {tab === "audit" && <AuditTable events={audit.data ?? []} />}
      </Section>
    </>
  );
}

function PendingItem({ a, onDecide }: { a: Approval; onDecide: (a: Approval, d: "approve" | "reject", p?: Record<string, any>) => Promise<void> }) {
  const [subject, setSubject] = useState(a.payload.subject ?? "");
  const [body, setBody] = useState(a.payload.body ?? "");
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  useEffect(() => { setSubject(a.payload.subject ?? ""); setBody(a.payload.body ?? ""); }, [a.payload]);
  const edited = a.kind === "send_email" && (subject !== a.payload.subject || body !== a.payload.body);
  const act = async (d: "approve" | "reject") => {
    setBusy(d);
    await onDecide(a, d, edited ? { ...a.payload, subject, body } : undefined);
    setBusy(null);
  };

  return (
    <li className="grid gap-4 px-4 py-4 lg:grid-cols-[1fr_auto]">
      <div className="min-w-0">
        <p className="flex flex-wrap items-center gap-2">
          <Badge tone="accent">{KIND[a.kind]}</Badge>
          <span className="font-medium">{a.title}</span>
          <span className="text-[12px] text-ink-3">{fmt.dateTime(a.created_at)}</span>
        </p>
        <p className="mt-1 text-ink-2">{a.rationale}</p>

        {a.kind === "send_email" && (
          <div className="mt-3 max-w-[72ch] rounded-md border border-line">
            <p className="border-b border-line px-3 py-1.5 text-[12px] text-ink-3">To <span className="font-mono">{a.payload.to}</span></p>
            <input value={subject} onChange={(e) => setSubject(e.target.value)} aria-label="Subject" className="w-full border-b border-line px-3 py-2 font-medium outline-none" />
            <textarea value={body} onChange={(e) => setBody(e.target.value)} aria-label="Body" rows={Math.min(10, body.split("\n").length + 1)} className="block w-full resize-y px-3 py-2 leading-relaxed outline-none" />
            {a.payload.facts_used?.length > 0 && (
              <p className="flex flex-wrap items-center gap-1 border-t border-line px-3 py-2 text-[12px] text-ink-3">
                Verified against CRM: {a.payload.facts_used.map((f: any) => <span key={f.field + f.value} className="inline-flex items-center gap-1"><Field name={f.field} /><span className="text-ink-2">{f.value}</span></span>)}
              </p>
            )}
          </div>
        )}

        {a.kind === "update_record" && (
          <table className="mt-3 text-[13px]">
            <tbody>
              {Object.entries(a.payload.fields).map(([k, v]) => (
                <tr key={k}><td className="py-0.5 pr-4"><Field name={k} /></td><td className="pr-3 text-ink-3 line-through">{a.payload.before?.[k] ?? "empty"}</td><td className="font-medium text-ok">{String(v)}</td></tr>
              ))}
            </tbody>
          </table>
        )}

        {a.kind === "merge_records" && (
          <div className="mt-3 overflow-x-auto">
            <table className="min-w-[560px] text-[13px]">
              <thead className="text-left text-[12px] text-ink-3"><tr><th className="py-1 pr-4 font-medium" /><th className="pr-4 font-medium">Name</th><th className="pr-4 font-medium">Email</th><th className="pr-4 font-medium">Company</th><th className="font-medium">Created</th></tr></thead>
              <tbody>
                {a.payload.records.map((r: any) => (
                  <tr key={r.Id}>
                    <td className="py-0.5 pr-4">{r.Id === a.payload.survivor_id ? <Badge tone="ok">keep</Badge> : <Badge>merge in</Badge>}</td>
                    <td className="pr-4">{r.FirstName} {r.LastName}</td><td className="pr-4 font-mono text-[12px]">{r.Email ?? "—"}</td>
                    <td className="pr-4">{r.Company}</td><td className="font-mono text-[12px] tabular">{r.CreatedDate?.slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-1 text-[12px] text-ink-3">Match confidence <span className="font-mono tabular">{a.payload.confidence}%</span></p>
          </div>
        )}
      </div>
      <div className="flex items-start gap-2 lg:flex-col lg:items-stretch">
        <Button variant="primary" icon={<Check size={14} />} loading={busy === "approve"} disabled={!!busy} onClick={() => act("approve")}>{edited ? "Approve edited" : "Approve"}</Button>
        <Button variant="danger" icon={<X size={14} />} loading={busy === "reject"} disabled={!!busy} onClick={() => act("reject")}>Reject</Button>
      </div>
    </li>
  );
}

function AuditTable({ events }: { events: AuditEvent[] }) {
  if (events.length === 0) return <Empty title="The audit log is empty">Every run, model call, tool call and decision is recorded here.</Empty>;
  return (
    <div className="max-h-[680px] overflow-auto">
      <table className="w-full min-w-[720px] text-[13px]">
        <thead className="sticky top-0 bg-surface text-left text-[12px] text-ink-3 shadow-[0_1px_0_var(--line)]">
          <tr><th className="px-4 py-2 font-medium">Time</th><th className="px-2 py-2 font-medium">Actor</th><th className="px-2 py-2 font-medium">Event</th><th className="px-2 py-2 font-medium">Summary</th><th className="px-4 py-2 text-right font-medium">Tokens in / out</th></tr>
        </thead>
        <tbody className="divide-y divide-line">
          {events.map((e) => (
            <tr key={e.id} className="align-top">
              <td className="whitespace-nowrap px-4 py-2 font-mono text-[12px] text-ink-3 tabular">{fmt.dateTime(e.at)}</td>
              <td className="whitespace-nowrap px-2 py-2">{MODULES[e.actor] ?? e.actor}</td>
              <td className="whitespace-nowrap px-2 py-2"><Badge tone={e.kind.includes("fail") || e.kind === "guardrail" ? "danger" : e.kind.startsWith("approval") ? "ok" : "neutral"}>{e.kind.replaceAll("_", " ")}</Badge></td>
              <td className="px-2 py-2">{e.summary}{e.model && <span className="ml-1.5 font-mono text-[11.5px] text-ink-3">{e.model}</span>}</td>
              <td className="whitespace-nowrap px-4 py-2 text-right font-mono text-[12px] tabular">{e.input_tokens != null ? `${fmt.n(e.input_tokens)} / ${fmt.n(e.output_tokens)}` : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
