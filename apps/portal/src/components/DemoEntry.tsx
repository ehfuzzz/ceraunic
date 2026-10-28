"use client";

// Opens the shared, seeded `demo` world (scripts/seed-demo.py) as one of its three businesses.
// It forgets this browser's private world (so every page reads `demo`) and acts as that business's owner address.
// The addresses are anvil's public dev accounts, the same ones the seed uses; sim mode only.
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { clearCoreSession } from "@/lib/core-session";
import { notifyStoreChanged } from "@/lib/trading-store";

const SEEDED = {
  nyc: { name: "Fixture Scoops Midtown", city: "New York", owner: "0x15d34aaf54267db7d7c367839aaf71a00a2c6a65" },
  chi: { name: "Fixture Bakehouse Midway", city: "Chicago", owner: "0x9965507d1a55bcc2695c58ba16fb37d819b0a4dc" },
  mia: { name: "Fixture Juice Bar Miami", city: "Miami", owner: "0x976ea74026e726554db657fa54763abd0c3a0aa9" },
} as const;
type Key = keyof typeof SEEDED;
const isKey = (k: string | null): k is Key => !!k && k in SEEDED;

export function DemoEntry({ as }: { as: string | null }) {
  const router = useRouter();
  const qc = useQueryClient();

  const open = (k: Key) => {
    window.localStorage.removeItem("wi.world");
    window.localStorage.setItem("wi.trade.address", SEEDED[k].owner);
    clearCoreSession();
    notifyStoreChanged();
    qc.clear();
    router.replace("/app/policies");
  };

  useEffect(() => {
    if (isKey(as)) open(as);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [as]);

  return (
    <section className="max-w-2xl">
      <h1 className="font-display text-3xl tracking-tight">Seeded demo</h1>
      <p className="mt-4 text-muted">
        Everyone who opens the demo shares one simulated world. It was set up with three small businesses, each with a week of weather cover
        bought on 15 July 2026, and the clock moved forward until the first covered day paid out. Pick one to see it from the owner&apos;s side.
      </p>
      <ul className="mt-8 space-y-3">
        {(Object.keys(SEEDED) as Key[]).map((k) => (
          <li key={k}>
            <button type="button" onClick={() => open(k)} className="text-left underline" data-testid={`demo-as-${k}`}>
              {SEEDED[k].name} ({SEEDED[k].city})
            </button>
          </li>
        ))}
      </ul>
      <p className="mt-8 text-sm text-muted">
        Onboarding a new business starts a private world of your own, so nothing you do there changes this one. Come back here to return to it.
      </p>
    </section>
  );
}
