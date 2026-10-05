"""GCAD parcels: read the county's "Parcels with data" shapefile zip (https://galvestoncad.org/gis-data/),
and look a parcel up by Parcel ID or by street address (situs).

Keeps Parcel ID, situs address, legal description, acres, the parcel shape and its centre, in lat/long.
The owner fields are never read.
"""
import math
import re
import struct
import zipfile

# NAD83 / Texas South Central (EPSG 2278, US survey feet) -> NAD83 lat/long: Lambert conformal conic inverse (Snyder)
A, F = 6378137.0, 1 / 298.257222101
E = math.sqrt(2 * F - F * F)
FT = 0.3048006096012192
P1, P2, P0, L0 = (math.radians(v) for v in (28.38333333333333, 30.28333333333333, 27.83333333333333, -99.0))
FE, FN = 1968500.0 * FT, 13123333.33333333 * FT


def _m(p):
    return math.cos(p) / math.sqrt(1 - (E * math.sin(p)) ** 2)


def _t(p):
    s = E * math.sin(p)
    return math.tan(math.pi / 4 - p / 2) / ((1 - s) / (1 + s)) ** (E / 2)


N = (math.log(_m(P1)) - math.log(_m(P2))) / (math.log(_t(P1)) - math.log(_t(P2)))
AF = A * _m(P1) / (N * _t(P1) ** N)
RHO0 = AF * _t(P0) ** N


def to_latlon(x_ft, y_ft):
    x, y = x_ft * FT - FE, RHO0 - (y_ft * FT - FN)
    t = (math.hypot(x, y) / AF) ** (1 / N)
    phi = math.pi / 2 - 2 * math.atan(t)
    for _ in range(4):  # converges to well under a millimetre
        s = E * math.sin(phi)
        phi = math.pi / 2 - 2 * math.atan(t * ((1 - s) / (1 + s)) ** (E / 2))
    return round(math.degrees(phi), 6), round(math.degrees(math.atan2(x, y) / N + L0), 6)


def polygon(content):
    """(rings in state plane feet, area centroid) of one shapefile polygon record, or None."""
    if struct.unpack_from("<i", content, 0)[0] not in (5, 15, 25):
        return None
    nparts, npts = struct.unpack_from("<ii", content, 36)
    starts = list(struct.unpack_from(f"<{nparts}i", content, 44)) + [npts]
    pts = struct.unpack_from(f"<{2 * npts}d", content, 44 + 4 * nparts)
    rings = [[(pts[2 * i], pts[2 * i + 1]) for i in range(a, b)] for a, b in zip(starts, starts[1:])]
    a2 = cx = cy = 0.0
    for ring in rings:
        for (x0, y0), (x1, y1) in zip(ring, ring[1:]):
            c = x0 * y1 - x1 * y0
            a2, cx, cy = a2 + c, cx + (x0 + x1) * c, cy + (y0 + y1) * c
    if abs(a2) < 1e-9:
        return rings, (pts[0], pts[1])
    return rings, (cx / (3 * a2), cy / (3 * a2))


def bbox_of(shape):
    """[min lat, min lon, max lat, max lon] of a shape (rings of [lat, lon])."""
    lats, lons = [q[0] for ring in shape for q in ring], [q[1] for ring in shape for q in ring]
    return [min(lats), min(lons), max(lats), max(lons)]


def read_parcels(path):
    """[{id, situs, legal, acres, centre: [lat, lon], shape: [ring of [lat, lon], ...]}] from the GCAD zip."""
    z = zipfile.ZipFile(path)
    dbf, shp = z.open("parcels.dbf"), z.open("parcels.shp")
    n, header_len, rec_len = struct.unpack("<IHH", dbf.read(32)[4:12])
    fields, off, rest = {}, 1, dbf.read(header_len - 32)
    for i in range(0, len(rest) - 1, 32):
        if rest[i] == 0x0D:
            break
        name, size = rest[i:i + 11].split(b"\0")[0].decode(), rest[i + 16]
        fields[name] = (off, off + size)
        off += size
    keep = {"id": fields["GEOID"], "situs": fields["SITUS"], "legal": fields["LEGAL"], "acres": fields["ACRES"]}
    shp.read(100)
    out = []
    for _ in range(n):
        row = dbf.read(rec_len)
        size = struct.unpack(">ii", shp.read(8))[1] * 2
        poly = polygon(shp.read(size))
        if not poly:
            continue
        rings, c = poly
        p = {k: row[a:b].decode("latin1").strip() for k, (a, b) in keep.items()}
        p["acres"] = float(p["acres"] or 0)
        p["centre"] = list(to_latlon(*c))
        p["shape"] = [[to_latlon(x, y) for x, y in ring] for ring in rings]  # tuples: smaller than lists
        p["bbox"] = bbox_of(p["shape"])
        out.append(p)
    return out


