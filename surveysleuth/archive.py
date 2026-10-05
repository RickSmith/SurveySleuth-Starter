"""The archive module: build the index from the Facts read from each Record, and run a Nearby search on it.

No PDF reading, no network calls and no rendering here, so it stays fast and testable on fake data.
"""
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import PurePosixPath

from surveysleuth.gcad import Gcad, address_words, bbox_of

MILE_M = 1609.344
FT_PER_M = 3.28084
JOB_RE = re.compile(r"(\d{2}-\d{4})")
NUMBERED = r"([1-9]|[12]\d|30)"  # the old zones A1 to A30 and V1 to V30
ZONE_RE = re.compile(rf"A|AE|AH|AO|AR|A99|V|VE|B|C|X|D|A{NUMBERED}|V{NUMBERED}")


def rule(test, note):
    """A check from a yes/no test on the value."""
    return lambda v: (True, None) if test(v) else (False, note)


def zone_name(v):
    """A zone as printed, without shading words or punctuation: 'SHADED X' -> 'X', 'A-17' -> 'A17'."""
    return re.sub(r"\b(UN)?SHADED\b|[^A-Z0-9]", "", v.upper())


def zone_check(v):
    # Old names stay as printed (e.g. "C", "A17", "SHADED X"); only the check reads past the shading words.
    return (True, None) if ZONE_RE.fullmatch(zone_name(v)) else (False, "Not a FEMA zone name.")


def today_name(v):
    """Today's FEMA name for a zone as printed: A1 to A30 are AE now, V1 to V30 are VE, and B and C are X."""
    z = zone_name(v)
    return ("AE" if re.fullmatch(f"A{NUMBERED}", z) else "VE" if re.fullmatch(f"V{NUMBERED}", z) else
            "X" if z in ("B", "C") else z)


def number(v):
    """A number as printed: 11' and 9.2. are 11 and 9.2."""
    return float(v.strip().rstrip("'."))


def number_in(lo, hi):
    def test(v):
        try:
            return lo <= number(v) <= hi
        except ValueError:
            return False
    return test


def iso_date(v, job=None):
    """A date as printed (23-MAR-11, 27-SEPT-10, 23-MAR-2011, 03-23-2011, March 23, 2011 on a letter, or 2011-03-23
    from the vision model) -> '2011-03-23', or None. With its Job, only a reading in the Job's years counts, and the
    year may come first: some certificates print 11-JUN-27 for 27 June 2011."""
    s = re.sub(r"[\s,-]+", "-", re.sub(r"(\d)([A-Za-z])", r"\1-\2", v.strip())).upper()
    s = re.sub(r"([A-Z]{3})[A-Z]*", r"\1", s)  # SEPT, JULY -> SEP, JUL
    for fmt in ("%d-%b-%y", "%d-%b-%Y", "%m-%d-%Y", "%Y-%m-%d", "%b-%d-%Y") + (("%y-%b-%d",) if job else ()):
        try:
            d = datetime.strptime(s, fmt).date()
        except ValueError:
            continue
        if not job or job_year(job) - 1 <= d.year <= job_year(job) + 3:
            return d.isoformat()
    return None


CERTIFICATE = "Elevation Certificate"  # signed while its Job ran; a Survey can be years older than its Job
SURVEY = "Survey"
LETTER = "Natural Ground Letter"
SIGNED_DURING_JOB = (CERTIFICATE, LETTER)  # so their dates lie in the Job's years


def job_year(job):
    return 2000 + int(job[:2])


def date_check(v, job):
    if iso_date(v, job):
        return True, None
    return False, f"Far from its Job's year, {job_year(job)}." if iso_date(v) else "Not a date."


def parcel_check(v, gcad):
    if not re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}", v):
        return False, "Does not look like a Parcel ID."
    if v[:4] in ("0000", "9999"):
        return False, "Placeholder number, not a real parcel."
    pieces, split = gcad.pieces(v)
    if not pieces:
        return False, "Not in GCAD today: retired by a replat, or misread."
    return True, "Split since: GCAD now has only newer parcels with this number." if split else None


def degrees(text):
    n = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", text)]
    return n[0] + n[1] / 60 + n[2] / 3600 if len(n) == 3 and n[1] < 60 and n[2] < 60 else None


def latlong(v):
    """'N 29°12'36", W 94°54'18"' -> (29.21, -94.905), or None."""
    parts = v.split(",")
    if len(parts) != 2:
        return None
    lat, lon = degrees(parts[0]), degrees(parts[1])
    return None if lat is None or lon is None else (lat, -lon)


COUNTY_BOX = (29.0, -95.3, 29.65, -94.35)  # min lat, min lon, max lat, max lon around Galveston County


def in_county(p):
    # ponytail: a box around the county, GCAD's county outline if a Record ever lands in the box but outside it
    return COUNTY_BOX[0] <= p[0] <= COUNTY_BOX[2] and COUNTY_BOX[1] <= p[1] <= COUNTY_BOX[3]


def latlong_check(v):
    p = latlong(v)
    if p is None:
        return False, "Could not read a clean lat/long."
    if not in_county(p):
        return False, "Not in Galveston County."
    return True, None


