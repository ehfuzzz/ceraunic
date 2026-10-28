"""Oracle adapter: signed reports, per-index windows, finalize, void (docs/SPEC.md section 9).

Revert names follow contracts/src/OracleAdapter.sol (Phase 8). Revision policy (fixed vintage):
revision 0 is the source as fetched at fetchAt; a later revision may only correct a transcription
error against the SAME vintage, so the engine rejects a revision whose vintageHash differs from
revision 0's (`VintageChanged`). The chain cannot check this (vintageHash is not signed, SPEC 9.1);
the engine can, and it is the rule that stops settlement on a later source revision.
"""
from __future__ import annotations

from .eip712 import report_digest
from .state import P, Revert, obs_key
from .units import DAY_S, check_int64


def windows(st: dict, index_id: str, day: int) -> dict:
    idx = st["indices"][index_id]
    fetch_at = (day + 1) * DAY_S + idx["fetchLag"]
    finalize_at = fetch_at + idx["disputeWindow"]
    return {"fetchAt": fetch_at, "finalizeAt": finalize_at, "voidAt": finalize_at + idx["voidGrace"]}


def check_post(st: dict, ts: int, p: dict) -> None:
    idx = st["indices"].get(p["indexId"])
    if idx is None or not idx["active"]:
        raise Revert("IndexNotActive")  # P1
    ob = st["obs"].get(obs_key(p["indexId"], p["day"]))
    if ob and ob["status"] == "final":
        raise Revert("AlreadyFinal")  # P2
    if ob and ob["status"] == "void":
        raise Revert("DayVoided")  # P2
    w = windows(st, p["indexId"], p["day"])
    if p["asOf"] < w["fetchAt"]:
        raise Revert("AsOfBeforeFetch")  # P3
    if p["asOf"] > ts:
        raise Revert("AsOfInFuture")  # P4
    if ts - p["asOf"] > P(st, "maxReportAge"):
        raise Revert("ReportStale")  # P5
    if ts >= w["finalizeAt"]:
        raise Revert("WindowClosed")  # P6
    if ob is not None and p["revision"] <= ob["revision"]:
        raise Revert("RevisionNotNewer")  # P7
    if p["revision"] < 0 or p["revision"] >= 2**16:
        raise Revert("RevisionNotNewer")
    if p["signer"] not in st["world"]["roles"]["reporters"]:
        raise Revert("BadSigner")  # P8 (sim: the engine signs for the allow-listed reporter)
    check_int64(p["value"])
    if ob is not None and p["vintageHash"] != ob["vintage0"]:
        raise Revert("VintageChanged")  # fixed-vintage policy, engine-side


def h_report_posted(st: dict, ts: int, p: dict) -> None:
    check_post(st, ts, p)
    k = obs_key(p["indexId"], p["day"])
    ob = st["obs"].get(k)
    if ob is None:
        ob = st["obs"][k] = {"status": "posted", "vintage0": p["vintageHash"], "revisions": 0}
    ob.update({"value": p["value"], "revision": p["revision"], "asOf": p["asOf"], "signer": p["signer"],
               "vintage": p["vintageHash"], "postedAt": ts})
    ob["revisions"] += 1


def h_index_finalized(st: dict, ts: int, p: dict) -> None:
    ob = st["obs"].get(obs_key(p["indexId"], p["day"]))
    w = windows(st, p["indexId"], p["day"])
    # check order = contracts/src/OracleAdapter.sol finalize()
    if ob is not None and ob["status"] == "final":
        raise Revert("AlreadyFinal")
    if ob is None or ob["status"] != "posted":
        raise Revert("NothingPosted")
    if ts < w["finalizeAt"]:
        raise Revert("TooEarly")
    if p["value"] != ob["value"]:
        raise Revert("NotLastReport")  # I11: the final is the last accepted report
    ob["status"] = "final"
    ob["finalAt"] = ts


def h_index_voided(st: dict, ts: int, p: dict) -> None:
    k = obs_key(p["indexId"], p["day"])
    if p["indexId"] not in st["indices"]:
        raise Revert("NotRegistered")
    w = windows(st, p["indexId"], p["day"])
    ob = st["obs"].get(k)
    # check order = contracts/src/OracleAdapter.sol voidDay()
    if ob is not None and ob["status"] == "void":
        raise Revert("DayVoided")
    if ob is not None:
        raise Revert("AlreadyPosted")
    if ts < w["voidAt"]:
        raise Revert("TooEarly")
    st["obs"][k] = {"status": "void", "voidAt": ts, "revision": -1, "vintage0": "", "revisions": 0}


def get_final(st: dict, index_id: str, day: int) -> int:
    ob = st["obs"].get(obs_key(index_id, day))
    if ob is None or ob["status"] != "final":
        raise Revert("NotFinal")
    return ob["value"]


def is_void(st: dict, index_id: str, day: int) -> bool:
    ob = st["obs"].get(obs_key(index_id, day))
    return ob is not None and ob["status"] == "void"


def finalized_before(st: dict, index_id: str, ts: int) -> list[tuple[int, int]]:
    """(day, value) of every final of `index_id` finalized at or before ts (point-in-time history)."""
    pre = index_id + ":"
    out = []
    for k, ob in st["obs"].items():
        if k.startswith(pre) and ob["status"] == "final" and ob["finalAt"] <= ts:
            out.append((int(k[len(pre):]), ob["value"]))
    return sorted(out)


# ---------------------------------------------------------------- commands
def post_report(led, ts: int, index_id: str, day: int, value: int, *, revision: int = 0, as_of: int | None = None,
                vintage_hash: str, signer: str | None = None) -> str:
    st = led.state
    as_of = windows(st, index_id, day)["fetchAt"] if as_of is None else as_of
    signer = signer or st["world"]["roles"]["reporters"][0]
    led.emit(ts, "ReportPosted", {"indexId": index_id, "day": day, "value": value, "revision": revision,
                                  "asOf": as_of, "signer": signer, "vintageHash": vintage_hash})
    return report_digest({"indexId": index_id, "day": day, "value": value, "revision": revision, "asOf": as_of})


def finalize(led, ts: int, index_id: str, day: int) -> int:
    ob = led.state["obs"][obs_key(index_id, day)]
    led.emit(ts, "IndexFinalized", {"indexId": index_id, "day": day, "value": ob["value"]})
    return ob["value"]


def void_day(led, ts: int, index_id: str, day: int) -> None:
    led.emit(ts, "IndexVoided", {"indexId": index_id, "day": day})