SHORT = {"DRIVE": "DR", "STREET": "ST", "AVENUE": "AVE", "AV": "AVE", "ROAD": "RD", "CIRCLE": "CIR", "LANE": "LN",
         "COURT": "CT", "BOULEVARD": "BLVD", "PLACE": "PL", "PARKWAY": "PKWY", "TRAIL": "TRL", "HIGHWAY": "HWY",
         "COVE": "CV", "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W"}
STREET_TYPES = {"DR", "ST", "AVE", "RD", "CIR", "LN", "CT", "BLVD", "PL", "PKWY", "TRL", "HWY", "CV", "WAY", "LOOP"}


def address_words(text):
    """'12 Example Drive (Shop)' -> ['12', 'EXAMPLE', 'DR']: no note in brackets, no punctuation, short street types,
    and the state as TX (but not in Texas City)."""
    text = re.sub(r"\bTEXAS\b(?!\s+CITY)", "TX", re.sub(r"\(.*?\)", " ", text.upper()))
    return [SHORT.get(w, w) for w in re.sub(r"[^A-Z0-9 ]", " ", text).split()]


def in_order(words, rest):
    """True when the words are all in rest, in the same order (with other words between them allowed)."""
    rest = iter(rest)
    return all(w in rest for w in words)


class Gcad:
    """The county's GCAD parcels, looked up by Parcel ID and by street address (situs)."""

    def __init__(self, parcels):
        self.parcels = list(parcels)
        self.by_id, self.by_first14, self.by_number = {}, {}, {}
        for p in parcels:
            self.by_id.setdefault(p["id"], []).append(p)  # a parcel can be drawn as several shapes
            self.by_first14.setdefault(p["id"][:14], []).append(p)
            words = address_words(p["situs"])
            if words:
                self.by_number.setdefault(words[0], []).append((words, p))

    def pieces(self, pid):
        """(parcels, split): the parcel with this ID, else the pieces it was split into since (same first 14 characters)."""
        if pid in self.by_id:
            return self.by_id[pid], False
        return (self.by_first14.get(pid[:14], []), True) if pid else ([], False)

    def at_address(self, address):
        """The parcels at a street address, or [] when GCAD has no such situs, or more than one (see matches)."""
        found = self.matches(address)
        return found[0] if len(found) == 1 else []

    def matches(self, address):
        """[parcels at one situs, ...] for each situs a street address can be: 'street, city' as a Record prints it, or as
        a surveyor types it, with or without commas, city and ZIP ('12 sample dr 77550'). With a comma, the city or ZIP
        only chooses when the street is in two towns (a Record's city is often not GCAD's); with no comma, the words after
        the street must be the situs's city, state or ZIP. GCAD often leaves the street type out, so '12 Sample Drive'
        also finds the situs '12 SAMPLE ...', but never '12 SAMPLE CT ...'."""
        street, comma, place = address.partition(",")
        words, place = address_words(street), address_words(place)
        splits = [(words, place)] if comma else [(words[:k], words[k:]) for k in range(len(words), 1, -1)]
        for street_words, place_words in splits:
            on_street = self._on_street(street_words)
            one_town = len({tuple(w) for w, _, _ in on_street}) == 1
            found = {}
            for w, p, n in on_street:
                if in_order(place_words, w[n:]) or (comma and one_town):
                    found.setdefault(tuple(w), []).append(p)
            if found:
                return list(found.values())
        return []

    def _on_street(self, street):
        """(situs words, parcel, n) for every situs whose first n words are this street, or this street without its
        street type (when the situs has no other street type there). The words after the first n are its city, state, ZIP."""
        found = [(w, p, len(street)) for w, p in self._starting(street)]
        if not found and len(street) > 2 and street[-1] in STREET_TYPES:
            n = len(street) - 1
            found = [(w, p, n) for w, p in self._starting(street[:-1]) if len(w) == n or w[n] not in STREET_TYPES]
        return found

    def _starting(self, street):
        """(situs words, parcel) for every situs that starts with these street words."""
        return [(w, p) for w, p in self.by_number.get(street[0], []) if w[:len(street)] == street] if street else []
