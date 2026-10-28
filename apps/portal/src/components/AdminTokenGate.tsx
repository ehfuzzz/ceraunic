"use client";

import { useState } from "react";
import { useAdminToken } from "@/lib/trading-store";
import { btn, field } from "./TradingKit";

/** The admin token is typed once and kept in sessionStorage only. It is never in the code or the build. */
export function AdminTokenGate({ children }: { children: React.ReactNode }) {
  const { token, setToken } = useAdminToken();
  const [draft, setDraft] = useState("");

  if (!token)
    return (
      <form
        className="max-w-md space-y-3 border border-rule px-4 py-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (draft.trim()) setToken(draft.trim());
        }}
      >
        <label className="block text-sm">
          Admin token
          <input
            type="password"
            autoComplete="off"
            className={`${field} mt-1 block w-full`}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
        </label>
        <p className="text-sm text-muted">
          Type it once. It is kept in this tab only and forgotten when you close it. For a local engine it is the one set in
          ADMIN_TOKEN.
        </p>
        <button className={btn} disabled={!draft.trim()}>
          Use token
        </button>
      </form>
    );

  return (
    <>
      <p className="mb-2 text-xs text-muted">
        Admin token is set for this tab.{" "}
        <button className="underline" onClick={() => setToken(null)}>
          Forget it
        </button>
      </p>
      {children}
    </>
  );
}
