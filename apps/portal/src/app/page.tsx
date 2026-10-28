import Link from "next/link";

export default function Landing() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-2xl flex-col justify-between px-6 py-10 md:py-16">
      <p className="font-display text-lg">WI · weather cover</p>

      <div>
        <h1 className="font-display text-4xl leading-tight tracking-tight md:text-6xl">
          Cover for the weather on your own block.
        </h1>
        <ul className="mt-12 space-y-5 text-lg">
          <li>
            You pick a payout tied to the temperature or rain at your address,
            not at the nearest airport.
          </li>
          <li className="text-muted">
            Most of the risk is hedged on liquid airport-station contracts that
            already trade.
          </li>
          <li className="text-muted">
            The small gap between the airport and your block is traded in
            batch auctions, open to anyone with a wallet.
          </li>
        </ul>
        <Link
          href="/app"
          className="mt-12 inline-block border-b border-accent pb-0.5 text-lg text-accent no-underline"
        >
          Open the app
        </Link>
      </div>

      <p className="text-sm text-muted">
        A prototype. Testnet and simulated money only.
      </p>
    </main>
  );
}