height_check = rule(number_in(-5, 45), "Not a normal height.")
BASES = ("Construction drawings", "Building under construction", "Finished construction")
FLOOD_NOTES = {"in": "In the 100-year flood plain", "out": "Not in the 100-year flood plain"}  # a Survey's note 1
DRAWN = ("Building", "Easement", "Setback line")  # Drawing Facts: one Fact per label (corner marks never)

# Each Fact label the index keeps, with its simple check: value -> (ok, note). checked() adds the Job number, Date
# and Parcel ID checks, which need the Record's Job and GCAD. Any other label (an owner's name, say) is never stored.
CHECKS = {
    "Address": rule(lambda v: re.search(r"[A-Za-z]{2}", v), "Not an address."),
    "Lot and block": rule(str.strip, "No text."),
    "Lat/long": latlong_check,
    "Flood zone": zone_check,
    "BFE": rule(number_in(0, 40), "Not a normal BFE."),
    "FIRM panel": rule(lambda v: re.fullmatch(r"\d{6} \d{4} [A-Z](, .+)?", v), "Not a FIRM panel number."),
    "Basis": rule(lambda v: v in BASES, "Could not read the C1 tick boxes."),
    "Top of bottom floor": height_check,
    "Lowest structural member": height_check,
    "Lowest adjacent grade": height_check,
    "Highest adjacent grade": height_check,
    "Benchmark": rule(lambda v: re.fullmatch(r"[A-Za-z0-9 .,#/()+:-]{2,120}", v), "Garbled text."),  # letters describe it
    "Flood note": rule(lambda v: v in FLOOD_NOTES.values(), "Not a flood note."),
    "Natural ground": height_check,
    "Recorded Plat": rule(lambda v: re.fullmatch(r"Volume \S+, Page \d+(\.\d+)?(-?A)?(, .+ County)?", v), "Not a volume and page."),
    **{label: rule(str.strip, "No text.") for label in DRAWN},
}


def checked(facts, job, gcad, kind):
    """The printed Job number is a check only: it must match the Job number from the file name."""
    checks = {**CHECKS, "Job number": rule(lambda v: v.startswith(job), f"The file name says {job}."),
              "Date": lambda v: date_check(v, job) if kind in SIGNED_DURING_JOB else rule(iso_date, "Not a date.")(v),
              "Parcel ID": lambda v: parcel_check(v, gcad)}
    out = []
    for f in facts:
        check = checks.get(f["label"])
        if check:
            ok, note = check(f["value"])
            out.append({**f, "ok": ok, "note": note})
    return out


def passed(facts, label):
    """The value of the first Fact with this label that passed its check, or None."""
    return next((f["value"] for f in facts if f["label"] == label and f["ok"]), None)


def plat_of(facts):
    """The volume_page of the Galveston County Recorded Plat a Survey cites, as plats.py names it ('Volume 31-A, Page 5'
    -> '31A_5', 'Volume 7, Page 16-A' -> '7_16A'), or None; another county's plat ('..., Sample County') never has one."""
    m = re.fullmatch(r"Volume (\S+), Page (\d+(?:\.\d+)?)(-?A)?", passed(facts, "Recorded Plat") or "")
    return m and f"{m.group(1).replace('-', '').upper()}_{m.group(2)}{'A' if m.group(3) else ''}"


