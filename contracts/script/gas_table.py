#!/usr/bin/env python3
"""Max gasUsed / gas limit per (contract, function) over mined anvil transactions in broadcast/*/31337.

Reads every run-<ts>.json (not run-latest, which duplicates the newest run). Prints a markdown table
and flags anything whose gasUsed exceeds the 2.0M non-deploy budget or whose gas limit exceeds 3M.
"""
import glob
import json
import os
import sys

root = sys.argv[1] if len(sys.argv) > 1 else "broadcast"
names = {}
book = os.path.join(os.path.dirname(os.path.abspath(root)), "deployments", "31337.json")
if os.path.exists(book):
    for k, v in json.load(open(book)).items():
        if isinstance(v, str) and v.startswith("0x") and len(v) == 42:
            names.setdefault(v.lower(), k)
rows = {}
for path in sorted(glob.glob(os.path.join(root, "*", "31337", "run-*.json"))):
    if path.endswith("run-latest.json"):
        continue
    run = json.load(open(path))
    gas_used = {r["transactionHash"]: int(r["gasUsed"], 16) for r in run.get("receipts", []) if int(r.get("status", "0x1"), 16) == 1}
    for tx in run.get("transactions", []):
        h = tx.get("hash")
        if h not in gas_used:
            continue
        kind = tx.get("transactionType")
        name = tx.get("contractName") or names.get((tx["transaction"].get("to") or "").lower(), "?")
        fn = "CREATE" if kind in ("CREATE", "CREATE2") else (tx.get("function") or "?").split("(")[0]
        limit = int(tx["transaction"].get("gas", "0x0"), 16)
        key = (name, fn)
        n, u, lim = rows.get(key, (0, 0, 0))
        rows[key] = (n + 1, max(u, gas_used[h]), max(lim, limit))

print("| contract | function | txs | max gasUsed | max gas limit | ok |")
print("|---|---|---|---|---|---|")
bad = 0
for (name, fn), (n, u, lim) in sorted(rows.items(), key=lambda kv: -kv[1][1]):
    ok = fn == "CREATE" or (u <= 2_000_000 and lim <= 3_000_000)
    bad += not ok
    print(f"| {name} | {fn} | {n} | {u:,} | {lim:,} | {'yes' if ok else 'NO'} |")
print(f"\n{sum(v[0] for v in rows.values())} mined transactions; {bad} over budget")
sys.exit(1 if bad else 0)
