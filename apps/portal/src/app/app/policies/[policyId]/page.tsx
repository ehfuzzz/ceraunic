import { PolicyDetail } from "@/components/core/PoliciesView";

export default async function PolicyPage({ params }: { params: Promise<{ policyId: string }> }) {
  const { policyId } = await params;
  return (
    <section>
      <h1 className="font-display text-3xl tracking-tight">
        Policy <span className="font-mono text-2xl">{policyId}</span>
      </h1>
      <PolicyDetail id={policyId} />
    </section>
  );
}
