"""Page images and the vision-model readers (ingestion only).

Page 1 of a Record is read by qwen3.6:35b in Ollama with the setup chosen in decision #5: thinking off, temperature 0,
a fixed JSON schema, and the page sent as the whole sheet at 1024 px plus the whole sheet in at most 3 x 3 tiles of
up to 1400 px, with no rotation fix. One reading reads a Record in the Survey folder; another reads a certificate
that has no clean text layer (a scanned page) and a Natural Ground Letter. A third reads a Survey's drawing with the
setup chosen in decision #14 (see drawing_images). Every answer is saved, keyed by the PDF's content and the prompt,
so a re-run asks only about new or changed Records. Needs Poppler, Ollama and (for the drawing reading) Pillow.
"""
import base64
import hashlib
import json
import math
import re
import shutil
import struct
import subprocess
import sys
import threading
import zlib
from pathlib import Path
from urllib.request import Request, urlopen

from surveysleuth.archive import CERTIFICATE, DRAWN, FLOOD_NOTES, LETTER, SURVEY

MODEL = "qwen3.6:35b"
OLLAMA = "http://localhost:11434/api/chat"
READ_BY = f"vision model ({MODEL})"


def run(tool, *args):
    """A Poppler tool's output. Git for Windows puts xpdf's pdftotext first on PATH; use the folder of pdftoppm."""
    poppler = shutil.which("pdftoppm")
    if not poppler:
        sys.exit("Poppler is not on PATH (pdftoppm not found).")
    return subprocess.run([str(Path(poppler).parent / tool), *args], capture_output=True, check=True).stdout


def render(pdf, dpi):
    """Page 1 in grey: (width, height, pixels)."""
    b = run("pdftoppm", "-gray", "-r", f"{dpi:.2f}", "-f", "1", "-l", "1", "-singlefile", str(pdf))
    _, w, h, _ = b.split(maxsplit=4)[:4]
    return int(w), int(h), b[len(b) - int(w) * int(h):]


def png(w, h, pixels):
    """A grey PNG file from w x h pixels."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    rows = b"".join(b"\0" + pixels[y * w:(y + 1) * w] for y in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))


def sheet_images(pdf, dpi):
    """PNGs: the whole sheet at 1024 px, then the whole sheet at dpi (or less, to stay within 4200 px)
    cut into at most 3 x 3 tiles of up to 1400 px, left to right, top to bottom."""
    whole = run("pdftoppm", "-png", "-scale-to", "1024", "-f", "1", "-l", "1", "-singlefile", str(pdf))
    # floor the dpi to 2 decimals so the long side stays within 4200 px: at most 3 x 3 tiles
    sheet = render(pdf, math.floor(min(dpi, 4200 * 72 / long_side(pdf)) * 100) / 100)
    return [whole] + [png(*t) for t in tiles(*sheet, lap=0)]


def long_side(pdf):
    """Page 1's long side in points (1/72 in)."""
    size = re.search(rb"Page\s+1 size:\s+([\d.]+) x ([\d.]+)", run("pdfinfo", "-f", "1", "-l", "1", str(pdf)))
    return max(map(float, size.groups()))


def tiles(w, h, px, lap=100):
    """The sheet cut into nx x ny equal parts of at most 1400 px, left to right, top to bottom, each part widened by
    lap px into its neighbors (as tested in #14): [(width, height, pixels)]."""
    nx, ny = math.ceil(w / 1400), math.ceil(h / 1400)
    tw, th = math.ceil(w / nx), math.ceil(h / ny)
    out = []
    for j in range(ny):
        for i in range(nx):
            x0, y0 = max(i * tw - lap, 0), max(j * th - lap, 0)
            x1, y1 = min((i + 1) * tw + lap, w), min((j + 1) * th + lap, h)
            out.append((x1 - x0, y1 - y0, b"".join(px[y * w + x0:y * w + x1] for y in range(y0, y1))))
    return out


def upright(w, h, px):
    """The sheet turned a quarter clockwise: each column, read bottom to top, becomes a row."""
    return h, w, b"".join(px[x::w][::-1] for x in range(w))


