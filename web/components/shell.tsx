"use client";

import { ArrowLeftRight, Code2, Route, Database, Inbox, LayoutGrid, Menu, TrendingUp, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type Status } from "@/lib/api";
import { cx, SalesforceMark } from "./ui";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutGrid },
  { href: "/refresh", label: "Refresh & migrate", icon: Database },
  { href: "/revenue", label: "Revenue agent", icon: TrendingUp },
  { href: "/review", label: "Code review", icon: Code2 },
  { href: "/router", label: "AI router", icon: Route },
  { href: "/approvals", label: "Approvals & audit", icon: Inbox, badge: true },
];

const StatusCtx = createContext<{ status: Status | null; refresh: () => void }>({ status: null, refresh: () => {} });
export const useStatus = () => useContext(StatusCtx);

export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const [status, setStatus] = useState<Status | null>(null);
  const [offline, setOffline] = useState(false);
  const [open, setOpen] = useState(false);

  const refresh = () => api<Status>("/status").then((s) => { setStatus(s); setOffline(false); }).catch(() => setOffline(true));
  useEffect(() => { refresh(); const t = setInterval(refresh, 5000); return () => clearInterval(t); }, []);
  useEffect(() => setOpen(false), [path]);

  const org = status?.org;
  const nav = (
    <nav className="flex flex-1 flex-col gap-0.5 px-2" aria-label="Main">
      {NAV.map(({ href, label, icon: Icon, badge }) => {
        const active = href === "/" ? path === "/" : path.startsWith(href);
        const pending = badge ? status?.stats.pending_approvals ?? 0 : 0;
        return (
          <Link key={href} href={href} aria-current={active ? "page" : undefined}
            className={cx("flex h-8 items-center gap-2.5 rounded-md px-2.5 text-[13px] font-medium transition-colors",
              active ? "bg-accent-soft text-heading font-semibold" : "text-ink-2 hover:bg-surface hover:text-heading")}>
            <Icon size={15} strokeWidth={1.75} className={active ? "text-accent" : "text-ink-3"} />
            <span className="flex-1">{label}</span>
            {pending > 0 && <span className="rounded bg-accent px-1.5 font-mono text-[11px] leading-[18px] text-accent-ink tabular">{pending}</span>}
          </Link>
        );
      })}
    </nav>
  );

  const orgBadge = (
    <Link href="/" className="mx-2 mb-3 flex items-center gap-2.5 rounded-md border border-line bg-surface px-2.5 py-2 hover:border-line-strong">
      <SalesforceMark size={30} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[12.5px] font-medium text-ink">{offline ? "API offline" : org?.org_name ?? "Connecting…"}</span>
        <span className="flex items-center gap-1.5 text-[11.5px] text-ink-3">
          <span className={cx("h-1.5 w-1.5 rounded-full", offline ? "bg-critical" : org?.connected ? "bg-ok" : "bg-line-strong")} />
          {offline ? "start the backend" : org?.edition ?? "Connected"}
          {!offline && <>{" · "}{status?.claude.configured ? "Claude" : "Rules engine"}</>}
        </span>
      </span>
    </Link>
  );

  return (
    <StatusCtx.Provider value={{ status, refresh }}>
      <div className="min-h-screen md:grid md:grid-cols-[232px_1fr]">
        <aside className="sticky top-0 hidden h-screen flex-col border-r border-line bg-surface md:flex">
          <Brand />
          {nav}
          {orgBadge}
        </aside>

        <div className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-paper/95 px-4 py-2.5 backdrop-blur md:hidden">
          <Brand compact />
          <button onClick={() => setOpen(!open)} aria-label={open ? "Close menu" : "Open menu"} className="rounded-md p-1.5 hover:bg-sunken">
            {open ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
        {open && <div className="fixed inset-x-0 top-[49px] z-20 flex flex-col gap-2 border-b border-line bg-paper pb-2 pt-2 shadow-[0_8px_24px_rgba(23,25,27,0.08)] md:hidden">{nav}{orgBadge}</div>}

        <main className="page-wash min-w-0 px-4 py-6 md:px-8 md:py-8">
          <div className="mx-auto max-w-[1240px]">{children}</div>
        </main>
      </div>
    </StatusCtx.Provider>
  );
}

function Brand({ compact }: { compact?: boolean }) {
  return (
    <Link href="/" className={cx("flex items-center gap-2", compact ? "" : "px-4 pb-5 pt-5")}>
      <span className="flex h-7 w-7 items-center justify-center rounded-md bg-heading text-white">
        <ArrowLeftRight size={14} strokeWidth={2.25} />
      </span>
      <span className="leading-tight">
        <span className="block font-display text-[14px] font-semibold tracking-[-0.01em] text-heading">SF Ops Copilot</span>
        {!compact && <span className="block text-[12px] text-ink-3">Salesforce automation, approved</span>}
      </span>
    </Link>
  );
}