def build_index(records, parcels=(), overrides=None, census_geocoder=None, fema=None, ngs=(), plats=()):
    """records: [{file, kind, facts: [{label, value, page, read_by}], pages, photo_page}], file relative to the Legacy
    archive folder; pages, photo_page and photo (a building photo thumbnail was saved) come from the page images
    drawn at ingestion.
    parcels: GCAD parcels [{id, situs, legal, acres, centre: [lat, lon], shape: [ring of [lat, lon], ...]}].
    overrides: the overrides file, {Record id: {lat, lon, why}}: Records placed by hand.
    census_geocoder: address -> (lat, lon) or None, asked only when GCAD has no such address.
    fema: the saved FEMA NFHL, {zones: [{zone, bfe, shape}], panels: [{panel, date, shape}]}.
    ngs: the saved NGS vertical Benchmarks, [{id, name, lat, lon, height_ft}].
    plats: the volume_page of every Recorded Plat held; a Survey citing one links to it (its "plat").
    Returns (index, ingestion report). The index holds everything Nearby search reads."""
    gcad = Gcad(parcels)
    overrides = overrides or {}
    out, report = [], {"skipped": {}, "not_located": [], "bad_overrides": []}
    for r in records:
        name = r["file"].replace("\\", "/").rsplit("/", 1)[-1]
        job = JOB_RE.match(name)
        if not job:
            report["skipped"].setdefault("no Job number in the file name", []).append(r["file"])
            continue
        facts = checked(r["facts"], job.group(1), gcad, r["kind"])
        override = overrides.get(r["file"])
        if override and in_county((override["lat"], override["lon"])):
            location, flags = located((override["lat"], override["lon"]), "placed by hand"), []
        else:
            if override:
                report["bad_overrides"].append({"id": r["file"], "reason": "Not in Galveston County."})
            location, flags = place(facts, gcad, census_geocoder)
        if r["kind"] == SURVEY and not legal_agrees(facts, gcad):
            flags.append("Lot and block differ from GCAD's legal description for its Parcel ID.")
            lot_and_block = next(f for f in facts if f["label"] == "Lot and block")
            lot_and_block.update(ok=False, note="Differs from GCAD's legal description.")
        printed_job = next((f["value"] for f in facts if f["label"] == "Job number" and not f["ok"]), None)
        if printed_job:
            flags.append(f"Printed JOB No. {printed_job}; the file name says {job.group(1)}.")
        date, plat = passed(facts, "Date"), plat_of(facts)
        out.append({"id": r["file"], "job": job.group(1), "kind": r["kind"], "date": date and iso_date(date, job.group(1) if r["kind"] in SIGNED_DURING_JOB else None),
                    "facts": facts, "location": location, "flags": flags, "plat": plat if plat in plats else None,
                    "pages": r.get("pages"), "photo_page": r.get("photo_page"), "photo": r.get("photo")})  # for the viewer
    by_job = {}
    for r in out:
        by_job.setdefault(r["job"], []).append(r)
    for recs in by_job.values():  # Rule 4: a Record nothing else places takes its Job's Location
        placed = [r for r in recs if r["location"]]
        spread = max((metres(point_of(a), point_of(b)) for a in placed for b in placed), default=0)
        source = [r for r in placed if r["kind"] == CERTIFICATE] or [r for r in placed if r["kind"] == SURVEY]
        for r in recs:
            if r["location"]:
                continue
            if source and spread <= 300:
                r["location"] = located(point_of(source[0]), "placed by its Job")
                printed = passed(r["facts"], "Lat/long")
                off = metres(latlong(printed), point_of(r)) if printed else 0
                if off > 100:
                    r["flags"].append(f"Printed lat/long is {distance_text(off)} off. Placed by its Job.")
            else:
                job_note = ("Its Job's other Records are more than 300 m apart." if source else
                            "Its Job has no placed certificate or Survey." if placed else "Its Job has no other placed Records.")
                report["not_located"].append({"id": r["id"], "reason": no_place_reason(r["facts"], job_note)})
    ids = {r["id"] for r in out}
    report["bad_overrides"] += [{"id": i, "reason": "No such Record."} for i in overrides if i not in ids]
    report["flagged"] = [{"id": r["id"], "flags": r["flags"]} for r in out if r["flags"]]
    citing = [(r, cited) for r in out if (cited := passed(r["facts"], "Recorded Plat"))]
    report["plat_citations"] = {"citing": len(citing), "found": sum(1 for r, _ in citing if r["plat"]),
                                "not_held": [{"id": r["id"], "plat": cited} for r, cited in citing if not r["plat"]]}
    counts = {"jobs": len({r["job"] for r in out}), "records": len(out),
              "kinds": dict(Counter(r["kind"] for r in out))}
    fema = fema or {"zones": [], "panels": []}
    return {"records": out, "counts": counts, "gcad": gcad, "fema": fema, "ngs": list(ngs)}, report


NUMBER_WORDS = {w: i for i, w in enumerate("ZERO ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE TEN ELEVEN TWELVE "
                                           "THIRTEEN FOURTEEN FIFTEEN SIXTEEN SEVENTEEN EIGHTEEN NINETEEN".split())}
TENS = {"TWENTY": 20, "THIRTY": 30, "FORTY": 40, "FIFTY": 50, "SIXTY": 60, "SEVENTY": 70, "EIGHTY": 80, "NINETY": 90}


def plain_legal(t):
    """Upper case, no apostrophes, number words as digits ('Thirty-Seven' -> 37), no leading zeros."""
    t = re.sub(r"\b(" + "|".join(TENS) + r")(?:[- ](ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE)\b)?",
               lambda m: str(TENS[m.group(1)] + NUMBER_WORDS.get(m.group(2), 0)), t.upper().replace("'", ""))
    t = re.sub(r"\b[A-Z]+\b", lambda m: str(NUMBER_WORDS.get(m.group(0), m.group(0))), t)
    return re.sub(r"\b0+(\d)", r"\1", t)


def survey_lots_and_blocks(text):
    """({lots}, {blocks}) in a Survey's 'Lots 3, 4, Block 9 (9), Subdivision': lots run until an item with no number."""
    lots, after_lot = set(), re.search(r"\bLOTS?\b(.*?)(?=\bBLOCK\b|\bBLK\b|$)", text)
    for item in (after_lot.group(1) if after_lot else "").split(","):
        found = re.findall(r"\b(\d+[A-Z]?|[A-Z])\b", item.replace("LOT", ""))
        if not found:
            break
        lots |= set(found)
    blocks = set()
    for part in re.findall(r"\b(?:BLOCK|BLK)\b([^,]*)", text):  # every Block part: "Nine (9)" -> 9, "141 and 142", "B"
        blocks |= set(re.findall(r"\((\d+)\)", part) or re.findall(r"\d+", part) or re.findall(r"\b([A-Z])\b", part))
    return lots, blocks


def same_lot(ours, theirs):
    """Lot 15 is lot 15A replatted since (a parcel change, not an error); 18A and 18C are different lots."""
    if ours == theirs:
        return True
    base_ours, base_theirs = re.match(r"\d*", ours).group(), re.match(r"\d*", theirs).group()
    return bool(base_ours) and base_ours == base_theirs and (ours == base_ours or theirs == base_theirs)


