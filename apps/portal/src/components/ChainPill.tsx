import { CHAIN_MODE, MODE_LABEL } from "@/lib/chain-mode";

export function ChainPill() {
  return (
    <span
      title={MODE_LABEL[CHAIN_MODE]}
      className="inline-flex items-center gap-2 rounded-full border border-rule px-3 py-1 font-mono text-xs text-muted"
    >
      <span aria-hidden className="size-1.5 rounded-full bg-accent" />
      {CHAIN_MODE}
    </span>
  );
}