def drawing_images(pdf):
    """PNGs as tested in #14: page 1 at 200 dpi, or 150 dpi when its long side passes 17 in (200 dpi on a 24x36 sheet
    passes the model's 32k context). A landscape legal scan holds a portrait Survey turned sideways, so it is turned
    upright first; no other sheet is turned. Then the whole sheet at 1024 px, and the full-size sheet in tiles."""
    dpi = 150 if long_side(pdf) / 72 > 17 else 200
    sheet = render(pdf, dpi)
    # ponytail: every landscape scan up to 14.5 in wide is turned clockwise, as the Survey inventory and #14 did;
    # find the way up from the page itself if another Firm's scans lie the other way
    if sheet[0] > sheet[1] and sheet[0] / dpi < 14.5 and scanned(pdf):
        sheet = upright(*sheet)
    return [png(*shrink(*sheet))] + [png(*t) for t in tiles(*sheet)]


def shrink(w, h, px):
    """The sheet at 1024 px on its long side, by Pillow's Lanczos filter as in #14. The model is that sensitive:
    Poppler's own 1024 px render, or a box filter, lost 2 to 5 of the 20 hand-checked Surveys per kind."""
    try:
        from PIL import Image  # ingestion only, so the app and the tests need no Pillow
    except ImportError:
        sys.exit("Pillow is not installed (pip install pillow); reading Survey drawings needs it.")
    s = 1024 / max(w, h)
    im = Image.frombytes("L", (w, h), px).resize((round(w * s), round(h * s)), Image.LANCZOS)
    return im.width, im.height, im.tobytes()


def scanned(pdf):
    """Is page 1 a scan: does it hold an image of over a million pixels?"""
    rows = [r.split() for r in run("pdfimages", "-list", "-f", "1", "-l", "1", str(pdf)).decode("latin1").splitlines()[2:]]
    return any(int(r[3]) * int(r[4]) > 1_000_000 for r in rows if len(r) > 4 and r[3].isdigit() and r[4].isdigit())


TEXT = {"type": ["string", "null"]}


def schema(**properties):
    return {"type": "object", "properties": properties, "required": list(properties)}


# ------------------------------------------------------------ a Record in the Survey folder (decision #5, ticket #21)

PROMPT = """This is page 1 of a Record from a Texas land-surveying firm: usually a land survey plat. Read it and fill in the JSON.
- record_kind: "survey plat or replat" for a drawn plat of a lot, tract or subdivision; "metes and bounds description" for a page of text that describes a tract by bearings and distances (often headed Exhibit "A"); "floor plan" for a drawn plan of a building's rooms; "field notes" for hand-written notes or a hand sketch.
- job_no: the JOB No. in the small title block (two digits, a dash, four digits, sometimes a suffix). If there is no title block, use the job number printed in the page footer.
- survey_date: the SURVEY DATE in the title block (not a REVISED date), as YYYY-MM-DD.
- file_no: the FILE No. in the title block, format NNNN-NNNN-NNNN-NNN.
- lots: every lot number named in the legal description paragraph ("Survey of Lot ..."), as a list of strings.
- block: the block number in the legal description, or null.
- subdivision: the subdivision, addition or survey name in the legal description.
- flood_note: "in" if a note says the property does lie within the 100 year flood plain, "out" if a note says it does not lie within it, else null.
Use null for anything not shown. Do not guess. Never copy a person's name.
Image 1 is the whole sheet. The other images are close-ups of the same sheet, left to right, top to bottom. The sheet may be rotated.
- street: the street address of the surveyed lot if the sheet shows one (house number and street name), else null.
- plat_citation: the words that cite the recorded plat of the surveyed lot's own subdivision (not a plat cited for an adjoining lot or tract), copied as printed (e.g. "Volume 7, Page 12, of the Map Records of Galveston County"), or null. A deed volume and page, a Clerk's File number or a Film Code number is not a plat citation.
- plat_volume, plat_page: the volume and page of that plat citation, e.g. "7" and "12"; a second map on a page keeps its decimal, e.g. "64.1". null when there is no plat citation."""
# The street and plat lines follow the image line, as in the prompt that passed #49 Part 2 (the street is not kept).
# This wording read 19 of #49's 20 checked citations right; naming the legal description instead fixed the adjoiner
# miss but broke 2 others (18 of 20), so it was not kept.
KINDS = {"survey plat or replat": SURVEY, "metes and bounds description": "Metes-and-Bounds Description",
         "floor plan": "Floor Plan", "field notes": "Field Notes"}