def gcad_lots_and_blocks(legal):
    """({lots}, {blocks}) in a GCAD legal description: only numbers right after LOT or LOTS count (with ranges like
    '1 THRU 4'), not footages like 'E 37-6 FT', shares like '1/2' or acres like '0.2'."""
    lots = set(re.findall(r"\bLOTS?\s+([A-Z])\b", legal))
    for part in re.findall(r"\bLOTS?\b(.*?)(?=\b(?:BLK|BLOCK|ACRES?|ACRS|ABST|SEC|SECTION)\b|$)", legal):
        lots |= set(re.findall(r"(?<![\w./-])(\d+[A-Z]?)(?![\w./]|-\d|\s+FT)", part))
        for a, b in re.findall(r"(\d+)\s+THRU\s+(\d+)", part):
            lots |= {str(n) for n in range(int(a), int(b) + 1)}
    return lots, set(re.findall(r"\b(?:BLK|BLOCK)\s+(\d+[A-Z]?|[A-Z])\b", legal))


def legal_agrees(facts, gcad):
    """Does a Survey's lot and block agree with the GCAD legal description of its Parcel ID? Only what both give is
    compared. True when there is nothing to compare: no lot or block, or no exact Parcel ID (a split parcel's lots
    changed)."""
    ours, (pieces, split) = passed(facts, "Lot and block"), gcad.pieces(passed(facts, "Parcel ID"))
    if not ours or not pieces or split:
        return True
    lots, blocks = survey_lots_and_blocks(plain_legal(ours))
    gcad_lots, gcad_blocks = gcad_lots_and_blocks(plain_legal(" ".join(p["legal"] for p in pieces)))
    lot_ok = not lots or not gcad_lots or any(same_lot(a, b) for a in lots for b in gcad_lots)
    block_ok = not blocks or not gcad_blocks or bool(blocks & gcad_blocks)
    return lot_ok and block_ok


def pages_dir(index_dir, record_id):
    """Where the index keeps a Record's page images: index/pages/<its path in the archive, without .pdf>/."""
    return index_dir / "pages" / PurePosixPath(record_id).with_suffix("")


def point_of(r):
    return r["location"]["lat"], r["location"]["lon"]


def located(point, found_by):
    return {"lat": round(point[0], 7), "lon": round(point[1], 7), "found_by": found_by}


def centre(parcels):
    """The centre of several parcels together, each weighted by its acres."""
    weights = [p["acres"] for p in parcels] if all(p["acres"] > 0 for p in parcels) else [1] * len(parcels)
    return [sum(w * p["centre"][i] for w, p in zip(weights, parcels)) / sum(weights) for i in (0, 1)]


def place(facts, gcad, census_geocoder):
    """(Location, flags) for a Record by rules 1 to 3 of issue #9: the first rule that works wins.
    Rule 4 (its Job) and rule 5 (by hand, else the ingestion report) are in build_index."""
    printed = passed(facts, "Lat/long")
    printed = printed and latlong(printed)
    pieces, split = gcad.pieces(passed(facts, "Parcel ID"))
    address = passed(facts, "Address")
    at_address = gcad.at_address(address) if address else []
    census = census_geocoder(address) if census_geocoder and address and not pieces and not at_address else None
    census = census if census and in_county(census) else None

    def near(parcels):
        return parcels and min(metres_outside(printed, p["shape"]) for p in parcels) <= 100
    # Rule 1: the printed lat/long, checked against its parcel by Parcel ID, else by address. Never trusted blindly.
    if printed and near(pieces):
        return located(printed, "certificate lat/long, checked by Parcel ID"), []
    if printed and near(at_address):  # two sources agree, so a far Parcel ID is the typo
        flags = []
        if pieces:
            off = distance_text(metres(printed, centre(pieces)))
            flags.append(f"Parcel ID points to a parcel {off} away. The lat/long and address agree.")
            parcel_id = next(f for f in facts if f["label"] == "Parcel ID" and f["ok"])
            parcel_id.update(ok=False, note=f"Points to a parcel {off} from the lat/long and address.")
        return located(printed, "certificate lat/long, checked by address"), flags
    if printed and census and metres(printed, census) <= 100:
        return located(printed, "certificate lat/long, checked by address (Census Geocoder)"), []
    # Rule 2: Parcel ID -> GCAD parcel centre. Rule 3: street address -> GCAD situs, else the Census Geocoder.
    if pieces:
        point, by = centre(pieces), "Parcel ID"
    elif at_address:
        point, by = centre(at_address), "address (GCAD)"
    elif census:
        point, by = census, "address (Census Geocoder)"
    else:
        return None, []
    flags = ["Parcel split since this Record. Placed at the centre of its pieces."] if split else []
    if printed:
        flags.insert(0, f"Printed lat/long is {distance_text(metres(printed, point))} off. Placed by {by}.")
    return located(point, f"placed by {by}" + (", since split" if split else "")), flags


def distance_text(m):
    return f"{m / 1000:.1f} km" if m >= 1000 else f"{m:.0f} m"


