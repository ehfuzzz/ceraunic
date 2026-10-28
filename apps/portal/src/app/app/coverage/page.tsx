import type { Metadata } from "next";
import { CoverageFlow } from "@/components/core/CoverageFlow";

export const metadata: Metadata = { title: "Cover | WI · weather cover" };

export default function CoveragePage() {
  return (
    <section>
      <h1 className="font-display text-3xl tracking-tight">Cover</h1>
      <p className="mt-4 max-w-xl text-muted">
        The cover we suggest for your business, what it costs on each of the two paths, and buying it. A weather payout here is
        paid from the public weather record, so there&apos;s no claim to file. Hot days, cool days and rainy days.
      </p>
      <CoverageFlow />
    </section>
  );
}
