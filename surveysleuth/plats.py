"""Recorded Plats: the county's subdivision plats in a plat group folder, known by volume and page (ingestion only).

A file name gives the volume and page of the Map Records, e.g. 7_12.tif; a second map on a page is 7_12.1, and an
A map is 7_12-A (known as 7_12A). A file can be named for two or three maps on the next pages: 7_30_31, 7_40-41-42
or "7_20, 7_21".
The vision model reads each plat's title (PLAT_READING), and PlatAreas places it on the area of the GCAD parcels it
lays out, with the rules that passed the #54 prototype (12 of 20 placed, none wrong).
"""
import re
import sys

from surveysleuth.archive import gcad_lots_and_blocks, metres, plain_legal, plural
from surveysleuth.gcad import address_words, in_order
from surveysleuth.vision import TEXT, fresh, png, run, schema, shrink, tiles

PLAT = re.compile(r"(?<!\d)(\d{1,4}[AB]?)[_-](\d+(?:\.\d+)?)(?:-?(A)(?![A-Za-z]))?")  # 7_16-A or 7_16A: an A map
MORE = re.compile(r"[_-](\d{1,4})(?![\d.A-Za-z])|,\s*" + PLAT.pattern)  # after 7_30: _31, -31 or ", 7_31"
TIFF, FILE_TYPES = (".tif", ".tiff"), (".tif", ".tiff", ".jpg", ".pdf")  # the order a volume and page's files win in


def map_numbers(stem):
    """The volume_page of each map a file name holds, in page order: '7_30_31' -> ['7_30', '7_31']. Only the next page
    of the same volume counts as a further map, so an instrument number or a year after the page is not one."""
    m = PLAT.search(stem)
    if not m:
        return []
    volume, page = m.group(1), m.group(2)
    out, rest = [f"{volume}_{page}{m.group(3) or ''}"], stem[m.end():]
    while (n := MORE.match(rest)) and page.isdigit():
        nxt = n.group(1) or (n.group(3) if n.group(2) == volume else None)
        if nxt != str(int(page) + 1):
            break
        out.append(f"{volume}_{nxt}")
        page, rest = nxt, rest[n.end():]
    return out


def recorded_plats(files):
    """({volume_page: (file, page in the file)}, extra copies, files that are not plats). A volume and page can be in
    several files: the plain TIFF (named just 7_12.tif) wins, then any TIFF, JPG, PDF; a file used for no plat is an
    extra copy (it carries an instrument number, a name or "Rotation of" in its name, or is a PDF beside its TIFF)."""
    found, skipped = {}, []
    for f in files:
        volume_pages = map_numbers(f.stem) if f.suffix.lower() in FILE_TYPES else []
        if not volume_pages:
            skipped.append(f)
        for page, volume_page in enumerate(volume_pages):
            found.setdefault(volume_page, []).append((f, page))

    def rank(entry):
        f = entry[0]
        plain = PLAT.fullmatch(f.stem) and f.suffix.lower() in TIFF
        return not plain, FILE_TYPES.index(f.suffix.lower()), len(f.name)

    plats = {volume_page: min(entries, key=rank) for volume_page, entries in found.items()}
    used = {f for f, _ in plats.values()}
    copies = list(dict.fromkeys(f for entries in found.values() for f, _ in entries if f not in used))
    return plats, copies, skipped


def draw_plat(file, page, out):
    """Draw one page of a plat file as a black-and-white PNG of at most 3200 px on its long side, for the Record viewer;
    a page past the file's last page gives its last page (a one-page file can be named for two maps). A page drawn
    since the file last changed is kept; the page is written under a temporary name first, so an interrupted run
    leaves no half-written page. Needs Pillow, and Poppler for a PDF."""
    if fresh(out, file):
        return
    bw = grey_page(file, page, 3200).point(lambda v: 255 if v >= 128 else 0)
    if dark(bw):  # a negative (white lines on black): turn it positive
        bw = bw.point(lambda v: 255 - v)
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_suffix(".part.png")
    bw.convert("1").save(part)
    part.replace(out)


def dark(im):
    """True when most of a grey image is dark: a negative scan."""
    return sum(im.histogram()[:128]) > im.width * im.height / 2


