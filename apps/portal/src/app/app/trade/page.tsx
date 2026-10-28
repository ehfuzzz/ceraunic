import type { Metadata } from "next";
import { TradeBoard } from "@/components/TradeBoard";

export const metadata: Metadata = { title: "Trade | WI · weather cover" };

export default function TradePage() {
  return <TradeBoard />;
}
