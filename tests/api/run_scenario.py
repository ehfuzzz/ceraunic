"""Run tests/api/scenario_nyc_3d.json against an engine API and write a normalised response dump.

    uv run python tests/api/run_scenario.py http://127.0.0.1:8787 [--out dump.json]

Normalisation drops ids, hashes and timestamps so a sim run and an anvil run can be compared
field for field on money (...E6), quantities, days and statuses. Exit 0 iff every step returned
its expected status.

    uv run python tests/api/run_scenario.py <base> --golden          # also compare with golden/scenario_nyc_3d.json
    uv run python tests/api/run_scenario.py <base> --write-golden    # record the golden (sim only; review it)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests

HERE = Path(__file__).parent
DROP_KEYS = {"simTime", "asOf", "tickKey", "blockNumber", "txHash", "hash", "expiresAt", "publicCutoff",
             "ts", "fetchedAt", "epochTs", "refId", "positionId", "worldId"}
ID_SUFFIX = re.compile(r"(Id|Ids|Hash)$")


def normalise(x):
    if isinstance(x, dict):
        return {k: normalise(v) for k, v in x.items() if k not in DROP_KEYS and not ID_SUFFIX.search(k)}
    if isinstance(x, list):
        return [normalise(v) for v in x]
    return x


MONEY_KEY = re.compile(r"(E6|^qty|Qty|^units|^status|^value|^day|^days|^side|^peril|^path|^kind|^tranche|Shares|^shares|"
                       r"Wei$|^bps|TenthsF$|^tick$)")


def money(dump: list[dict]) -> list:
    """The money projection the golden pins: HTTP status per step plus every money / quantity / status /
    index-value field (with its path), in step order. Mode-specific fields (mode, chainId, ids, times) drop."""
    out = []

    def walk(x, path):
        if isinstance(x, dict):
            for k in sorted(x):
                if isinstance(x[k], (dict, list)):
                    walk(x[k], path + "." + k)
                elif MONEY_KEY.search(k):
                    out.append([path + "." + k, x[k]])
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f"{path}[{i}]")

    for s in dump:
        out.append([s["step"] + ":http", s["status"]])
        walk(s["body"], s["step"])
    return out


def dig(data, path: str):
    """'a.b', '0.id', or '[key=value].field' (first list item where key == value)."""
    cur = data
    for part in re.findall(r"\[[^\]]+\]|[^.\[\]]+", path):
        if part.startswith("["):
            k, v = part[1:-1].split("=", 1)
            cur = next(i for i in cur if str(i.get(k)) == v)
        elif isinstance(cur, list):
            cur = cur[int(part)]
        else:
            cur = cur[part]
    return cur


def sub(x, env: dict):
    if isinstance(x, str):
        return re.sub(r"\{\{(\w+)\}\}", lambda m: str(env[m.group(1)]), x)
    if isinstance(x, dict):
        return {k: sub(v, env) for k, v in x.items()}
    if isinstance(x, list):
        return [sub(v, env) for v in x]
    return x


def run(base: str, scenario: dict, http=requests) -> tuple[list[dict], bool]:
    env: dict[str, str] = {}
    dump, ok = [], True
    for step in scenario["steps"]:
        resp = http.request(step["method"], base.rstrip("/") + sub(step["path"], env),
                                headers=sub(step.get("headers", {}), env), json=sub(step.get("body"), env)
                                if "body" in step else None, timeout=30)
        want = step.get("expect", 200)
        good = resp.status_code == want
        ok &= good
        body = resp.json() if resp.content else None
        if good:
            for var, path in step.get("save", {}).items():
                env[var] = dig(body, path)
        dump.append({"step": step["name"], "status": resp.status_code, "body": normalise(body)})
        print(f"{'ok ' if good else 'BAD'} {resp.status_code} {step['name']}", file=sys.stderr)
    return dump, ok


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    base = args[0] if args else "http://127.0.0.1:8787"
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else HERE.parents[1] / "var" / "api" / "last_run.json"
    dump, ok = run(base, json.loads((HERE / "scenario_nyc_3d.json").read_text()))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dump, indent=1, sort_keys=True) + "\n")
    golden = HERE / "golden" / "scenario_nyc_3d.json"
    if "--write-golden" in sys.argv and ok:
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(json.dumps(money(dump), indent=0) + "\n")
        print(f"wrote {golden}", file=sys.stderr)
    if "--golden" in sys.argv:
        want = json.loads(golden.read_text())
        got = money(dump)
        diffs = [(i, w, g) for i, (w, g) in enumerate(zip(want, got)) if w != g]
        if len(want) != len(got):
            print(f"golden length {len(want)} != run length {len(got)}", file=sys.stderr)
            ok = False
        for i, w, g in diffs[:40]:
            print(f"DIFF {i}: golden {w} run {g}", file=sys.stderr)
        ok &= not diffs
        print("golden: " + ("MATCH" if not diffs and len(want) == len(got) else f"{len(diffs)} diffs"), file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
