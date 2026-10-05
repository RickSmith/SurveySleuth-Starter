"""Ingestion: turn a Legacy archive folder into an index folder.

    python -m surveysleuth.ingest ARCHIVE_FOLDER INDEX_FOLDER --parcels parcels.zip [--overrides overrides.json]
                                  [--model qwen3.6:35b]

Reads only the certificate folder (EL_GAL_Data), the Survey folder (SUR_GAL_Data) and plat group folders (named like
"Galveston County Plats Group 1"); a file in any other folder, or at the top of the archive folder, is skipped unread
and counted under a reason that names its folder. A plat group folder holds the county's Recorded Plats: each is known
by the volume and page in its file name, gets a page image (pages/plats/<volume_page>.png), is read by the vision
model and is placed on the area of its GCAD parcels when the rules allow (see plats.py).
Reads typed Elevation Certificates from their text layer (page 1). The local vision model reads every Record in the
Survey folder (and a Survey's drawing a second time, for its buildings, easements and setback lines) and every other
certificate-folder Record: a scanned page with no text layer or a garbled one, and a Natural Ground Letter (its
answers are saved in vision.jsonl, so a re-run asks only about new or changed Records and Recorded Plats: a first
run over a plat group reads for hours, and can be stopped and run again).
Counts every file it skips. Gives each Record its Location from the GCAD parcels, the overrides file ({Record id: {lat,
lon, why}}) and, when online, the Census Geocoder. Saves the county's FEMA flood zones and NGS Benchmarks once
(fema.json, ngs.json: delete one to fetch it again). Writes index.json, parcels.json and report.json (the
ingestion report) into the index folder. Needs Poppler (pdftotext, pdffonts, pdftoppm) on PATH, Ollama with
qwen3.6:35b and Pillow. Never writes into the archive folder.
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from surveysleuth.archive import CERTIFICATE, SURVEY, build_index, pages_dir
from surveysleuth.gcad import read_parcels
from surveysleuth.plats import PLAT_READING, PlatAreas, draw_plat, recorded_plats
from surveysleuth.sources import census_geocoder, fetch_fema, fetch_ngs
from surveysleuth.vision import (CERTIFICATE_READING, DRAWING_READING, MODEL, SURVEY_READING, Answers, certificate_record,
                                 draw_pages, drawing_facts, render, run, survey_record, use_model)

TEXT = "text layer"
SURVEY_FOLDER = "SUR_GAL_Data"  # ponytail: this Firm's folders; make them an option when a second Firm comes
CERTIFICATE_FOLDER = "EL_GAL_Data"
PLAT_GROUP = re.compile(r".+ Plats Group \d+")  # this county's plat folders, e.g. "Galveston County Plats Group 1"


def clean(v):
    v = re.sub(r"\s+", " ", v or "").strip(" ,;:")
    return v or None


def first(rx, s, flags=0):
    m = re.search(rx, s, flags)
    return clean(m.group(1)) if m else None


# ------------------------------------------------------------ typed certificate, page 1 text layer

def address(p1):
    """A2: the first line under the label, without the right-hand column; then the city."""
    m = re.search(r"A2\.\s*Building Street Address.*\n", p1)
    street = None
    for ln in (p1[m.end():].split("\n")[:4] if m else []):
        s = re.sub(r"\s{3,}Company NAIC Number.*$", "", ln).strip()
        if re.match(r"City\b", s):
            break
        if s and not re.fullmatch(r"(?i)st|nd|rd|th", s):  # a superscript on its own line
            street = clean(s)
            break
    city = first(r"^\s*City\s+(.*?)\s+State\s", p1, re.M)
    return ", ".join(x for x in (street, city) if x) or None


def flood_table(p1):
    """B4-B9: values sit in columns under a header line, spread over the lines before B10."""
    m = re.search(r"^(.*B4\. Map/Panel Number.*)\n((?:.*\n)*?)\s*B\s?10\.", p1, re.M)
    if not m:
        return {}
    hdr = m.group(1)
    labels = r"Effective/Revised Date|AO, use base flood depth\)|Zone\(s\)|\bDate\b"
    lines = [re.sub(labels, lambda x: " " * len(x.group(0)), ln) for ln in m.group(2).split("\n")]
    out = {}
    panel = re.search(r"(\d{6})\s*(\d{4})\s+([A-Z])\b", "\n".join(lines))
    date_rx = r"[A-Za-z]{3,9}\.?\s+\d{1,2}\s*,\s*\d{4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}"
    p7, p8, p9 = hdr.find("B7."), hdr.find("B8."), hdr.find("B9.")
    b7 = [d.group(0) for ln in lines for d in re.finditer(date_rx, ln) if p7 > 0 and d.start() >= p7 - 4]
    if panel:
        out["FIRM panel"] = " ".join(panel.groups()) + (f", {clean(b7[0]).title()}" if b7 else "")
    if p8 > 0 and p9 > 0:
        zone = [re.sub(date_rx, " ", ln[p8 - 6:p9 - 2]).strip() for ln in lines]
        zone = [re.sub(r"^\S*\d{4}\b", "", z).strip() for z in zone]  # a date's year spilling into the column
        bfe = [ln[p9 - 2:].strip() for ln in lines]
        out["Flood zone"] = clean(" ".join(z for z in zone if z))
        out["BFE"] = clean(" ".join(b for b in bfe if b))
    return out


HEIGHTS = {
    "Top of bottom floor": r"Top of bottom floor \(including basement, crawl\s?space,? or enclosure floor\)",
    "Lowest structural member": r"Bottom of the lowest horizontal structural mem\w*\s*\(V Zones only\)",
    "Lowest adjacent grade": r"Lowest adjacent \(finished\) grade(?: next to building)? \(LAG\)",
    "Highest adjacent grade": r"Highest adjacent \(finished\) grade(?: next to building)? \(HAG\)",
}


def certificate_facts(p1):
    """Raw Facts from page 1 of a typed FEMA Elevation Certificate. Box A1 holds the owner's name on the form,
    so only the Job number and Parcel ID are taken from it; owner and client names are never read."""
    a1 = first(r"A1\s?\.\s*Building Owner.?s Name\s*(.*)$", p1, re.M) or ""
    pid = first(r"File\s*(?:#|No\.?)?\s*:?\s*(\d[\d\- ]{12,22}\d)", a1)
    m = re.search(r"Lat\.\s*(.*?)\s+Long\.\s*(.*?)(?:\s{3,}|\s*Horizontal|$)", p1, re.M)
    lat, lon = (clean(m.group(1)), clean(m.group(2))) if m else (None, None)
    raw = {
        "Job number": first(r"Job\s*(?:#|No\.?)?\s*:?\s*(\d{2}-\d{4}\S*)", a1),
        "Parcel ID": pid and pid.replace(" ", ""),
        "Address": address(p1),
        "Lot and block": first(r"A3\.\s*Property Description.*?\n(.*?)\n\s*A4\.", p1, re.S),
        "Lat/long": f"{lat}, {lon}" if lat or lon else None,
        "Date": first(r"Date\s+(.+?)\s+Telephone", p1),
        **flood_table(p1),
        "Benchmark": first(r"Benchmark Utilized\s*(.*?)\s*Vertical Datum", p1),
    }
    for label, rx in HEIGHTS.items():
        raw[label] = first(rx + r"[ \t]*(\S*)", p1)
    return [{"label": k, "value": v.rstrip(",").strip(), "page": 1, "read_by": TEXT}
            for k, v in raw.items() if v and not re.fullmatch(r"(?i)n\.?/?a\.?|feet.*", v)]  # NA, N/A, N.A: not applicable


# ------------------------------------------------------------ C1 tick boxes, read from the pixels

DPI = 150
SCALE = DPI / 72


def words(pdf):
    out = run("pdftotext", "-bbox", "-f", "1", "-l", "1", str(pdf), "-").decode("utf-8", "replace")
    rx = r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="[\d.]+" yMax="([\d.]+)">(.*?)</word>'
    return [(float(x), float(y0), float(y1), t) for x, y0, y1, t in re.findall(rx, out)]


def dark(img, x, y0, y1):
    w, h, px = img
    return sum(px[y * w + x] < 150 for y in range(y0, y1)) / max(1, y1 - y0) if 0 <= x < w else 0


def ticked(img, word):
    """Ink inside the box just left of an option word, or None when no box is found there."""
    x0, y0, y1, _ = word
    yc = (y0 + y1) / 2 - 0.3
    ya, yb = int((yc - 2.6) * SCALE), int((yc + 2.6) * SCALE)
    edges, x, stop = [], int((x0 - 1) * SCALE), int((x0 - 24) * SCALE)
    while x > stop:  # scan left for the box's two vertical edges
        if dark(img, x, ya, yb) > 0.85:
            right = x
            while x > stop and dark(img, x - 1, ya, yb) > 0.85:
                x -= 1
            edges.append((x, right))
        x -= 1
    for (r0, _), (_, l1) in zip(edges, edges[1:]):
        if 4 <= (r0 - l1) / SCALE <= 11:
            w, _, px = img
            ys, xs = range(int((yc - 2.4) * SCALE), int((yc + 2.4) * SCALE)), range(l1 + 2, r0 - 1)
            return sum(px[y * w + x] < 150 for y in ys for x in xs) / max(1, len(ys) * len(xs))
    return None


def basis(pdf):
    ws = words(pdf)
    c1 = next((w for w in ws if re.match(r"C1\.?$", w[3])), None)
    if not c1:
        return None
    line = [w for w in ws if abs(w[1] - c1[1]) < 3 and w[0] > c1[0] + 100]
    options = {"Construction drawings": "Construction", "Building under construction": "Building",
               "Finished construction": "Finished"}
    img = render(pdf, DPI)
    on = []
    for name, word in options.items():
        w = next((w for w in line if w[3].startswith(word)), None)  # the first word of each option
        if w and (ticked(img, w) or 0) >= 0.10:
            on.append(name)
    value = on[0] if len(on) == 1 else ("No box ticked" if not on else "Two boxes ticked")
    return {"label": "Basis", "value": value, "page": 1, "read_by": "tick box pixels"}


# ------------------------------------------------------------ one file

def read(pdf, archive, answers):
    """(record, None) for a Record, else (None, the reason it was skipped). The vision model reads every Record in
    the Survey folder, and every other Record that is not a clean typed Elevation Certificate: a scanned page with no
    text layer or with a garbled one (an OCR layer, or too few Facts), or a Natural Ground Letter."""
    file = pdf.relative_to(archive).as_posix()
    if "/" not in file:
        return None, "a file at the top of the archive folder, in no folder ingestion knows"
    folder = file.split("/")[0]
    if folder not in (CERTIFICATE_FOLDER, SURVEY_FOLDER):
        return None, f"a folder ingestion does not know: {folder}"
    if pdf.suffix.lower() != ".pdf":
        return None, "not a PDF"
    if folder == SURVEY_FOLDER:
        rec = survey_record(file, answers.read(pdf, file, SURVEY_READING))
        if rec["kind"] == SURVEY:  # a failure here keeps the Record and its title-block Facts
            try:
                rec["facts"] += drawing_facts(answers.read(pdf, file, DRAWING_READING))
            except (OSError, ValueError, KeyError) as e:
                print(f"Could not read the drawing of {file} ({type(e).__name__}); run again to retry.")
        return rec, None
    p1 = run("pdftotext", "-layout", "-enc", "UTF-8", "-f", "1", "-l", "1", str(pdf), "-").decode("utf-8", "replace")
    p1 = p1.replace("\r", "").replace("\x01", " ")  # some typed letters use \x01 for a space
    typed = len(p1.strip()) >= 50 and b"OCR" not in run("pdffonts", "-f", "1", "-l", "1", str(pdf))
    if not typed or "ELEVATIONCERTIFICATE" not in re.sub(r"\s+", "", p1).upper():
        return certificate_record(file, answers.read(pdf, file, CERTIFICATE_READING)), None
    facts = certificate_facts(p1)
    if len(facts) < 8:  # a garbled text layer: a clean typed certificate gives 11 to 14 Facts
        return certificate_record(file, answers.read(pdf, file, CERTIFICATE_READING)), None
    c1 = basis(pdf)
    return {"file": file, "kind": CERTIFICATE, "facts": facts + ([c1] if c1 else [])}, None


def saved(path, fetch):
    """The saved copy of an Authoritative source in the index folder, fetched only when it is missing."""
    if not path.exists():
        print(f"Fetching {path.name} ...")
        path.write_text(json.dumps(fetch(), separators=(",", ":")), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def main(archive, index_dir, parcels_zip, overrides_file=None):
    archive, index_dir = Path(archive).resolve(), Path(index_dir).resolve()
    if index_dir == archive or archive in index_dir.parents:
        sys.exit("The index folder must be outside the Legacy archive folder.")
    overrides = json.loads(Path(overrides_file).read_text(encoding="utf-8")) if overrides_file else {}
    files = sorted(p for p in archive.rglob("*") if p.is_file())
    in_plat_group = [rel for rel in (p.relative_to(archive) for p in files)
                     if len(rel.parts) > 1 and PLAT_GROUP.fullmatch(rel.parts[0])]
    files = sorted(set(files) - {archive / rel for rel in in_plat_group})
    plats, copies, not_plats = recorded_plats(in_plat_group)
    index_dir.mkdir(parents=True, exist_ok=True)
    answers = Answers(index_dir / "vision.jsonl")

    def read_or_skip(pdf):
        try:
            rec, why = read(pdf, archive, answers)
        except subprocess.CalledProcessError:
            return None, "Poppler could not read the file"
        except (OSError, ValueError, KeyError) as e:  # Ollama not running, or an answer that does not parse
            return None, f"the vision model could not read it ({type(e).__name__}); run again to retry"
        if rec:  # page images for the Record viewer, so the laptop needs no Poppler; a failure here keeps the Record
            try:
                rec["pages"], rec["photo_page"], rec["photo"] = draw_pages(
                    pdf, pages_dir(index_dir, rec["file"]), rec["kind"] == CERTIFICATE)
            except (subprocess.CalledProcessError, OSError) as e:
                print(f"Could not draw the pages of {rec['file']} ({type(e).__name__}); its Record viewer shows none.")
        return rec, why

    def draw(plat):  # the plat's page image, or None when it cannot be drawn
        volume_page, (file, page) = plat
        try:
            draw_plat(archive / file, page, index_dir / "pages" / "plats" / f"{volume_page}.png")
            return f"pages/plats/{volume_page}.png"
        except (subprocess.CalledProcessError, OSError, ValueError, MemoryError) as e:  # one bad scan stops no run
            print(f"Could not draw Recorded Plat {volume_page} from {file.as_posix()} ({type(e).__name__}).")
            return None

    def read_plat(plat):  # the vision model's reading of the plat, or None
        volume_page, (file, page) = plat
        try:
            return answers.read(archive / file, file.as_posix(), PLAT_READING, page)
        except (subprocess.CalledProcessError, OSError, ValueError, KeyError, MemoryError) as e:  # no Ollama, or a bad scan
            print(f"Could not read Recorded Plat {volume_page} ({type(e).__name__}); run again to retry.")
            return None

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(read_or_skip, files))
        images = list(pool.map(draw, plats.items()))
        readings = list(pool.map(read_plat, plats.items()))
    fema, ngs = saved(index_dir / "fema.json", fetch_fema), saved(index_dir / "ngs.json", fetch_ngs)
    parcels = read_parcels(parcels_zip)
    areas = PlatAreas(parcels)
    placed_plats = [areas.place(reading) if reading else ([], "not read") for reading in readings]
    drawn = {volume_page for volume_page, image in zip(plats, images) if image}  # a Survey links only to a plat it can show
    index, report = build_index([rec for rec, _ in results if rec], parcels, overrides, census_geocoder, fema, ngs, drawn)
    for f, (_, why) in zip(files, results):
        if why:
            report["skipped"].setdefault(why, []).append(f.relative_to(archive).as_posix())
    for f in not_plats:
        report["skipped"].setdefault("not a Recorded Plat (in a plat group folder)", []).append(f.as_posix())
    how_placed = Counter(how.split(":")[0] for area, how in placed_plats if area)
    not_placed = {}
    for vp, (area, how) in zip(plats, placed_plats):
        if not area:
            not_placed.setdefault(how.split(":")[0], []).append(vp)
    report["plats"] = {"found": len(plats), "not drawn": [vp for vp, image in zip(plats, images) if not image],
                       "extra copies": [f.as_posix() for f in copies], "read": sum(1 for r in readings if r),
                       "placed": dict(how_placed), "not placed": not_placed}
    records = {"records": index["records"], "counts": index["counts"],  # the rest is in parcels, fema and ngs.json
               "plats": {vp: {"file": file.as_posix(), "page": page, "image": image, "reading": reading,
                              "area": sorted({p["id"] for p in area}), "how": how}  # area: GCAD Parcel IDs (parcels.json)
                         for (vp, (file, page)), image, reading, (area, how) in zip(plats.items(), images, readings, placed_plats)}}
    (index_dir / "index.json").write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    (index_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    (index_dir / "parcels.json").write_text(json.dumps(parcels, separators=(",", ":")), encoding="utf-8")
    print(f"Indexed {index['counts']['records']} Records in {index['counts']['jobs']} Jobs, with {len(parcels)} GCAD parcels.")
    placed = Counter(r["location"]["found_by"] if r["location"] else "not located" for r in index["records"])
    print("Locations:")
    for how, n in placed.most_common():
        print(f"  {n:4}  {how}")
    print(f"Flagged: {sum(1 for r in index['records'] if r['flags'])}. Skipped:")
    for why, names in sorted(report["skipped"].items()):
        print(f"  {len(names):4}  {why}")
    print(f"Recorded Plats: {len(plats)} found, {len(report['plats']['not drawn'])} not drawn, {len(copies)} extra copies, "
          f"{report['plats']['read']} read, {sum(how_placed.values())} placed. Placed:")
    for how, n in how_placed.most_common():
        print(f"  {n:4}  {how}")
    print("Not placed:")
    for why, vps in sorted(not_placed.items(), key=lambda x: -len(x[1])):
        print(f"  {len(vps):4}  {why}")
    cited = report["plat_citations"]
    print(f"Surveys citing a Recorded Plat: {cited['citing']}, the plat found for {cited['found']}, "
          f"not held for {len(cited['not_held'])}.")
    print(f"FEMA saved {fema['saved']}: {len(fema['zones'])} flood zones, {len(fema['panels'])} panels. "
          f"NGS: {len(ngs)} Benchmarks with a published height.")
    print(f"Wrote index.json, parcels.json and report.json in {index_dir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Turn a Legacy archive folder into an index folder.")
    ap.add_argument("archive", help="the Legacy archive folder")
    ap.add_argument("index", help="the index folder to write (outside the archive and outside git)")
    ap.add_argument("--parcels", required=True, help="the GCAD 'Parcels with data' shapefile zip")
    ap.add_argument("--overrides", help="the overrides file: Records placed by hand")
    ap.add_argument("--model", default=MODEL, help=f"the Ollama vision model (default {MODEL}; a 24 GB card can use qwen3.6:27b)")
    a = ap.parse_args()
    use_model(a.model)
    main(a.archive, a.index, a.parcels, a.overrides)
