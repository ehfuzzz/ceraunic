#!/usr/bin/env python3
"""Toggle HyperEVM big-block mode for the deployer. TESTNET ONLY. The owner runs this; agents never do.

Usage (from contracts/):
  uv run --no-project --python 3.12 --with hyperliquid-python-sdk==0.24.0 python script/hl_big_blocks.py status [0xADDRESS]
  uv run --no-project --python 3.12 --with hyperliquid-python-sdk==0.24.0 python script/hl_big_blocks.py on
  uv run --no-project --python 3.12 --with hyperliquid-python-sdk==0.24.0 python script/hl_big_blocks.py off
(`make bigblocks-status|bigblocks-on|bigblocks-off` wraps these.)

What it does: signs the HyperCore L1 action {"type": "evmUserModify", "usingBigBlocks": true|false} with
the deployer key (decrypted from the Foundry keystore, password prompted, never stored or printed) via
hyperliquid-python-sdk's Exchange.use_big_blocks, then polls eth_usingBigBlocks on the EVM RPC.

Guards (all must pass before anything is signed):
  * the exchange endpoint is the SDK's TESTNET_API_URL and must contain "testnet"; there is no mainnet path;
  * the EVM RPC must answer eth_chainId == 998 (0x3e6);
  * the RPC host must not be a known mainnet host.
"""
from __future__ import annotations

import getpass
import json
import os
import sys
import time
import urllib.request

TESTNET_CHAIN_ID = 998
RPC = os.environ.get("HYPEREVM_TESTNET_RPC", "https://rpc.hyperliquid-testnet.xyz/evm")
KEYSTORE = os.path.expanduser(os.environ.get("DEPLOYER_KEYSTORE", "~/.foundry/keystores/wi-deployer"))
MAINNET_HOSTS = ("rpc.hyperliquid.xyz", "api.hyperliquid.xyz")


def die(msg: str) -> None:
    print(f"REFUSING: {msg}", file=sys.stderr)
    sys.exit(2)


def rpc(method: str, params: list) -> object:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(RPC, body, {"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        out = json.load(r)
    if "error" in out:
        raise RuntimeError(f"{method}: {out['error']}")
    return out["result"]


def check_testnet_rpc() -> None:
    if any(h in RPC for h in MAINNET_HOSTS):
        die(f"RPC {RPC} is a mainnet host")
    cid = int(str(rpc("eth_chainId", [])), 16)
    if cid != TESTNET_CHAIN_ID:
        die(f"RPC {RPC} is chain {cid}, not HyperEVM testnet ({TESTNET_CHAIN_ID})")


def using_big_blocks(addr: str) -> bool:
    return bool(rpc("eth_usingBigBlocks", [addr]))


def load_account():
    from eth_account import Account

    if not os.path.exists(KEYSTORE):
        die(f"keystore {KEYSTORE} not found (cast wallet import wi-deployer --interactive)")
    with open(KEYSTORE) as f:
        ks = json.load(f)
    key = Account.decrypt(ks, getpass.getpass(f"password for {KEYSTORE}: "))
    return Account.from_key(key)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd not in ("status", "on", "off"):
        die("usage: hl_big_blocks.py status [0xADDRESS] | on | off")
    check_testnet_rpc()
    if cmd == "status" and len(sys.argv) > 2:
        addr = sys.argv[2]
        print("address", addr, "usingBigBlocks:", using_big_blocks(addr))
        return

    acct = load_account()
    print("deployer", acct.address, "usingBigBlocks:", using_big_blocks(acct.address))
    if cmd == "status":
        return

    from hyperliquid.exchange import Exchange
    from hyperliquid.utils import constants

    api = constants.TESTNET_API_URL
    if "testnet" not in api:
        die(f"SDK TESTNET_API_URL looks wrong: {api}")
    want = cmd == "on"
    resp = Exchange(acct, api).use_big_blocks(want)
    print("exchange response:", resp)  # expect {'status': 'ok', 'response': {'type': 'default'}}
    if not (isinstance(resp, dict) and resp.get("status") == "ok"):
        print("The action failed. If it mentions the user/account, the deployer is not a HyperCore user yet:"
              " send it ~5 USDC on HyperCore testnet first (RUNBOOK step 4).", file=sys.stderr)
        sys.exit(1)
    for _ in range(15):
        if using_big_blocks(acct.address) == want:
            print("usingBigBlocks now:", want)
            return
        time.sleep(2)
    print("usingBigBlocks did not flip within 30 s; re-run `status` in a minute.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
