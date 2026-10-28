"use client";

import { useCoreSession } from "@/lib/core-session";
import { BusinessCard } from "./BusinessCard";
import { BusinessForm } from "./BusinessForm";
import { ElasticityView } from "./ElasticityView";
import { HolderCard } from "./HolderCard";
import { SalesStep } from "./SalesStep";
import { Muted, Step } from "./ui";

export function OnboardFlow() {
  const { business, elasticity, sales } = useCoreSession();
  return (
    <>
      <div className="mt-8 max-w-3xl">
        <HolderCard />
      </div>
      <Step n={1} title="Your business" done={!!business}>
        {business ? <BusinessCard business={business} /> : <BusinessForm />}
      </Step>
      <Step n={2} title="Your sales" done={!!sales}>
        {business ? <SalesStep business={business} /> : <Muted>Save your business first. Then upload a sales file or connect Square.</Muted>}
      </Step>
      <Step n={3} title="How weather moves your sales" done={!!elasticity}>
        {business && elasticity ? (
          <ElasticityView business={business} e={elasticity} />
        ) : (
          <Muted>Once your sales are in, this shows how much a hot or rainy day changes them, and how sure we are.</Muted>
        )}
      </Step>
    </>
  );
}