SURVEY_READING = {
    "prompt": PROMPT, "images": lambda pdf: sheet_images(pdf, 150),
    "schema": schema(record_kind={"type": "string", "enum": list(KINDS)}, job_no=TEXT, survey_date=TEXT, file_no=TEXT,
                     lots={"type": "array", "items": {"type": "string"}}, block=TEXT, subdivision=TEXT,
                     flood_note={"type": ["string", "null"], "enum": ["in", "out", None]}, street=TEXT,
                     plat_citation=TEXT, plat_volume=TEXT, plat_page=TEXT),
}


# ------------------------------------------------------------ a certificate with no clean text layer, or a letter (#22)

CERTIFICATE_PROMPT = """This is page 1 of a flood Elevation Certificate (FEMA form 81-31) or of a Natural Ground letter from a Texas land-surveying firm. It may be a poor scan. Read it and fill in the JSON. Copy each value exactly as printed or written. Use null for anything not shown, "N/A" or blank. Do not guess. Never copy a person's name.
- record_kind: "elevation certificate" for the FEMA form; "natural ground letter" for a letter that certifies the natural ground elevation of a lot.
- job_no: the firm's job number (two digits, a dash, four digits). On the FEMA form it is written in box A1, e.g. "CST Job# 09-0001".
- parcel_id: the tax parcel or File No., format NNNN-NNNN-NNNN-NNN (box A1 on the FEMA form).
- street: the building street address (box A2), house number and street only. city: the city of that address.
- legal: the property description (box A3): lot, block, subdivision.
- lat, lon: the latitude and longitude (box A5) exactly as written, e.g. N 29°18'46.5" and W 94°47'12.3".
- panel: the six-digit community number and the four-digit panel number (box B4 on the FEMA form; the Community and Panel columns on a letter). suffix: the panel suffix letter (box B5). panel_date: the FIRM panel effective/revised date (box B7).
- zone: the flood zone (box B8). bfe: the base flood elevation (box B9).
- basis: the box that is checked in C1: "construction drawings", "building under construction" or "finished construction".
- benchmark: the Benchmark Utilized (C2), or on a letter the temporary bench mark: its description.
- c2a: C2.a top of bottom floor. c2c: C2.c bottom of the lowest horizontal structural member. c2f: C2.f lowest adjacent grade (LAG). c2g: C2.g highest adjacent grade (HAG).
- natural_ground: on a letter, the natural ground elevation in feet.
- date: on the FEMA form the date next to the signature in Section D; on a letter the letter's date.
Image 1 is the whole page. The other images are close-ups of the same page, left to right, top to bottom."""
CERTIFICATE_READING = {
    "prompt": CERTIFICATE_PROMPT, "images": lambda pdf: sheet_images(pdf, 200),
    "schema": schema(record_kind={"type": "string", "enum": ["elevation certificate", "natural ground letter"]},
                     **{k: TEXT for k in ("job_no", "parcel_id", "street", "city", "legal", "lat", "lon", "panel", "suffix",
                                          "panel_date", "zone", "bfe", "basis", "benchmark", "c2a", "c2c", "c2f", "c2g",
                                          "natural_ground", "date")}),
}
BASES = {"construction drawings": "Construction drawings", "building under construction": "Building under construction",
         "finished construction": "Finished construction"}


# ------------------------------------------------------------ a Survey's drawing (decision #14, ticket #26)

