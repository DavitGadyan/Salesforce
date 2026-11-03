"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge, cx, ErrorNote, PageHeader, Section } from "@/components/ui";
import { useResource } from "@/lib/api";

interface Job { title: string; client: string; spend: string; hires_total: number; interviews: number; hires: number; budget: string; tier: number; pattern: number | null; why: string }
interface Insights { captured: string; jobs: Job[]; patterns: { id: number; name: string; module: string; demand: string; needs: string[] }[]; cross_cutting: string[]; filter_rule: string }

const HREF: Record<string, string> = { refresh: "/refresh", revenue: "/revenue", "code-review": "/review" };
const TIER = { 1: ["Tier 1", "accent"], 2: ["Tier 2", "accent"], 3: ["Tier 3", "neutral"], 0: ["Excluded", "neutral"] } as const;

export default function InsightsPage() {
  const { data, error } = useResource<Insights>("/insights");
  const [showExcluded, setShowExcluded] = useState(false);
  const jobs = data?.jobs.filter((j) => showExcluded || j.tier > 0) ?? [];

  return (
    <>
      <PageHeader
        title="Why these three automations"
        lede={<>14 Upwork job posts about Salesforce automation, captured {data?.captured ?? "…"}. Ghost posts (no spend, no interviews, recruiters) were dropped; the clients who actually interview, hire and spend all ask for the same three things.</>}
      />
      <ErrorNote message={error} />
      {data && (
        <div className="space-y-8">
          <ol className="grid gap-px overflow-hidden rounded-lg border border-line bg-line lg:grid-cols-3">
            {data.patterns.map((p) => (
              <li key={p.id} className="flex flex-col bg-surface px-5 py-5">
                <h2 className="text-[16px] font-semibold leading-snug tracking-[-0.01em]">{p.name}</h2>
                <p className="mt-2 text-ink-2">{p.demand}</p>
                <ul className="mt-4 flex-1 space-y-1.5 text-[13px]">
                  {p.needs.map((n) => <li key={n} className="flex gap-2"><span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-accent" />{n}</li>)}
                </ul>
                <Link href={HREF[p.module]} className="mt-5 text-[13px] font-medium text-accent underline">Open the module</Link>
              </li>
            ))}
          </ol>

          <Section title="Every serious client also asked for">
            <ul className="grid gap-x-8 gap-y-2 px-5 py-4 md:grid-cols-2">
              {data.cross_cutting.map((c) => <li key={c} className="flex gap-2"><span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-ink-3" />{c}</li>)}
            </ul>
          </Section>

          <Section title="The job posts" aside={
            <label className="flex items-center gap-1.5"><input type="checkbox" checked={showExcluded} onChange={(e) => setShowExcluded(e.target.checked)} className="accent-[var(--accent)]" />show excluded</label>}>
            <p className="max-w-[80ch] border-b border-line px-4 py-3 text-[13px] text-ink-2">{data.filter_rule}</p>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px] text-[13px]">
                <thead className="whitespace-nowrap text-left text-[12px] text-ink-3"><tr className="border-b border-line">
                  <th className="px-4 py-2 font-medium">Post</th><th className="px-2 py-2 font-medium">Client spend</th>
                  <th className="px-2 py-2 text-right font-medium">Interviews</th><th className="px-2 py-2 text-right font-medium">Hires</th>
                  <th className="px-2 py-2 font-medium">Verdict</th><th className="px-4 py-2 font-medium">Pattern</th></tr></thead>
                <tbody className="divide-y divide-line">
                  {jobs.map((j) => (
                    <tr key={j.title} className={cx("align-top", j.tier === 0 && "text-ink-3")}>
                      <td className="px-4 py-2.5"><p className="font-medium text-ink">{j.title}</p><p className="text-[12px] text-ink-3">{j.client} · {j.why}</p></td>
                      <td className="whitespace-nowrap px-2 py-2.5 font-mono tabular">{j.spend}</td>
                      <td className="px-2 py-2.5 text-right font-mono tabular">{j.interviews}</td>
                      <td className="px-2 py-2.5 text-right font-mono tabular">{j.hires}</td>
                      <td className="px-2 py-2.5"><Badge tone={TIER[j.tier as 0 | 1 | 2 | 3][1]}>{TIER[j.tier as 0 | 1 | 2 | 3][0]}</Badge></td>
                      <td className="px-4 py-2.5 text-ink-2">{j.pattern ? data.patterns[j.pattern - 1].name : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        </div>
      )}
    </>
  );
}
