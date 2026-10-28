"use client";

import { useState } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { api, type Auction } from "@/lib/api";
import { utc } from "@/lib/trading-format";
import { POLL_MS, useContractInfo, useSimClock } from "@/lib/trading-queries";
import { useTradingAccount } from "@/lib/trading-store";
import { AdminModeBanner } from "./AdminModeBanner";
import { TradeAccountBar } from "./TradeAccountBar";
import { TradeAuctionDetail } from "./TradeAuctionDetail";
import { TradeAuctionList } from "./TradeAuctionList";
import { Empty, ErrorLine, Panel } from "./TradingKit";

const FILTERS = ["all", "open", "closed", "cleared"] as const;

export function TradeBoard() {
  const info = useContractInfo();
  const acct = useTradingAccount();
  const clock = useSimClock();
  const list = useQuery({ queryKey: ["auctions"], queryFn: () => api.auctions(), refetchInterval: POLL_MS });
  const details = useQueries({
    queries: (list.data ?? []).map((a) => ({
      queryKey: ["auction", a.auctionId],
      queryFn: () => api.auction(a.auctionId),
      refetchInterval: POLL_MS,
    })),
  });
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");
  const [picked, setPicked] = useState<string | null>(null);

  const all: Auction[] = details.flatMap((d) => (d.data ? [d.data] : []));
  all.sort((a, b) => (a.day === b.day ? a.stationId.localeCompare(b.stationId) : a.day.localeCompare(b.day)));
  const shown = all.filter((a) => filter === "all" || a.status === filter);
  const selected = all.find((a) => a.auctionId === picked) ?? all.find((a) => a.status === "open") ?? all[0];

  return (
    <div className="max-w-5xl">
      <h1 className="font-display text-3xl tracking-tight">Trade</h1>
      <p className="mt-4 max-w-2xl text-muted">
        Each night the weather cover we sell leaves a small leftover risk in every city: how much hotter or cooler the metro runs than its
        weather station. That leftover is traded here, one market per city per day, in a batch auction. Anyone with a wallet can buy or sell.
      </p>
      <details className="mt-4 max-w-2xl text-sm text-muted">
        <summary className="cursor-pointer text-ink">How is the price set?</summary>
        <p className="mt-2">
          Orders pile up until the cutoff. Then the engine picks one price for everybody: the price at which the most units can trade. If two
          prices trade the same amount, it takes the one closest to balanced, and if that ties too, the middle. Buyers who bid at or above that
          price pay it, sellers who asked at or below it receive it. Nobody pays their own limit, so there is nothing to gain by guessing the
          price. The pool&rsquo;s house quote is in the pile as well, up to its size, so there is usually something to trade against.
        </p>
        <p className="mt-2">
          Prices come in two forms. The <em>tick</em> is what you type: cents from 1 to 99 for a unit that pays at most $1. The <em>basis</em>{" "}
          is the same price as the gap, in degrees F, between the metro and its station that would make you break even. 50&cent; is 0.0 &deg;F.
          A lower price means the market expects the metro to run cooler than the station.
        </p>
      </details>

      <div className="mt-8">
        <AdminModeBanner />
        <TradeAccountBar />
      </div>

      <Panel
        title="Auctions"
        aside={clock.data ? <>sim time {utc(clock.data.simTime)}</> : undefined}
      >
        <div className="mb-4 flex gap-2" role="group" aria-label="Filter by status">
          {FILTERS.map((f) => (
            <button
              key={f}
              aria-pressed={filter === f}
              onClick={() => setFilter(f)}
              className={`rounded-full border px-3 py-1 text-sm ${filter === f ? "border-accent text-accent" : "border-rule text-muted"}`}
            >
              {f}
            </button>
          ))}
        </div>
        <ErrorLine error={list.error} />
        {list.isPending ? (
          <Empty>Loading auctions&hellip;</Empty>
        ) : (
          <TradeAuctionList
            auctions={shown}
            selectedId={selected?.auctionId ?? null}
            onSelect={setPicked}
            city={info.city}
            range={info.range}
          />
        )}
      </Panel>

      {selected && (
        <TradeAuctionDetail
          auction={selected}
          trader={acct.address}
          city={info.city(selected.stationId)}
          range={info.range(selected.contractId)}
          isSim={info.mode === "sim"}
          simTime={clock.data?.simTime}
          onCleared={() => setPicked(selected.auctionId)}
        />
      )}
    </div>
  );
}
