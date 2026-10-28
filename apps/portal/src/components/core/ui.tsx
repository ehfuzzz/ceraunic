// Small shared pieces for the onboard / coverage / policies pages. Tokens come from globals.css.
import type { ReactNode } from "react";

export const btnPrimary =
  "border border-accent bg-accent px-4 py-2 text-sm text-bg transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40";
export const btn =
  "border border-rule px-4 py-2 text-sm transition-colors hover:border-ink disabled:cursor-not-allowed disabled:opacity-40";
export const input =
  "w-full border border-rule bg-bg px-3 py-2 text-sm text-ink placeholder:text-muted/70 focus:border-ink focus:outline-none";
export const label = "block text-xs uppercase tracking-wide text-muted";

export function Step({ n, title, done, children, id }: { n: number; title: string; done?: boolean; children: ReactNode; id?: string }) {
  return (
    <section id={id} className="mt-12 max-w-3xl">
      <div className="flex items-baseline gap-3 border-b border-rule pb-2">
        <span className={`font-mono text-xs ${done ? "text-accent" : "text-muted"}`}>{done ? "done" : `step ${n}`}</span>
        <h2 className="font-display text-xl tracking-tight">{title}</h2>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}

export function Stat({ label: l, value, note, testId }: { label: string; value: ReactNode; note?: ReactNode; testId?: string }) {
  return (
    <div className="border-t border-rule pt-2">
      <div className="text-xs text-muted">{l}</div>
      <div className="mt-0.5 text-lg" data-testid={testId}>
        {value}
      </div>
      {note && <div className="mt-0.5 text-xs text-muted">{note}</div>}
    </div>
  );
}

export function ErrorLine({ error }: { error: string | null | undefined }) {
  if (!error) return null;
  return (
    <p role="alert" className="mt-3 text-sm text-accent">
      {error}
    </p>
  );
}

export function Muted({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <p className={`text-sm text-muted ${className}`}>{children}</p>;
}

export function Row({ k, v, mono }: { k: ReactNode; v: ReactNode; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-4 border-b border-rule/70 py-1.5 text-sm">
      <span className="text-muted">{k}</span>
      <span className={`text-right ${mono ? "font-mono text-xs" : ""}`}>{v}</span>
    </div>
  );
}