def no_place_reason(facts, job_note):
    why = []
    for label, name in (("Lat/long", "lat/long"), ("Parcel ID", "Parcel ID"), ("Address", "address")):
        f = next((f for f in facts if f["label"] == label), None)
        why.append(f"No {name}." if not f else f"{label}: {f['note']}" if not f["ok"] else
                   "Lat/long could not be checked against a parcel or address." if label == "Lat/long" else
                   f"{label} not found.")
    return " ".join(why + [job_note])


M_PER_DEG = 111195.08  # metres in one degree of latitude on the mean Earth


def metres_outside(point, shape):
    """0 when point (lat, lon) lies inside the parcel shape, else metres to its nearest edge."""
    def xy(q):  # metres east and north of point; flat Earth is fine within a few km
        return (q[1] - point[1]) * M_PER_DEG * math.cos(math.radians(point[0])), (q[0] - point[0]) * M_PER_DEG

    inside, nearest = False, math.inf
    for ring in shape:
        pts = [xy(q) for q in ring]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if (y0 > 0) != (y1 > 0) and x0 - y0 * (x1 - x0) / (y1 - y0) > 0:  # edge crosses the ray east of point
                inside = not inside
            dx, dy = x1 - x0, y1 - y0
            t = max(0, min(1, -(x0 * dx + y0 * dy) / (dx * dx + dy * dy or 1)))
            nearest = min(nearest, math.hypot(x0 + t * dx, y0 + t * dy))
    return 0 if inside else nearest


def metres(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(h))


def nearby_search(index, point, distance_mi, parcel_id=None):
    """The search answer for point (lat, lon): Jobs with any Record's Location within distance_mi, nearest first,
    then by Job number, and the Authoritative-source Facts at the point. No network calls."""
    def away(r):
        return metres(point, (r["location"]["lat"], r["location"]["lon"])) if r["location"] else math.inf

    by_job = {}
    for r in index["records"]:
        by_job.setdefault(r["job"], []).append(r)
    found, outside = [], (math.inf, None, None)
    for job, recs in by_job.items():
        recs = sorted(recs, key=away)  # nearest Record first
        d = away(recs[0])
        if d <= distance_mi * MILE_M:
            found.append((d, job, recs))
        elif d < math.inf and (outside[1] is None or (d, job) < outside[:2]):
            outside = (d, job, recs[0])
    found.sort(key=lambda x: (x[0], x[1]))
    gcad = index["gcad"]
    pieces = gcad.pieces(parcel_id)[0] if parcel_id else []
    at = pieces[0] if pieces else holding(gcad.parcels, point)
    home = gcad.by_id[at["id"]] if at else []  # every shape of the searched parcel
    jobs = [{"rank": rank, "job": job, "distance_ft": round(d * FT_PER_M),
             "address": address_of(recs, gcad), "relation": relation(recs, home, gcad),
             "kinds": sorted({r["kind"] for r in recs}), "flags": list(dict.fromkeys(f for r in recs for f in r["flags"])),
             "pins": pins(recs), "records": recs}
            for rank, (d, job, recs) in enumerate(found, 1)]
    zone, panel = holding(index["fema"]["zones"], point), holding(index["fema"]["panels"], point)
    fema = {"zone": zone and zone["zone"], "bfe": zone and zone["bfe"],
            "panel": panel and panel["panel"], "panel_date": panel and panel["date"]}
    parcel = at and {k: at[k] for k in ("id", "situs", "legal", "acres")}
    query = {"point": list(point), "distance_mi": distance_mi, "parcel_id": parcel_id or (parcel and parcel["id"])}
    benchmark = min(index["ngs"], key=lambda b: metres(point, (b["lat"], b["lon"])), default=None)
    ngs = benchmark and {k: benchmark[k] for k in ("id", "name", "height_ft", "lat", "lon")}
    if ngs:
        ngs["distance_ft"] = round(metres(point, (ngs["lat"], ngs["lon"])) * FT_PER_M)
    answer = {"query": query, "jobs": jobs, "parcel": parcel, "fema": fema, "ngs": ngs,
              "plats": plats_holding(index.get("plats", {}), at and at["id"]),
              "counts": {"jobs": len(jobs), "records": sum(len(j["records"]) for j in jobs)}}
    d, job, rec = outside
    if not jobs and job:
        answer["nearest_outside"] = {"job": job, "distance_ft": round(d * FT_PER_M), "reaches_at_2_mi": d <= 2 * MILE_M,
                                     "lat": rec["location"]["lat"], "lon": rec["location"]["lon"]}
    answer["summary"] = summarize(answer, home, gcad)
    return answer


def plats_holding(plats, parcel_id):
    """The Recorded Plats whose placed area (GCAD Parcel IDs, see plats.py) holds the searched parcel, newest first;
    only those with a page image, so each can be shown."""
    if not parcel_id:
        return []
    found = []
    for volume_page, p in plats.items():
        if parcel_id in p.get("area", ()) and p.get("image"):
            r = p["reading"]
            volume, page = volume_page.split("_", 1)
            found.append({"id": volume_page, "volume": volume, "page": page, "date": r["date"], "kind": r["kind"],
                          "name": " ".join(x for x in (r["name"], r["section"]) if x)})
    return sorted(found, key=lambda x: x["date"] or "", reverse=True)


RELATIONS = ("same parcel", "next door", "same block", "same subdivision", "nearby")


