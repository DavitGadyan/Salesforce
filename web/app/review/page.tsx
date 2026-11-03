"use client";

import { Play, ShieldAlert, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Badge, Button, cx, Empty, EngineNote, ErrorNote, PageHeader, RunLog, Section, SeverityBadge, Tabs } from "@/components/ui";
import { useResource, useRun, type Finding, type ReviewResult, type Severity } from "@/lib/api";

interface Sample { filename: string; code: string }
type Tab = "findings" | "diff" | "tests";

export default function ReviewPage() {
  const samples = useResource<Sample[]>("/samples");
  const [filename, setFilename] = useState("");
  const [code, setCode] = useState("");
  const [active, setActive] = useState<number | null>(null);
  const [tab, setTab] = useState<Tab>("findings");
  const [reviewed, setReviewed] = useState("");
  const { run, error, start, running } = useRun<ReviewResult>();
  const result = run?.status === "done" ? run.result : null;

  useEffect(() => {
    if (samples.data && !code) { setFilename(samples.data[0].filename); setCode(samples.data[0].code); }
  }, [samples.data, code]);

  const go = () => { setActive(null); setTab("findings"); setReviewed(code); start("/runs/code-review", { code, filename }); };

  const counts = useMemo(() => {
    const c: Record<Severity, number> = { critical: 0, high: 0, medium: 0, low: 0 };
    result?.findings.filter((f) => f.confirmed).forEach((f) => c[f.severity]++);
    return c;
  }, [result]);

  return (
    <>
      <PageHeader
        title="Code review"
        lede="Paste Apex or Flow metadata, or open a file from the library. A static analyser runs first; Claude confirms each finding, adds what rules can't see, and rewrites the code with a bulk test."
        actions={<Button variant="primary" icon={<Play size={14} />} loading={running} onClick={go} disabled={code.trim().length < 10}>Review code</Button>}
      />
      <ErrorNote message={error ?? samples.error} />
      <RunLog run={running || run?.status === "failed" ? run : null} />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Section title="Source" aside={
          <select aria-label="File" value={filename} onChange={(e) => {
            const s = samples.data?.find((x) => x.filename === e.target.value);
            setFilename(e.target.value); if (s) setCode(s.code);
          }} className="h-7 rounded-md border border-line-strong bg-surface px-2 font-mono text-[12px] text-ink">
            {samples.data?.map((s) => <option key={s.filename} value={s.filename}>{s.filename}</option>)}
            {filename && !samples.data?.some((s) => s.filename === filename) && <option value={filename}>{filename}</option>}
          </select>
        }>
          {result && reviewed === code ? (
            <CodeView code={code} findings={result.findings} active={active} onEdit={() => setReviewed("")} />
          ) : (
            <textarea value={code} onChange={(e) => { setCode(e.target.value); if (!samples.data?.some((s) => s.code === e.target.value)) setFilename("pasted.cls"); }}
              spellCheck={false} aria-label="Apex or Flow source"
              className="block h-[520px] w-full resize-y rounded-b-lg bg-surface p-4 font-mono text-[12.5px] leading-[1.6] text-ink outline-none" />
          )}
        </Section>

        <Section title="Review" aside={result && <EngineNote engine={result.engine} />}>
          {!result ? (
            <Empty title={running ? "Reviewing…" : "No review yet"}>
              {running ? "Static analysis finishes instantly; Claude's review takes 20–60 seconds." : "Run a review to see findings ranked by severity, each with the line, the rule and the fix."}
            </Empty>
          ) : (
            <div className="rise">
              <div className={cx("flex items-start gap-3 border-b border-line px-4 py-3.5", result.production_ready ? "bg-ok-soft/50" : "bg-critical-soft/40")}>
                {result.production_ready ? <ShieldCheck size={20} className="mt-0.5 shrink-0 text-ok" /> : <ShieldAlert size={20} className="mt-0.5 shrink-0 text-critical" />}
                <div className="min-w-0">
                  <p className="font-semibold">{result.production_ready ? "Ready for production" : "Not ready for production"}</p>
                  <p className="mt-0.5 text-ink-2">{result.summary}</p>
                  <p className="mt-2 flex flex-wrap gap-1.5">
                    {(Object.keys(counts) as Severity[]).filter((k) => counts[k]).map((k) => (
                      <span key={k} className="inline-flex items-center gap-1"><SeverityBadge severity={k} /><span className="font-mono text-[12px] tabular">{counts[k]}</span></span>
                    ))}
                  </p>
                </div>
              </div>
              <Tabs value={tab} onChange={setTab} items={[
                { id: "findings", label: `Findings (${result.findings.length})` },
                { id: "diff", label: result.corrected_code ? "Corrected code" : "Corrected code · Claude" },
                { id: "tests", label: result.test_class ? "Test class" : "Test class · Claude" },
              ]} />
              {tab === "findings" && (
                <ol className="max-h-[560px] divide-y divide-line overflow-y-auto">
                  {result.findings.map((f, i) => (
                    <li key={i}>
                      <button onClick={() => setActive(f.line)} className={cx("block w-full px-4 py-3 text-left hover:bg-sunken/40", active === f.line && "bg-accent-soft/50", !f.confirmed && "opacity-60")}>
                        <span className="flex flex-wrap items-center gap-2">
                          <SeverityBadge severity={f.severity} />
                          <code className="font-mono text-[12px] font-medium text-ink">{f.rule}</code>
                          <span className="font-mono text-[12px] text-ink-3">line {f.line}</span>
                          {f.source === "claude" && <Badge tone="accent">found by Claude</Badge>}
                          {!f.confirmed && <Badge>false positive</Badge>}
                        </span>
                        <span className="mt-1 block text-ink">{f.message}</span>
                        <span className="mt-1 block text-ink-2"><span className="font-medium text-ok">Fix: </span>{f.fix}</span>
                      </button>
                    </li>
                  ))}
                </ol>
              )}
              {tab === "diff" && (result.corrected_code
                ? <Diff before={reviewed} after={result.corrected_code} />
                : <Empty title="Corrected code comes from the Claude engine">With Claude enabled, the code is rewritten so every confirmed finding is fixed.</Empty>)}
              {tab === "tests" && (result.test_class
                ? <pre className="max-h-[560px] overflow-auto p-4 font-mono text-[12.5px] leading-[1.6]">{result.test_class}</pre>
                : <Empty title={result.engine === "claude" ? "No separate test class" : "Test generation needs Claude"}>
                    {result.engine === "claude" ? "The input was a test class, so the improved test is in Corrected code." : "With Claude enabled, a bulk (200-record) test class with real assertions is generated."}
                  </Empty>)}
            </div>
          )}
        </Section>
      </div>
    </>
  );
}