# The prompt and schema that passed #14, word for word. They ask for corner marks too; those are never kept.
DRAWING_PROMPT = """This is page 1 of a land survey plat from a Texas surveying firm.
Image 1 is the whole sheet. The other images are full-size close-ups of the same sheet (they overlap a little).
List the labels drawn on the plat for these four kinds. Copy each label as printed. List each different label once.
- corner_marks: survey marks at lot corners, e.g. "Fnd. 1/2" Rod", "Fnd. 1" Pipe", "Fnd. "X"", "Set 1/2" Rod", "CM".
  status is "found" (Fnd., Found, Fd.) or "set" (Set). Use "found" for a CM unless it says Set.
  Copy only the mark, not its offset or bearing: for "Fnd. 1/2" Rod 0.2' East" write "Fnd. 1/2" Rod".
  For "P.O.B. Fnd. 1" Pipe" write "Fnd. 1" Pipe". A P.O.B. or P.O.C. with no mark named is not a corner mark.
  Ignore marks named only in the NOTES text (e.g. "Bearings based on ...").
- buildings: buildings and structures drawn on the plat, as labeled, e.g. "2-Sty High Raised Frame House", "Garage",
  "Shed", "Deck", "Pool", "Dock", "Pier", "Bulkhead", "Carport". Leave out the house number ("No. 1234").
  Leave out flat paving (concrete, drives, walks, slabs), fences, ponds, water, roads and anything on a neighbor's lot.
- easements: each easement, width and kind as printed, e.g. "10' U.E.", "5' A.E.", "D.E.", "Drainage Esmt.".
  Roads, streets, alleys and R.O.W. are not easements.
- setback_lines: each building line or setback line as printed, e.g. "25' B.L.". Only lines labeled B.L., Building Line
  or Setback; an offset from a water line is not a setback line.
Use [] when a kind is not shown. Do not guess. Never copy a person's or owner's name."""
LABELS = {"type": "array", "items": {"type": "string"}}
DRAWING_READING = {
    "prompt": DRAWING_PROMPT, "images": drawing_images,
    "schema": schema(corner_marks={"type": "array", "items": schema(label={"type": "string"},
                                                                    status={"type": "string", "enum": ["found", "set"]})},
                     buildings=LABELS, easements=LABELS, setback_lines=LABELS),
}
DRAWING_LABELS = dict(zip(("buildings", "easements", "setback_lines"), DRAWN))  # schema key -> Fact label; no corner marks


def drawing_facts(out):
    """The Facts from one drawing answer: each different building, easement and setback line label once, as printed,
    without a house number the model copied anyway. Corner marks stay out: the model names their kinds well but
    cannot count them (#14)."""
    def without_house_number(x):
        return re.sub(r"(?i)^no\.?\s*\d+[a-z]?\s+", "", x.strip())
    return [{"label": label, "value": v, "page": 1, "read_by": READ_BY}
            for key, label in DRAWING_LABELS.items() for v in dict.fromkeys(map(without_house_number, out.get(key) or [])) if v]


def ask(images, reading):
    """The model's answer for these page images, as a dict that fits the reading's schema."""
    body = {"model": MODEL, "stream": False, "keep_alive": "30m", "think": False, "format": reading["schema"],
            "messages": [{"role": "user", "content": reading["prompt"], "images": [base64.b64encode(i).decode() for i in images]}],
            "options": {"temperature": 0, "num_ctx": 32768, "num_predict": 1024}}
    with urlopen(Request(OLLAMA, json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=900) as r:
        return json.loads(json.load(r)["message"]["content"])


def parses(line):
    try:
        json.loads(line)
        return True
    except ValueError:
        return False


class Answers:
    """The saved model answers (a JSON-lines file in the index folder), keyed by the PDF's content and the prompt."""

    def __init__(self, path):
        self.path, self.lock = path, threading.Lock()
        lines = path.read_bytes().decode("utf-8", "replace").splitlines() if path.exists() else []
        good = [line for line in lines if parses(line)]
        if len(good) < len(lines):  # a hard stop cut the last answer short: drop it, so it is asked again
            path.write_text("".join(line + "\n" for line in good), encoding="utf-8")
        self.saved = {a["key"]: a["out"] for a in map(json.loads, good)}

    def read(self, pdf, file, reading, page=0):
        # The key holds the model and prompt, not the images or schema: change the prompt's wording when changing those,
        # so old answers are not reused. A page after the first (a Recorded Plat file can hold 2 or 3 maps) has its own.
        prompt_key = hashlib.sha256((MODEL + reading["prompt"]).encode()).hexdigest()[:12]
        key = hashlib.sha256(pdf.read_bytes()).hexdigest() + ":" + prompt_key + (f":{page}" if page else "")
        if key not in self.saved:
            out = ask(reading["images"](pdf, page) if page else reading["images"](pdf), reading)
            with self.lock:
                self.saved[key] = out
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"key": key, "file": file, "out": out}) + "\n")
        return self.saved[key]