def apart(a, b):
    """Metres between two parcels, 0 when they touch: each one's corners against the other's edges."""
    return min(metres_outside(q, y["shape"]) for x, y in ((a, b), (b, a)) for ring in x["shape"] for q in ring)


def relation(recs, home, gcad):
    """How a Job lies to the searched parcel (home: its shapes): the closest relation any of its Records has.
    A Record's parcels are its Parcel ID's and its address's (a printed address can name the searched parcel when the
    Parcel ID is a neighbor's); with neither, it is on the same parcel when its Location lies inside it.
    A Parcel ID reads subdivision-block-lot-piece, so a shared start means the same block or subdivision."""
    if not home:
        return "nearby"
    hid, closest = home[0]["id"], len(RELATIONS) - 1
    for r in recs:
        pid, address = passed(r["facts"], "Parcel ID"), passed(r["facts"], "Address")
        theirs = gcad.pieces(pid)[0] + (gcad.at_address(address) if address else [])
        inside = not theirs and r["location"] and any(metres_outside(point_of(r), h["shape"]) == 0 for h in home)
        if inside or any(p["id"] == hid for p in theirs):  # a parcel split since includes its piece we searched
            return "same parcel"
        for p in theirs:
            closest = min(closest, 1 if any(apart(p, h) <= 2 for h in home) else
                          2 if hid[5:9] != "0000" and p["id"][:9] == hid[:9] else 3 if p["id"][:4] == hid[:4] else 4)
    return RELATIONS[closest]


# ------------------------------------------------------------ the Search summary

AUTHORITIES = {"FEMA": "FEMA National Flood Hazard Layer", "NGS": "NGS Benchmarks", "GCAD": "Galveston CAD parcels"}
MILES = {0.25: "¼ mi", 0.5: "½ mi", 1: "1 mi", 2: "2 mi"}
HEIGHTS = ("Lowest adjacent grade", "Top of bottom floor", "Lowest structural member", "Natural ground")


def feet_text(ft):
    return f"{ft:,} ft" if ft < 5280 else f"{ft / 5280:.2f} mi"


def month_year(iso):
    return datetime.fromisoformat(iso).strftime("%b %Y") if iso else "no date"


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def stage(r):
    """Newest stage first: finished construction beats construction drawings; then the newest date."""
    basis = passed(r["facts"], "Basis")
    return BASES.index(basis) if basis else -1, r["date"] or ""


def newest_stage(certs):
    """The (Job, Record) of a building's newest stage, from [(Job, Record)] at one address. A certificate dated after
    the finished one is for a new building there (a rebuild), so only those count then."""
    finished = max((r["date"] for _, r in certs if r["date"] and passed(r["facts"], "Basis") == BASES[-1]), default=None)
    rebuilt = [(j, r) for j, r in certs if finished and (r["date"] or "") > finished]
    return max(rebuilt or certs, key=lambda x: stage(x[1]))


def buildings(jobs, point):
    """[(Job, Record, feet from point)], nearest first: each Natural Ground Letter, and the newest stage of each
    building's Elevation Certificates. A building is a street address: one parcel can hold many buildings, and one
    building's certificates (drawings, then construction, then finished) can be in one Job or several."""
    at_address = {}
    for j in jobs:
        for r in j["records"]:
            if r["kind"] in (CERTIFICATE, LETTER) and r["location"]:
                address = r["kind"] == CERTIFICATE and passed(r["facts"], "Address")
                key = " ".join(address_words(address.partition(",")[0])) if address else r["id"]
                at_address.setdefault(key, []).append((j, r))
    return sorted(((j, r, round(metres(point, point_of(r)) * FT_PER_M)) for j, r in map(newest_stage, at_address.values())),
                  key=lambda x: x[2])


def drawing_text(r):
    """A Survey's Drawing Facts, as printed: 'buildings “House”, “Shed”; setback line “20' B.L.”', or ''."""
    parts = []
    for label in DRAWN:
        values = [f["value"] for f in r["facts"] if f["label"] == label and f["ok"]]
        if values:
            parts.append(f"{label.lower()}{'s' if len(values) > 1 else ''} " + ", ".join(f"“{x}”" for x in values))
    return "; ".join(parts)


