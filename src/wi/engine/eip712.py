"""keccak ids and EIP-712 digests for the three locked type strings (docs/SPEC.md sections 1, 6.1, 9.1, 10.1).

Uses eth_utils.keccak and eth_abi.encode (both light, both pulled in by eth-account). Signing lives in
`sign_digest` and imports eth_account lazily so the reducer never needs it.
"""
from __future__ import annotations

from eth_abi import encode as abi_encode
from eth_utils import keccak

DOMAIN_TYPE = "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
QUOTE_TYPE = ("Quote(bytes32 market,address buyer,bool isLong,uint128 units,uint128 premium,uint128 fee,"
              "uint64 expiry,uint256 nonce)")
REPORT_TYPE = "Report(bytes32 indexId,uint32 day,int64 value,uint16 revision,uint64 asOf)"
RFQ_TYPE = ("RfqQuote(bytes32 requestId,bytes32 market,address maker,address taker,bool takerLong,uint8 tick,"
            "uint128 maxQty,uint64 validUntil,uint256 nonce)")

# sim sentinels (SPEC section 15): signatures made in sim never verify on a real chain
SIM_CHAIN_ID = 31337
SIM_ORACLE = "0x00000000000000000000000000000000000000a1"
SIM_POLICY = "0x00000000000000000000000000000000000000a2"

QUOTE_FIELDS = (("market", "bytes32"), ("buyer", "address"), ("isLong", "bool"), ("units", "uint128"),
                ("premium", "uint128"), ("fee", "uint128"), ("expiry", "uint64"), ("nonce", "uint256"))
REPORT_FIELDS = (("indexId", "bytes32"), ("day", "uint32"), ("value", "int64"), ("revision", "uint16"),
                 ("asOf", "uint64"))
RFQ_FIELDS = (("requestId", "bytes32"), ("market", "bytes32"), ("maker", "address"), ("taker", "address"),
              ("takerLong", "bool"), ("tick", "uint8"), ("maxQty", "uint128"), ("validUntil", "uint64"),
              ("nonce", "uint256"))


def hx(b: bytes) -> str:
    return "0x" + b.hex()


def b32(h: str) -> bytes:
    b = bytes.fromhex(h[2:] if h.startswith("0x") else h)
    if len(b) != 32:
        raise ValueError("bytes32 expected")
    return b


def keccak_text(s: str) -> str:
    return hx(keccak(text=s))


def index_id(name: str) -> str:
    """indexId = keccak256(utf8(name))."""
    return keccak_text(name)


def market_id(index_id_hex: str, day: int, lo: int, hi: int) -> str:
    """marketId = keccak256(abi.encode(bytes32 indexId, uint32 day, int64 lo, int64 hi))."""
    return hx(keccak(abi_encode(["bytes32", "uint32", "int64", "int64"], [b32(index_id_hex), day, lo, hi])))


def type_hash(type_string: str) -> bytes:
    return keccak(text=type_string)


def domain_separator(name: str, version: str, chain_id: int, verifying_contract: str) -> bytes:
    return keccak(abi_encode(["bytes32", "bytes32", "bytes32", "uint256", "address"],
                             [type_hash(DOMAIN_TYPE), keccak(text=name), keccak(text=version), chain_id,
                              verifying_contract]))


def struct_hash(type_string: str, fields: tuple, values: dict) -> bytes:
    types = ["bytes32"] + [t for _, t in fields]
    vals = [type_hash(type_string)]
    for n, t in fields:
        v = values[n]
        vals.append(b32(v) if t == "bytes32" else v)
    return keccak(abi_encode(types, vals))


def digest(domain_sep: bytes, s_hash: bytes) -> bytes:
    return keccak(b"\x19\x01" + domain_sep + s_hash)


def policy_domain(chain_id: int = SIM_CHAIN_ID, verifying: str = SIM_POLICY) -> bytes:
    return domain_separator("wi-policy", "1", chain_id, verifying)


def oracle_domain(chain_id: int = SIM_CHAIN_ID, verifying: str = SIM_ORACLE) -> bytes:
    return domain_separator("wi-oracle", "1", chain_id, verifying)


def quote_digest(q: dict, chain_id: int = SIM_CHAIN_ID, verifying: str = SIM_POLICY) -> str:
    return hx(digest(policy_domain(chain_id, verifying), struct_hash(QUOTE_TYPE, QUOTE_FIELDS, q)))


def report_digest(r: dict, chain_id: int = SIM_CHAIN_ID, verifying: str = SIM_ORACLE) -> str:
    return hx(digest(oracle_domain(chain_id, verifying), struct_hash(REPORT_TYPE, REPORT_FIELDS, r)))


def rfq_digest(q: dict, chain_id: int = SIM_CHAIN_ID, verifying: str = SIM_POLICY) -> str:
    return hx(digest(policy_domain(chain_id, verifying), struct_hash(RFQ_TYPE, RFQ_FIELDS, q)))


def sign_digest(private_key: str, digest_hex: str) -> dict:
    """ECDSA-sign a 32-byte digest (eth_account imported lazily). Returns v, r, s, signature, signer."""
    from eth_account import Account

    acct = Account.from_key(private_key)
    sig = Account.unsafe_sign_hash(b32(digest_hex), private_key)
    return {"v": sig.v, "r": "0x" + sig.r.to_bytes(32, "big").hex(), "s": "0x" + sig.s.to_bytes(32, "big").hex(),
            "signature": "0x" + bytes(sig.signature).hex(), "signer": acct.address.lower()}
