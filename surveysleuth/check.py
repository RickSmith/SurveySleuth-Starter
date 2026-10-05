"""Success check: run the 12 test addresses through the app's Nearby search and print pass or fail per address.

    python -m surveysleuth.check [--index index] [--testset testset/test-set.json]

Reads the real index and the local test set (Firm data, outside git). Never runs in CI. Exits with 1 when an
address fails. The search goes through the app's own call, which only ever sees each address and its point:
the test set's expected Jobs and distances stay here, in the check.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from surveysleuth.app import load_index, search, test_addresses


def authoritative(expected):
    """{zone, bfe, panel, parcel} that a no-Job address must show, from the test set. Its 'authoritative' line reads
    like 'FEMA flood zone X9, BFE 10 ft NAVD 88, ... (FIRM panel 48000C0000Z, effective ...). GCAD parcel ...'."""
    def find(rx):
        m = re.search(rx, expected["authoritative"])
        return m.group(1) if m else None
    return {"zone": find(r"flood zone (\w+)"), "bfe": find(r"BFE ([\d.]+) ft"),
            "panel": find(r"FIRM panel (\w+)"), "parcel": expected["parcel_id"]}


def same(k, want, got):
    if want is None or got is None:
        return False
    return float(got) == float(want) if k == "bfe" else str(got).replace(" ", "").upper() == str(want).upper()


def problems(expected, answer):
    """What is wrong with one address's search answer, as lines of text; [] when it passes."""
    listed = {j["job"] for j in answer["jobs"]}
    must, allowed = {j["job"] for j in expected["expected_jobs"]}, {j["job"] for j in expected.get("either_way_jobs", [])}
    traps = expected.get("traps", [])
    out = []
    missing = sorted(must - listed - {t["job"] for t in traps})  # a trap is reported on its own line below
    extra = sorted(listed - must - allowed)
    if missing:
        out.append("missing: " + ", ".join(missing))
    if extra:
        out.append("extra: " + ", ".join(extra))
    for t in traps:
        listed_ok = t["kind"] == "must be listed"
        if (t["job"] in listed) != listed_ok:
            out.append(f"trap {t['job']} {'not found' if listed_ok else 'listed'} ({t['why']})")
    if expected["expect_no_jobs"]:
        fema, parcel = answer.get("fema") or {}, answer.get("parcel") or {}  # the answer shape in spec #18
        got = {"zone": fema.get("zone"), "bfe": fema.get("bfe"), "panel": fema.get("panel"), "parcel": parcel.get("id")}
        for k, want in authoritative(expected).items():
            if not same(k, want, got[k]):
                name = "GCAD Parcel ID" if k == "parcel" else f"FEMA {k}"
                out.append(f"{name}: want {want}, got {got[k] if got[k] is not None else 'none'}")
    return out


def main():
    ap = argparse.ArgumentParser(description="Run the 12 test addresses and print pass or fail per address.")
    ap.add_argument("--index", default="index", type=Path, help="the index folder from ingestion")
    ap.add_argument("--testset", default="testset/test-set.json", type=Path, help="the local test set file")
    args = ap.parse_args()
    index = load_index(args.index)
    test_set = json.loads(args.testset.read_text(encoding="utf-8"))
    addresses = test_addresses(args.testset)  # what the search may see: no expected answers
    failed = 0
    for expected in test_set["addresses"]:
        status, answer = search(index, addresses, {"id": expected["id"], "r": "0.5"})
        wrong = problems(expected, answer) if status == 200 else [answer["error"]]
        failed += bool(wrong)
        print(f"{expected['id']}  {'FAIL' if wrong else 'pass'}  {len(answer.get('jobs', []))} Jobs  {expected['address']}")
        for line in wrong:
            print(f"        {line}")
    print(f"{len(test_set['addresses']) - failed} of {len(test_set['addresses'])} addresses pass.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
