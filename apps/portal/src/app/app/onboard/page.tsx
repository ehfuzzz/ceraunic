import { OnboardFlow } from "@/components/core/OnboardFlow";

export default function OnboardPage() {
  return (
    <section>
      <h1 className="font-display text-3xl tracking-tight">Onboard</h1>
      <p className="mt-4 max-w-xl text-muted">
        Tell us about your business, upload your sales history or connect your point-of-sale, and see how weather moves your
        revenue. Then we suggest a weather payout that fits.
      </p>
      <OnboardFlow />
    </section>
  );
}