def summarize(answer, home, gcad):
    """The Search summary: advice, then findings under fixed headings, written by fixed rules (no AI) from Facts
    that passed their checks. Every claim cites a Source as [n]; sources lists only the cited ones, numbered in
    reading order."""
    sources, numbers = [], {}

    def cite(key, source):
        if key not in numbers:
            numbers[key] = len(sources) + 1
            sources.append({"n": numbers[key], **source})
        return f"[{numbers[key]}]"

    def record(r):
        return cite(r["id"], {"record": r["id"], "job": r["job"], "kind": r["kind"], "date": r["date"]})

    def authority(name, parcels=None):  # parcels: the GCAD parcels behind one claim, for its popup
        source = {"source": name, "label": AUTHORITIES[name]}
        return cite((name, *parcels), {**source, "parcels": parcels}) if parcels else cite(name, source)

    def lead(j):  # the Record to cite for a whole Job: its Survey, else its nearest Record
        return next((r for r in j["records"] if r["kind"] == SURVEY), j["records"][0])

    def where(r, ft):  # of one Record: a Job can have Records in many places
        return "on this parcel" if relation([r], home, gcad) == "same parcel" else f"{feet_text(ft)} away"

    jobs, fema, ngs, parcel = answer["jobs"], answer["fema"], answer["ngs"], answer["parcel"]
    within = MILES.get(answer["query"]["distance_mi"], f"{answer['query']['distance_mi']:g} mi")
    near = {k: [j for j in jobs if j["relation"] == k] for k in RELATIONS}
    same, surveyed = near["same parcel"], [j for j in jobs if SURVEY in j["kinds"]]

    if jobs:  # this parcel's Job first, else the nearest Survey, else the nearest Job
        j = (same or surveyed or jobs)[0]
        what = f"Survey {j['job']}" if SURVEY in j["kinds"] else f"Job {j['job']}'s Records"
        advice = (f"Get {what} before you quote {record(lead(j))}. The Firm has already worked on this parcel." if same
                  else f"Get {what}, {feet_text(j['distance_ft'])} away, before you quote {record(lead(j))}.")
    else:
        advice = f"The Firm has no Jobs within {within}. Quote from scratch; the flood, Benchmark and parcel findings below still help."

    text = "No earlier Job on this parcel."
    if same:
        jobs_here = [f"Job {j['job']}: " + "; ".join(f"{r['kind']}, {month_year(r['date'])} {record(r)}" for r in j["records"][:3])
                     for j in same[:2]]
        flagged = {}  # each conflict flag on these Records, with every Record that carries it
        for r in (r for j in same[:2] for r in j["records"]):
            for f in r["flags"]:
                flagged.setdefault(f, []).append(r)
        flags = [f"Flag: {f.rstrip('.')} {' '.join(record(r) for r in rs)}." for f, rs in list(flagged.items())[:2]]
        head = "The Firm has worked on this parcel before." if len(same) == 1 else f"The Firm has {len(same)} Jobs on this parcel."
        surveys = [r for j in same for r in j["records"] if drawing_text(r) and relation([r], home, gcad) == "same parcel"]
        newest = max(surveys, key=lambda r: r["date"] or "", default=None)
        drawn = [f"Survey {newest['job']} ({month_year(newest['date'])}) shows {drawing_text(newest)} {record(newest)}."] if newest else []
        text = " ".join([head, ". ".join(jobs_here) + ".", *drawn, *flags])
    findings = [("Same parcel", text)]

    def group(js, place):
        j = js[0]
        who = f"Job {j['job']} is {place}" if len(js) == 1 else f"{len(js)} Jobs are {place}; the nearest is {j['job']}"
        shows = drawing_text(lead(j))
        return f"{who}, {feet_text(j['distance_ft'])} away{f'; its Survey shows {shows}' if shows else ''} {record(lead(j))}."
    s = [group(near[k], place) for k, place in (("next door", "next door"), ("same block", "on the same block"),
                                                ("same subdivision", "in the same subdivision")) if near[k]]
    if near["nearby"]:
        s.append(group(near["nearby"], f"{'elsewhere ' if s else ''}within {within}"))
    findings.append(("Neighbors", " ".join(s) or (f"No other Jobs within {within}." if jobs else f"The Firm has no Jobs within {within}.")))

    built = [(j, r, where(r, ft)) for j, r, ft in buildings(jobs, answer["query"]["point"])]
    s = []
    zoned = [x for x in built if passed(x[1]["facts"], "Flood zone")]
    then = next((x for x in zoned if x[2] == "on this parcel"), zoned[0] if zoned else None)
    if then:
        j, r, place = then
        zone, bfe = passed(r["facts"], "Flood zone"), passed(r["facts"], "BFE")
        renamed = f" (called {today_name(zone)} today)" if today_name(zone) != zone_name(zone) else ""
        s.append(f"Job {j['job']}'s {r['kind']} {place} ({month_year(r['date'])}) shows Zone {zone}{renamed}"
                 f"{f', BFE {number(bfe):g} ft' if bfe else ''} {record(r)}.")
    if fema["zone"]:
        bfe = f", BFE {fema['bfe']:g} ft" if fema["bfe"] is not None else ""
        panel = f", panel {fema['panel']}" if fema["panel"] else ""
        if fema["panel"] and fema["panel_date"]:
            d = datetime.fromisoformat(fema["panel_date"])
            panel += f", effective {d:%b} {d.day}, {d.year}"
        s.append(f"FEMA's map today shows Zone {fema['zone']}{bfe}{panel} {authority('FEMA')}.")
        if then and then[2] == "on this parcel" and today_name(zone) != fema["zone"]:
            s.append(f"The zone has changed since our Record {record(then[1])} {authority('FEMA')}.")
    else:
        s.append(f"The saved FEMA flood map has no zone at this point {authority('FEMA')}.")
    findings.append(("Flood then and now", " ".join(s)))

    rows = []
    for j, r, place in built:
        v_zone = today_name(passed(r["facts"], "Flood zone") or "").startswith("V")
        heights = [(k, passed(r["facts"], k)) for k in HEIGHTS if k != "Lowest structural member" or v_zone]
        if any(v for _, v in heights):
            rows.append((j, r, place, heights))
    s = []
    for j, r, place, heights in rows[:3]:
        basis = passed(r["facts"], "Basis")
        s.append(f"Job {j['job']}, {place}{', ' + basis.lower() if basis else ''}: "
                 + ", ".join(f"{k.lower()} {number(v):g} ft" for k, v in heights if v) + f" {record(r)}.")
    findings.append(("Ground and floor heights",
                     " ".join(s) or "No nearby Elevation Certificate or Natural Ground Letter has checked heights."))

    used = {}  # each Benchmark our nearby Jobs used, nearest use first
    for j in jobs:
        for r in j["records"]:
            b = passed(r["facts"], "Benchmark")
            if b:
                used.setdefault(re.sub(r"[^A-Z0-9]", "", b.upper()), []).append((j, r))  # TBM-7 is TBM 7
    top = sorted(used.values(), key=lambda uses: -len({j["job"] for j, _ in uses}))[:2]
    s = []
    if top:
        named = [f"“{passed(uses[0][1]['facts'], 'Benchmark')}” ({plural(len({j['job'] for j, _ in uses}), 'Job')}) "
                 f"{record(uses[0][1])}" for uses in top]  # as printed on its nearest use
        s.append(f"Our nearby Jobs carried elevations from {' and '.join(named)}.")
    if ngs:
        s.append(f"The nearest NGS Benchmark is {ngs['id']} “{ngs['name']}”, {feet_text(ngs['distance_ft'])} away, "
                 f"height {ngs['height_ft']:.2f} ft {authority('NGS')}.")
    findings.append(("Benchmarks", " ".join(s) or "No Benchmark found nearby."))

    splits = {}  # each parcel on our Records that GCAD has split or renumbered since, closest Job first
    for j in sorted(jobs, key=lambda j: RELATIONS.index(j["relation"])):
        for r in j["records"]:
            pid = passed(r["facts"], "Parcel ID")
            pieces, split = gcad.pieces(pid)
            if split and pid not in splits:
                splits[pid] = (j, r, sorted({p["id"] for p in pieces}))
    s = [f"Parcel {pid} on Job {j['job']}'s {r['kind']} ({month_year(r['date'])}) has been "
         f"{f'split since, into {len(ids)} parcels' if len(ids) > 1 else f'renumbered since, to {ids[0]}'} "
         f"{record(r)} {authority('GCAD', ids)}." for pid, (j, r, ids) in list(splits.items())[:2]]
    if jobs and not splits:
        s.append(f"None of the parcels on our nearby Records has been split or renumbered since {authority('GCAD')}.")
    if parcel:
        legal = f" ({parcel['legal']})" if parcel["legal"] else ""
        s.append(f"GCAD today: parcel {parcel['id']}{legal}, {parcel['acres']:g} acres {authority('GCAD')}.")
    findings.append(("Parcel changes", " ".join(s) or "No GCAD parcel holds this point."))

    def plat(p):  # a Recorded Plat holding the address, cited as an Authoritative source
        year = re.match(r"\d{4}", p["date"] or "")
        volume_page = f"Volume {p['volume']}, Page {p['page']}"
        n = cite(("plat", p["id"]), {"source": "Recorded Plat", "plat": p["id"],
                                     "label": f"{volume_page}: {p['name']}" if p["name"] else volume_page})
        return (f"{p['name'] or 'a subdivision whose name was not read'}{' (a replat)' if p['kind'] == 'replat' else ''}, "
                f"{volume_page}{f', recorded {year[0]}' if year else ''} {n}")
    findings.append(("Recorded Plats", f"This address lies in {', and in '.join(map(plat, answer['plats']))}."
                     if answer["plats"] else "No placed Recorded Plat holds this address." if parcel  # an area is parcels
                     else "No GCAD parcel holds this point, so no Recorded Plat can be matched to it."))
    return {"advice": advice, "findings": [{"heading": h, "text": t} for h, t in findings], "sources": sources}