def grey_page(file, page, size):
    """One page of a plat file in grey (a Pillow image), at most size px on its long side; a page past the file's last
    page gives its last page. A PDF page is drawn at size px."""
    try:
        from PIL import Image  # ingestion only, so the app and the tests need no Pillow
    except ImportError:
        sys.exit("Pillow is not installed (pip install pillow); drawing and reading the Recorded Plats needs it.")
    Image.MAX_IMAGE_PIXELS = None  # the scans run to 21,632 px wide
    if file.suffix.lower() == ".pdf":
        pages = int(re.search(rb"Pages:\s+(\d+)", run("pdfinfo", str(file))).group(1))
        n = str(min(page, pages - 1) + 1)
        b = run("pdftoppm", "-gray", "-scale-to", str(size), "-f", n, "-l", n, "-singlefile", str(file))
        w, h = map(int, b.split(maxsplit=3)[1:3])
        return Image.frombytes("L", (w, h), b[len(b) - w * h:])
    with Image.open(file) as im:
        im.seek(min(page, getattr(im, "n_frames", 1) - 1))
        grey = im.convert("L")
    s = min(1.0, size / max(grey.size))
    return grey.resize((round(grey.width * s), round(grey.height * s)), Image.LANCZOS) if s < 1 else grey


def plat_images(file, page=0):
    """PNGs as in the #49 and #54 prototypes: one page of the plat in grey at up to 4200 px, a negative (mostly dark)
    turned positive, sent as the whole sheet at 1024 px and then in close-ups: parts of at most 1400 px, each widened
    100 px into its neighbors."""
    grey = grey_page(file, page, 4200)
    if dark(grey):
        grey = grey.point(lambda v: 255 - v)
    sheet = grey.width, grey.height, grey.tobytes()
    return [png(*shrink(*sheet))] + [png(*t) for t in tiles(*sheet)]


PLAT_PROMPT = """This is a subdivision plat recorded in the Map Records of Galveston County, Texas: a scanned microfilm copy. It may be faded, dark or turned sideways. Read its title and fill in the JSON.
- kind: "subdivision plat" for a plat that lays out a subdivision's lots; "replat" for a replat, resubdivision, amending plat or partial replat of an earlier subdivision; "other" for anything else (a road or right-of-way map, an acreage sketch, a drainage map, a site layout).
- name: the subdivision's name as titled, without its section, unit or phase and without words like "Replat of" or "of Lot 9", e.g. "Sample Shores".
- section: the section, unit or phase as titled, e.g. "Section 2", or null.
- replat_of: for a replat, the name and section of the earlier subdivision it replats, e.g. "Sample Shores Section 1", or null.
- lots: for a replat of only some lots or reserves of the earlier subdivision, those lots or reserves as the title or dedication names them, one per item, e.g. ["5", "6"] or ["Reserve A"]; [] when it replats a whole subdivision or section, or is not a replat.
- block: the block of those lots, or null.
- lot_count: how many lots, reserves and tracts this plat lays out (count the numbered ones drawn on it).
- town: the city or town named in the title or dedication, or null.
- date: the date it was filed or recorded, as YYYY-MM-DD, or YYYY if only the year is clear.
- sheet: e.g. "1 of 2" if the plat says it is one of several sheets, else null.
Use null for anything not shown or not readable. Do not guess. Never copy a person's name.
Image 1 is the whole sheet. The other images are close-ups of the same sheet, left to right, top to bottom."""
# The prompt and setup that passed the #54 prototype (12 of 20 placed, none wrong), word for word.
PLAT_READING = {
    "prompt": PLAT_PROMPT, "images": plat_images,
    "schema": schema(kind={"type": "string", "enum": ["subdivision plat", "replat", "other"]}, name=TEXT, section=TEXT,
                     replat_of=TEXT, lots={"type": "array", "items": {"type": "string"}}, block=TEXT,
                     lot_count={"type": ["integer", "null"]}, town=TEXT, date=TEXT, sheet=TEXT),
}


# ------------------------------------------------------------ placing a plat on its GCAD parcels (#54)

FILLER = {"THE", "OF", "A", "AN", "SUB", "SUBD", "SUBDIVISION", "ADDITION", "ADDN", "ADD", "REPLAT", "UNRECORDED",
          "AMENDED", "AMENDING", "PARTIAL", "RESUBDIVISION", "RESUB", "PLAT", "FINAL", "PRELIMINARY", "SURVEY", "SUR",
          "NO", "NUMBER"}
SAME_WORD = {"FIRST": "1", "SECOND": "2", "THIRD": "3", "FOURTH": "4", "FIFTH": "5", "SIXTH": "6", "SECTION": "SEC",
             "PHASE": "PH", "BLK": "BLOCK", "AND": "&"}
SECTION = ("SEC", "PH", "UNIT")
# words of a legal description that come just before a subdivision's name ("LOT 5 BLOCK 2 ...", "RES A ...")
BEFORE_A_NAME = {"&", "LOT", "LOTS", "BLOCK", "RES", "RESERVE", "TRACT", "TR", "TRS", "PT", "BLDG", "PARCEL", "UNIT",
                 "ESMT", "STRIP"}
