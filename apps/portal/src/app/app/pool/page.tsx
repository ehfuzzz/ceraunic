import type { Metadata } from "next";
import { PoolBoard } from "@/components/PoolBoard";

export const metadata: Metadata = { title: "Pool | WI · weather cover" };

export default function PoolPage() {
  return <PoolBoard />;
}