def address_of(recs, gcad):
    """A Job's address: a printed address on its Records (nearest first), else the GCAD situs of a Record's Parcel ID,
    since Surveys have no address line (decision #7)."""
    printed = next(filter(None, (passed(r["facts"], "Address") for r in recs)), None)
    if printed:
        return printed
    for r in recs:
        pieces, split = gcad.pieces(passed(r["facts"], "Parcel ID"))
        if pieces and not split and pieces[0]["situs"]:
            return pieces[0]["situs"]
    return None


def holding(items, point):
    """The first saved polygon (a FEMA zone, a FIRM panel, a parcel) that holds the point, or None.
    Saved data carries a bbox, so only the polygons near the point get the full test."""
    lat, lon = point
    for x in items:
        b = x.get("bbox") or bbox_of(x["shape"])
        if b[0] <= lat <= b[2] and b[1] <= lon <= b[3] and metres_outside(point, x["shape"]) == 0:
            return x
    return None


def pins(recs):
    """One pin per place of a Job: a Record within 50 m of a pin shares it."""
    out = []
    for r in recs:
        if r["location"]:
            pin = next((p for p in out if metres((p["lat"], p["lon"]), point_of(r)) <= 50), None)
            if pin:
                pin["records"].append(r["id"])
            else:
                out.append({"lat": r["location"]["lat"], "lon": r["location"]["lon"], "records": [r["id"]]})
    return out