PLAT_KM = 2.0  # Rick, 2026-10-03: a plat's area may be 2 km across


def words(text):
    """A name or legal description as GCAD writes it: 'Sample Shores, Section Two' -> SAMPLE SHORES SEC 2."""
    t = re.sub(r"[^A-Z0-9& ]", " ", plain_legal(text or "").replace("&", " & "))
    return [SAME_WORD.get(w, w) for w in t.split()]


def name_words(name):
    """The words GCAD must name for a subdivision: before "TO" ("Sample Addition to Sandport"), no filler such as
    SUBDIVISION, ADDITION or NO., no lone initials."""
    ws = words(name)
    ws = ws[:ws.index("TO")] if "TO" in ws else ws
    return [w for w in ws if w not in FILLER and not (len(w) == 1 and w.isalpha())]


def title(name, section):
    """'Sample Shores' and 'Section 2' -> 'Sample Shores Section 2'; either may be None."""
    return " ".join(x for x in (name, section) if x)


def km_across(parcels):
    """The diagonal of the box around the parcels' outlines, in km."""
    b = [p["bbox"] for p in parcels]
    return metres((min(x[0] for x in b), min(x[1] for x in b)), (max(x[2] for x in b), max(x[3] for x in b))) / 1000


def in_town(parcels, town):
    """The parcels whose GCAD situs is in the plat's town; all of them when the town is not given, is a county, or
    holds none of them. GCAD has many subdivisions of one name in different towns. (address_words turns the state into
    TX, so a TEXAS left over is Texas City.)"""
    t = [w for w in address_words(town or "") if w not in ("TX", "CITY", "OF")]
    if not t or {"CO", "COUNTY"} & set(t):
        return parcels
    # ponytail: a parcel with no situs (a reserve, a common area) is left out of its town's area, as in the prototype
    return [p for p in parcels if all(w in address_words(p["situs"] or "") for w in t)] or parcels


def capped(parcels, how):
    """(parcels, how, with how wide they are) when they are at most PLAT_KM across, else ([], too wide)."""
    km = km_across(parcels)
    return (parcels, f"{how}, {km:.2f} km across") if km <= PLAT_KM else ([], f"too wide: {len(parcels)} parcels, {km:.1f} km")


def lot_key(text):
    """'Lot 5' -> '5', 'Reserve A-1' -> 'A1', '12-A' -> '12A'."""
    return re.sub(r"[^A-Z0-9]", "", re.sub(r"\b(LOTS?|RES|RESERVE|RESTRICTED|UNRESTRICTED|TRACT|TR)\b", " ", plain_legal(text)))


def same_lot_key(a, b):
    """Lot and reserve keys: a key is itself with a letter added since (15 and 15A, A1 and A1R), unlike
    archive.same_lot, which knows no reserves; 18A and 18C differ."""
    return a == b or (a[:-1] == b and a[-1:].isalpha()) or (b[:-1] == a and b[-1:].isalpha())


def lots_of(legal):
    """(lot and reserve keys, block keys) in a GCAD legal description."""
    legal = plain_legal(legal or "")
    lots, blocks = gcad_lots_and_blocks(legal)
    reserves = re.findall(r"\bRES(?:ERVE)?\s+\(?([A-Z0-9]+(?:-[A-Z0-9]+)*)", legal)
    return {lot_key(x) for x in lots | set(reserves)} - {""}, {lot_key(x) for x in blocks} - {""}


