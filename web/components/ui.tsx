"use client";

import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import type { Run, Severity } from "@/lib/api";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

/** Salesforce logo (from salesforce.com), used only to mark the connected org. */
export function SalesforceMark({ size = 20, className }: { size?: number; className?: string }) {
  // eslint-disable-next-line @next/next/no-img-element
  return <img src="/salesforce.svg" alt="Salesforce" width={size} height={Math.round(size * 0.7)} className={className} />;
}

type Variant = "primary" | "secondary" | "ghost" | "danger";

export function Button({ variant = "secondary", loading, icon, children, className, disabled, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean; icon?: ReactNode }) {
  const styles: Record<Variant, string> = {
    primary: "bg-accent text-accent-ink hover:bg-accent-hover",
    secondary: "bg-surface text-accent border border-line-strong hover:border-accent hover:bg-accent-soft",
    ghost: "text-ink-2 hover:bg-sunken hover:text-ink",
    danger: "bg-surface text-critical border border-line-strong hover:border-critical hover:bg-critical-soft",
  };
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cx("inline-flex h-9 items-center gap-1.5 rounded px-3.5 text-[14px] font-semibold transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-50", styles[variant], className)}
    >
      {loading ? <Loader2 size={14} className="animate-spin" /> : icon}
      {children}
    </button>
  );
}

const SEV: Record<Severity, string> = {
  critical: "bg-critical-soft text-critical",
  high: "bg-high-soft text-high",
  medium: "bg-medium-soft text-medium",
  low: "bg-low-soft text-low",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <span className={cx("inline-flex rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide", SEV[severity])}>{severity}</span>;
}

export function Badge({ children, tone = "neutral", className }: { children: ReactNode; tone?: "neutral" | "accent" | "ok" | "warn" | "danger"; className?: string }) {
  const tones = {
    neutral: "bg-sunken text-ink-2",
    accent: "bg-accent-soft text-accent",
    ok: "bg-ok-soft text-ok",
    warn: "bg-high-soft text-high",
    danger: "bg-critical-soft text-critical",
  };
  return <span className={cx("inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[12px] font-medium", tones[tone], className)}>{children}</span>;
}

export function Tier({ tier }: { tier: "A" | "B" | "C" }) {
  const t = { A: "bg-heading text-accent-ink", B: "bg-accent-soft text-accent", C: "bg-sunken text-ink-3" }[tier];
  return <span className={cx("inline-flex h-6 w-6 items-center justify-center rounded font-mono text-[12px] font-semibold", t)} aria-label={`Tier ${tier}`}>{tier}</span>;
}

export function Field({ name }: { name: string }) {
  return <code className="rounded border border-line bg-sunken px-1 py-px font-mono text-[11.5px] text-ink-2">{name}</code>;
}

export function PageHeader({ title, lede, actions }: { title: string; lede: ReactNode; actions?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-col gap-4 border-b border-line pb-5 md:flex-row md:items-end md:justify-between">
      <div className="max-w-[68ch]">
        <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.015em]">{title}</h1>
        <p className="mt-1.5 text-ink-2">{lede}</p>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function Section({ title, aside, children, className }: { title: string; aside?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx("min-w-0 rounded-lg border border-line bg-surface", className)}>
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
        <h2 className="text-[14px] font-semibold">{title}</h2>
        {aside && <div className="flex items-center gap-2 text-[12px] text-ink-3">{aside}</div>}
      </div>
      {children}
    </section>
  );
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-2 px-5 py-8">
      <p className="font-medium text-ink">{title}</p>
      {children && <p className="max-w-[60ch] text-ink-2">{children}</p>}
      {action}
    </div>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div role="alert" className="mb-4 flex items-start gap-2 rounded-md border border-critical/30 bg-critical-soft px-3 py-2 text-critical">
      <AlertTriangle size={16} className="mt-0.5 shrink-0" />
      <span>{message}</span>
    </div>
  );
}

export function EngineNote({ engine }: { engine?: string }) {
  if (!engine) return null;
  return engine === "claude"
    ? <Badge tone="accent">Claude agent</Badge>
    : <Badge tone="neutral">Rules engine</Badge>;
}

export function RunLog({ run }: { run: Run | null }) {
  if (!run) return null;
  const last = run.progress.slice(-6);
  return (
    <div className="rise mb-4 rounded-lg border border-line bg-surface px-4 py-3" aria-live="polite">
      <div className="flex items-center gap-2 text-[13px] font-medium">
        {run.status === "running" && <span className="pulse-dot h-2 w-2 rounded-full bg-accent" />}
        {run.status === "done" && <CheckCircle2 size={15} className="shrink-0 text-ok" />}
        {run.status === "failed" && <AlertTriangle size={15} className="text-critical" />}
        <span>{run.status === "running" ? "Working…" : run.status === "done" ? "Finished" : "Failed"}</span>
        <span className="font-mono text-[11.5px] font-normal text-ink-3">run {run.id}</span>
      </div>
      {run.error && <p className="mt-1 text-critical">{run.error}</p>}
      {last.length > 0 && (
        <ol className="mt-2 space-y-0.5 font-mono text-[12px] text-ink-2">
          {last.map((p, i) => <li key={i} className="truncate">{p.message}</li>)}
        </ol>
      )}
    </div>
  );
}

export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (v: T) => void; items: { id: T; label: ReactNode }[] }) {
  return (
    <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-line px-2">
      {items.map((it) => (
        <button key={it.id} role="tab" aria-selected={value === it.id} onClick={() => onChange(it.id)}
          className={cx("-mb-px whitespace-nowrap border-b-2 px-2.5 py-2 text-[13px] font-medium transition-colors",
            value === it.id ? "border-accent text-ink" : "border-transparent text-ink-3 hover:text-ink")}>
          {it.label}
        </button>
      ))}
    </div>
  );
}

/** Renders model text safely: paragraphs, "- " bullets and **bold**. No HTML. */
export function Rich({ text, className }: { text: string; className?: string }) {
  const inline = (line: string) => line.split(/(\*\*[^*]+\*\*)/g).map((part, j) =>
    part.startsWith("**") && part.endsWith("**") ? <strong key={j} className="font-semibold">{part.slice(2, -2)}</strong> : part);
  return (
    <span className={className}>
      {text.split("\n").filter((l) => l.trim()).map((line, i) => {
        const bullet = /^\s*[-*•]\s+/.test(line);
        return bullet
          ? <span key={i} className="flex gap-2"><span className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-ink-3" /><span>{inline(line.replace(/^\s*[-*•]\s+/, ""))}</span></span>
          : <span key={i} className="block">{inline(line.replace(/^#+\s*/, ""))}</span>;
      })}
    </span>
  );
}
