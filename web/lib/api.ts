"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type Severity = "critical" | "high" | "medium" | "low";

export interface Status {
  claude: { configured: boolean; agent_model: string; bulk_model: string };
  org: { mode: "demo" | "live"; connected: boolean; org_name?: string; edition?: string; instance_url?: string | null; error?: string };
  salesforce_configured: boolean;
  stats: { runs: number; pending_approvals: number; approved: number; audit_events: number; assessed_leads: number; tokens_in: number; tokens_out: number };
  recent_runs: RunSummary[];
}

export interface RunSummary { id: string; module: string; status: "running" | "done" | "failed"; engine: string; created_at: string; finished_at?: string; error?: string }
export interface Run<T = unknown> extends RunSummary { result: T | null; progress: { at: string; message: string }[] }

export interface Lead {
  Id: string; FirstName: string; LastName: string; Title: string | null; Company: string; Email: string | null;
  Phone: string | null; Industry: string | null; NumberOfEmployees: number | null; Country: string | null;
  LeadSource: string | null; Status: string; LastActivityDate: string | null; Activity: string[]; OwnerName: string | null;
  score: number; tier: "A" | "B" | "C"; next_best_action: string; reasons: string[]; sources: string[];
  engine: string; assessed: boolean;
}

export interface Finding { rule: string; severity: Severity; line: number; message: string; fix: string; source: "static" | "claude"; confirmed: boolean }
export interface ReviewResult { engine: string; summary: string; production_ready: boolean; findings: Finding[]; corrected_code: string; test_class: string }

export interface Approval {
  id: string; run_id: string | null; created_at: string; kind: "send_email" | "update_record" | "merge_records";
  target: string; title: string; payload: Record<string, any>; rationale: string; status: "pending" | "approved" | "rejected";
  decided_at: string | null;
}

export interface AuditEvent { id: number; run_id: string | null; at: string; actor: string; kind: string; summary: string; detail: any; model: string | null; input_tokens: number | null; output_tokens: number | null }

export class ApiError extends Error {}

export async function api<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init ?? {};
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      ...rest,
      headers: { "Content-Type": "application/json", ...(rest.headers ?? {}) },
      body: json !== undefined ? JSON.stringify(json) : rest.body,
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Can't reach the API at localhost:8000. Start it with `make api` (see README).");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch {}
    throw new ApiError(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

/** Load a resource; `reload()` refetches. */
export function useResource<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    try { setData(await api<T>(path)); setError(null); }
    catch (e) { setError((e as Error).message); }
    finally { setLoading(false); }
  }, [path]);
  useEffect(() => { reload(); }, [reload]);
  return { data, error, loading, reload, setData };
}

/** Start a background run and poll it until it finishes. */
export function useRun<T>(onDone?: (run: Run<T>) => void) {
  const [run, setRun] = useState<Run<T> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const done = useRef(onDone);
  done.current = onDone;

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const poll = useCallback(async (id: string) => {
    try {
      const r = await api<Run<T>>(`/runs/${id}`);
      setRun(r);
      if (r.status === "running") timer.current = setTimeout(() => poll(id), 700);
      else done.current?.(r);
    } catch (e) { setError((e as Error).message); }
  }, []);

  const start = useCallback(async (path: string, json: unknown = {}) => {
    setError(null);
    try {
      const { run_id } = await api<{ run_id: string }>(path, { method: "POST", json });
      setRun({ id: run_id, module: "", status: "running", engine: "", created_at: "", result: null, progress: [] });
      poll(run_id);
    } catch (e) { setError((e as Error).message); }
  }, [poll]);

  return { run, error, start, running: run?.status === "running", reset: () => setRun(null) };
}

export const fmt = {
  n: (v: number | null | undefined) => (v == null ? "—" : v.toLocaleString("en-US")),
  time: (iso: string) => new Date(iso).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
  dateTime: (iso: string) => new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }),
  ago: (iso: string | null) => {
    if (!iso) return "never";
    const days = Math.round((Date.parse("2026-11-03") - Date.parse(iso)) / 86_400_000);
    return days <= 0 ? "today" : days === 1 ? "1 day ago" : days < 60 ? `${days} days ago` : `${Math.round(days / 30)} months ago`;
  },
};

export const MODULES: Record<string, string> = {
  "code-review": "Code review",
  "revenue-agent": "Revenue agent",
  dedupe: "Duplicate scan",
  refresh: "Refresh & migrate",
  "ai-router": "AI router",
};
