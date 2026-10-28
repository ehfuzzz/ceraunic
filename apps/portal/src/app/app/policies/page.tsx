import { PoliciesView } from "@/components/core/PoliciesView";

export default function PoliciesPage() {
  return (
    <section>
      <h1 className="font-display text-3xl tracking-tight">Policies</h1>
      <p className="mt-4 max-w-xl text-muted">What you&apos;ve bought, what each covered day read, and what it paid.</p>
      <PoliciesView />
    </section>
  );
}