function CodeView({ code, findings, active, onEdit }: { code: string; findings: Finding[]; active: number | null; onEdit: () => void }) {
  const byLine = useMemo(() => {
    const m = new Map<number, Finding[]>();
    findings.filter((f) => f.confirmed).forEach((f) => m.set(f.line, [...(m.get(f.line) ?? []), f]));
    return m;
  }, [findings]);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { if (active) ref.current?.querySelector(`[data-line="${active}"]`)?.scrollIntoView({ block: "center", behavior: "smooth" }); }, [active]);
  const tone: Record<Severity, string> = { critical: "bg-critical", high: "bg-high", medium: "bg-medium", low: "bg-low" };

  return (
    <div>
      <div ref={ref} className="h-[520px] overflow-auto py-2 font-mono text-[12.5px] leading-[1.6]">
        {code.split("\n").map((line, i) => {
          const fs = byLine.get(i + 1);
          return (
            <div key={i} data-line={i + 1} className={cx("flex", fs && "bg-critical-soft/40", active === i + 1 && "bg-accent-soft")}>
              <span className="w-11 shrink-0 select-none pr-3 text-right text-ink-3 tabular">{i + 1}</span>
              <span className="w-1.5 shrink-0">{fs && <span className={cx("block h-full w-[3px] rounded-full", tone[fs[0].severity])} />}</span>
              <span className="whitespace-pre pl-2 pr-4">{line || " "}</span>
            </div>
          );
        })}
      </div>
      <div className="border-t border-line px-4 py-2"><Button variant="ghost" onClick={onEdit}>Edit source</Button></div>
    </div>
  );
}

/** Minimal LCS line diff. */
function Diff({ before, after }: { before: string; after: string }) {
  const rows = useMemo(() => {
    const a = before.split("\n"), b = after.split("\n");
    const n = a.length, m = b.length;
    const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
    for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
      dp[i][j] = a[i].trim() === b[j].trim() ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    const out: { t: " " | "-" | "+"; s: string }[] = [];
    let i = 0, j = 0;
    while (i < n && j < m) {
      if (a[i].trim() === b[j].trim()) { out.push({ t: " ", s: b[j] }); i++; j++; }
      else if (dp[i + 1][j] >= dp[i][j + 1]) out.push({ t: "-", s: a[i++] });
      else out.push({ t: "+", s: b[j++] });
    }
    while (i < n) out.push({ t: "-", s: a[i++] });
    while (j < m) out.push({ t: "+", s: b[j++] });
    return out;
  }, [before, after]);
  return (
    <div className="max-h-[560px] overflow-auto py-2 font-mono text-[12.5px] leading-[1.6]">
      {rows.map((r, k) => (
        <div key={k} className={cx("flex whitespace-pre px-4", r.t === "+" && "bg-ok-soft", r.t === "-" && "bg-critical-soft/60 text-ink-2 line-through decoration-critical/40")}>
          <span className={cx("w-4 shrink-0 select-none", r.t === "+" ? "text-ok" : r.t === "-" ? "text-critical" : "text-ink-3")}>{r.t}</span>
          <span>{r.s || " "}</span>
        </div>
      ))}
    </div>
  );
}