def facts_from(raw):
    return [{"label": k, "value": str(v).strip(), "page": 1, "read_by": READ_BY}
            for k, v in raw.items() if v and str(v).strip() and not re.fullmatch(r"(?i)n\.?/?a\.?", str(v).strip())]


def survey_record(file, out):
    """The Record kind and raw Facts from one Survey-folder answer. A Metes-and-Bounds Description, Floor Plan or
    Field Notes keeps only the Facts every Record has: Job number, date and Parcel ID."""
    kind = KINDS.get(out.get("record_kind"), SURVEY)
    raw = {"Job number": out.get("job_no"), "Date": out.get("survey_date"), "Parcel ID": out.get("file_no")}
    if kind == SURVEY:
        lots = [re.sub(r"(?i)^lots?\s+", "", x.strip()) for x in out.get("lots") or []]  # the model may repeat "Lot"
        block = out.get("block") and re.sub(r"(?i)^(block|blk)\s+", "", out["block"].strip())
        subdivision = out.get("subdivision")
        legal = [("Lots " if len(lots) > 1 else "Lot ") + ", ".join(lots) if lots else None, block and f"Block {block}", subdivision]
        raw["Lot and block"] = ", ".join(x for x in legal if x)
        raw["Flood note"] = FLOOD_NOTES.get(out.get("flood_note"))
        raw["Recorded Plat"] = recorded_plat(out)
    return {"file": file, "kind": kind, "facts": facts_from(raw)}


NOT_COUNTY = {"THE", "OF", "SAID", "THIS", "RECORDS", "RECORD", "MAP", "PLAT", "DEED", "OFFICIAL"}


def recorded_plat(out):
    """'Volume 7, Page 12' for the Recorded Plat a Survey cites, or None. A deed, Clerk's File or Film Code citation
    is not a plat, even when the model fills in its volume and page, and neither is a volume and page with no citation
    text. A volume printed with a space is closed up ('31 A' -> '31A'); a plat cited on several pages gives its first.
    Another county's plat keeps its county ('Volume 8, Page 3, Sample County'), however the county is written, so it
    is never taken for a Galveston County plat of the same number."""
    cited = (out.get("plat_citation") or "").upper()
    volume = re.sub(r"\s+", "", out.get("plat_volume") or "")
    page = re.search(r"\d+(?:\.\d+)?(?:-?A\b)?", (out.get("plat_page") or "").upper())
    if not (cited.strip() and volume and page) or (
            re.search(r"DEED|CLERK'?S? FILE|FILM CODE|OFFICIAL PUBLIC", cited) and not re.search(r"MAP|PLAT", cited)):
        return None
    counties = [c for c in re.findall(r"\b((?:FORT )?[A-Z]+) (?:COUNTY|CO\.)", cited) + re.findall(r"\bCOUNTY OF (?:THE )?((?:FORT )?[A-Z]+)", cited)
                if c not in NOT_COUNTY]
    other = f", {counties[0].title()} County" if counties and "GALVESTON" not in counties else ""
    return f"Volume {volume}, Page {page.group()}{other}"


def feet(v):
    """'4.8 feet', '4.8 ft.' or "4.8'" -> '4.8', as the text-layer reader gives it; 'NA feet' -> 'NA'."""
    return v and re.sub(r"(?i)\s*(feet|ft\.?|')\s*$", "", v.strip())


def firm_panel(out, letter):
    """'485470 0274 E, December 6, 2002': community and panel number, suffix and (on the FEMA form) panel date."""
    digits = "".join(re.findall(r"\d", out.get("panel") or ""))
    if not digits:
        return None
    suffix = f" {out['suffix'].strip()}" if out.get("suffix") else ""
    date = f", {out['panel_date'].strip()}" if out.get("panel_date") and not letter else ""
    return f"{digits[:6]} {digits[6:]}{suffix}{date}"