class PlatAreas:
    """Places a Recorded Plat, from its reading, on the area of the GCAD parcels it lays out (the rules that passed
    the #54 prototype)."""

    def __init__(self, parcels):
        self.rows, self.by_word, self.lots = [], {}, {}
        for p in parcels:
            ws = name_words(p["legal"])
            for w in set(ws):
                self.by_word.setdefault(w, []).append(len(self.rows))
            self.rows.append((p, ws))
            self.lots[p["id"]] = lots_of(p["legal"])

    def naming(self, name, section=None):
        """The parcels whose legal description names the subdivision (and section) word for word. A name with no
        section never takes the parcels of a section ("Sample Shores" is not "Sample Shores Sec 2"). When the parcels
        lie in several GCAD subdivisions (a Parcel ID's first 4 digits), one that only ever names it inside a longer
        name ("West Sample Shores") is left out, as long as another names it on its own."""
        found, plain = {}, set()
        for p, _, alone in self._naming(name, section):
            found[p["id"]] = p  # a parcel can be drawn as several shapes
            if alone:
                plain.add(p["id"][:4])
        return [p for i, p in found.items() if not plain or i[:4] in plain]

    def sectioned(self, name):
        """True when GCAD gives this name a section anywhere."""
        return any(after in SECTION for _, after, _ in self._naming(name, None, any_section=True))

    def _naming(self, name, section, any_section=False):
        """(parcel, the word after the name, whether the name stands alone: no other name word just before it) for
        each place a parcel's legal description names it."""
        ws = name_words(title(name, section))
        if not ws:
            return
        n = len(ws)
        for p, w in (self.rows[i] for i in self.by_word.get(ws[0], [])):
            for i in range(len(w) - n + 1):
                after = w[i + n] if i + n < len(w) else None
                if w[i:i + n] == ws and (section or any_section or after not in SECTION):
                    yield p, after, i == 0 or w[i - 1] in BEFORE_A_NAME or any(c.isdigit() for c in w[i - 1])

    def two_places(self, parcels):
        """True when one block and lot is held by two parcels over 300 m apart: two places carry the name."""
        seen = {}
        for p in parcels:
            lots, blocks = self.lots[p["id"]]
            for lot in lots:
                if metres(seen.setdefault((tuple(sorted(blocks)), lot), p["centre"]), p["centre"]) > 300:
                    return True
        return False

    def place(self, reading):
        """(parcels, how it was placed), or ([], why it was not placed). A replat that names its lots and keeps its
        earlier subdivision's name goes only on those lots. One with a new name goes on the parcels naming its new name;
        failing that, when it lays out about as many lots as it names, on those lots under its new name. Neither ever
        goes on the earlier subdivision's whole area."""
        if reading.get("kind") == "other":
            return [], "not a subdivision plat"
        name, section, of = reading.get("name"), reading.get("section"), reading.get("replat_of")
        lots, count = reading.get("lots"), reading.get("lot_count")
        replat = reading.get("kind") == "replat" and bool(lots)
        new_name = bool(of) and not in_order(name_words(title(name, section)), name_words(of))
        if replat and not new_name:
            return self.replatted(reading, ((of, None), (of, section), (name, section)))
        area, how = self.on_name(name, section, reading.get("town"), count)
        # ponytail: the prototype's test for a replat that lays out about the lots it names; tuned on 40 plats only
        if area or not (replat and count and count <= 2 * len(lots) + 2):
            return area, how
        return self.replatted(reading, ((name, section),))

    def on_name(self, name, section, town, count):
        """(the parcels naming the subdivision and section in its town, how), or ([], why not)."""
        hits = self.naming(name, section)
        if not hits and section and not self.sectioned(name):  # GCAD gives this subdivision no sections
            hits = self.naming(name)
        hits = in_town(hits, town)
        if not hits:
            return [], "GCAD names no parcel"
        if self.two_places(hits):
            return [], "two places carry its name"
        if not count:
            return [], "lot count not read"
        n = self.lots_held(hits)
        # ponytail: limits tuned on 40 plats, against a plat of part of its area (or an area of part of the plat)
        if n > 1.5 * count + 5 or 3 * n < count:
            return [], f"lot count far off: its area holds {plural(n, 'lot')}, the plat lays out {count}"
        return capped(hits, f"on the parcels naming it: {plural(n, 'lot')} (the plat lays out {count})")

    def replatted(self, reading, names):
        """(the parcels of the lots a replat names, how) under the first of these (name, section) that holds them in
        one place, or ([], why not)."""
        for name, section in names:
            hits = in_town(self.on_lots(name, section, reading["lots"], reading.get("block")), reading.get("town")) if name else []
            if hits and not self.two_places(hits):
                return capped(hits, f"on the lots it replats: {plural(len(reading['lots']), 'lot')}")
        return [], "GCAD holds none of the lots it replats"

    def on_lots(self, name, section, lots, block):
        """The parcels naming the subdivision that hold one of the lots (and the block, when both give one); none when
        the plat names no block and the lots are in several blocks."""
        keys = {lot_key(x) for x in lots} - {""}
        out = []
        for p in self.naming(name, section) if keys else []:
            held, blocks = self.lots[p["id"]]
            if any(same_lot_key(a, b) for a in keys for b in held) and not (block and blocks and lot_key(block) not in blocks):
                out.append(p)
        return [] if not block and len({tuple(sorted(self.lots[p["id"]][1])) for p in out}) > 1 else out

    def lots_held(self, parcels):
        """How many lots the parcels hold: one per block and lot named, one per parcel that names no lot."""
        held = set()
        for p in parcels:
            lots, blocks = self.lots[p["id"]]
            held |= {(tuple(sorted(blocks)), lot) for lot in lots} or {p["id"]}  # ponytail: a condo's units count as lots
        return len(held)
