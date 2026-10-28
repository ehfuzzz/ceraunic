import Link from "next/link";
import { ChainPill } from "./ChainPill";
import { ConnectButton } from "./ConnectButton";

export function Header() {
  return (
    <header className="flex items-center justify-between gap-4 border-b border-rule px-6 py-4 md:px-10">
      <Link href="/" className="font-display text-lg no-underline">
        WI · weather cover
      </Link>
      <div className="flex items-center gap-4">
        <ChainPill />
        <ConnectButton />
      </div>
    </header>
  );
}
