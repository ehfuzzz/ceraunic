// Small shared look for the trade, pool and admin pages: panels, stats, buttons, error lines.
import type { ReactNode } from "react";
import { EngineError } from "@/lib/api";

export const btn =
  "rounded-full border border-rule px-4 py-1.5 text-sm transition-colors hover:border-ink disabled:cursor-not-allowed disabled:opacity-40";
export const btnAccent = `${btn} border-accent text-accent hover:bg-accent hover:text-bg`;
export const field =
  "rounded border border-rule bg-transparent px-3 py-1.5 text-sm font-mono outline-none focus:border-ink";
export const th = "py-2 pr-4 text-left text-xs font-normal uppercase tracking-wide text-muted";
export const td = "py-2 pr-4 align-top text-sm";

export function Panel({
  title,
  aside,
  children,
  id,
}: {
  title: string;
  aside?: ReactNode;
  children: ReactNode;
  id?: string;
}) {
  return (
    <section id={id} className="mt-10 border-t border-rule pt-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="font-display text-xl tracking-tight">{title}</h2>
        {aside && <div className="text-xs text-muted">{aside}</div>}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-1 font-mono text-lg">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-muted">{sub}</div>}
    </div>
  );
}

export function messageOf(e: unknown): string {
  if (e instanceof EngineError) {
    if (e.code === "RPC_UNAVAILABLE")
      return "The engine is running on a real chain mode and does not serve this yet. Switch the engine to sim to use this page.";
    return e.message;
  }
  return e instanceof Error ? e.message : String(e);
}

export function ErrorLine({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p role="alert" className="mt-3 text-sm text-accent">
      {messageOf(error)}
    </p>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="text-sm text-muted">{children}</p>;
}

export function Bar({ fraction, label }: { fraction: number; label?: string }) {
  const f = Math.max(0, Math.min(1, fraction));
  return (
    <div role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(f * 100)} aria-label={label} className="h-2 w-full rounded-full bg-surface">
      <div className="h-2 rounded-full bg-accent" style={{ width: `${f * 100}%` }} />
    </div>
  );
}
