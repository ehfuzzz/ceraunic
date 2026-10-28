import { DemoEntry } from "@/components/DemoEntry";

// The seeded shared demo world (scripts/seed-demo.py). /app/demo?as=chi opens it as the Chicago bakery.
export default async function DemoPage({ searchParams }: { searchParams: Promise<{ [key: string]: string | string[] | undefined }> }) {
  const as = (await searchParams).as;
  return <DemoEntry as={typeof as === "string" ? as : null} />;
}