def certificate_record(file, out):
    """The Record kind and raw Facts from one answer about a certificate with no clean text layer or a Natural Ground
    Letter, cleaned to look like the text-layer reader's Facts (same labels, same checks)."""
    letter = out.get("record_kind") == "natural ground letter"
    street, city = out.get("street"), out.get("city")
    benchmark = out.get("benchmark") and re.split(r"(?i)\s+vertical datum", out["benchmark"])[0]  # the next C2 label
    raw = {"Job number": out.get("job_no"), "Parcel ID": (out.get("parcel_id") or "").replace(" ", ""),
           "Address": ", ".join(x.strip() for x in (street, city) if x and x.strip()) if street else None,
           "Lot and block": out.get("legal"), "Date": out.get("date"), "Flood zone": out.get("zone"),
           "BFE": feet(out.get("bfe")), "FIRM panel": firm_panel(out, letter), "Benchmark": benchmark}
    if letter:
        raw["Natural ground"] = feet(out.get("natural_ground"))
    else:
        lat, lon = out.get("lat"), out.get("lon")
        basis = (out.get("basis") or "").strip(" *").lower()  # the form prints "Construction Drawings*"
        raw.update({"Lat/long": f"{lat}, {lon}" if lat and lon else None, "Basis": BASES.get(basis, out.get("basis")),
                    "Top of bottom floor": feet(out.get("c2a")), "Lowest structural member": feet(out.get("c2c")),
                    "Lowest adjacent grade": feet(out.get("c2f")), "Highest adjacent grade": feet(out.get("c2g"))})
    return {"file": file, "kind": LETTER if letter else CERTIFICATE, "facts": facts_from(raw)}


# ------------------------------------------------------------ page images for the Record viewer (ticket #23)

def fresh(path, pdf):
    return path.exists() and path.stat().st_mtime >= pdf.stat().st_mtime


def draw_pages(pdf, out_dir, with_photo):
    """Draw every page of a Record as out_dir/1.jpg, 2.jpg ... (150 dpi, at most 3200 px on the long side), so the
    laptop needs no Poppler. Pages newer than the PDF are kept; each is written under a temporary name first, so an
    interrupted run leaves no half-written page.
    With with_photo (a certificate), find the photo page: the first page from page 3 on with a colour image (on the
    FEMA form pages 1 and 2 are the form, on both editions). Its thumbnail is the largest photo-sized colour image there
    (not a whole-page scan, not a strip), saved as out_dir/photo.jpg when it is a JPEG.
    Returns (number of pages, photo page or None, whether a thumbnail was saved)."""
    info = run("pdfinfo", "-f", "1", "-l", "9999", str(pdf))
    sizes = {int(n): max(float(w), float(h)) for n, w, h in re.findall(rb"Page\s+(\d+) size:\s+([\d.]+) x ([\d.]+)", info)}
    out_dir.mkdir(parents=True, exist_ok=True)
    for n, side in sizes.items():
        if not fresh(out_dir / f"{n}.jpg", pdf):
            dpi = math.floor(min(150, 3200 * 72 / side) * 100) / 100
            run("pdftoppm", "-jpeg", "-jpegopt", "quality=80", "-r", f"{dpi:.2f}", "-f", str(n), "-l", str(n),
                "-singlefile", str(pdf), str(out_dir / f"{n}.part"))
            (out_dir / f"{n}.part.jpg").replace(out_dir / f"{n}.jpg")
    if not with_photo:
        return len(sizes), None, False
    # pdfimages -list rows: page, num, type, width, height, color, comp, ...
    rows = [r.split() for r in run("pdfimages", "-list", str(pdf)).decode("latin1").splitlines()[2:]]
    rows = [r for r in rows if len(r) > 6 and r[0].isdigit() and r[3].isdigit() and r[4].isdigit()]
    page = next((int(r[0]) for r in rows if int(r[0]) >= 3 and r[6] == "3"), None)  # 3 colour channels
    if not page:
        return len(sizes), None, False
    on_page = [r for r in rows if int(r[0]) == page]
    photos = [(int(r[3]) * int(r[4]), i) for i, r in enumerate(on_page)
              if r[6] == "3" and int(r[3]) >= 200 and int(r[4]) >= 150 and int(r[3]) * int(r[4]) <= 3_000_000]
    photo = out_dir / "photo.jpg"
    if photos and not fresh(photo, pdf):
        run("pdfimages", "-j", "-f", str(page), "-l", str(page), str(pdf), str(out_dir / "img"))
        chosen = out_dir / f"img-{max(photos)[1]:03d}.jpg"  # pdfimages numbers a page's images in -list order
        if chosen.exists():
            chosen.replace(photo)
        for f in out_dir.glob("img-*"):
            f.unlink()
    return len(sizes), page, bool(photos) and photo.exists()
