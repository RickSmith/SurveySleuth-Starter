"""The search app: a Python standard-library web server and one page (layout B, "Briefing first").

    python -m surveysleuth.app [--index index] [--archive Data] [--testset testset/test-set.json] [--tiles tiles]
                               [--live-map] [--port 8765] [--host 127.0.0.1]

Reads only the index folder, plus the test addresses from the local test set file when it is there. Serves the page
images drawn at ingestion and the original PDFs (the Legacy archive folder) for the Record viewer.
A typed address that the saved GCAD situs data does not have goes to the Census Geocoder, when online.
The map reads the tiles folder (built by python -m surveysleuth.tiles), so it needs no internet;
--live-map uses live tiles from the internet instead.
Needs Python only: no pip installs, no Poppler.
"""
import argparse
import json
import platform
import re
import sys
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from surveysleuth.archive import centre, in_county, nearby_search, pages_dir
from surveysleuth.gcad import Gcad
from surveysleuth.sources import census_geocoder
from surveysleuth.tiles import E, N, S, W

STATIC = Path(__file__).parent / "static"
# The page, and the map code it loads from the app, not a CDN (vendor/LICENSES.txt)
PAGES = {"/": "index.html", **{f"/{name}": name for name in (
    "app.js", "styles.css", "vendor/leaflet.js", "vendor/leaflet.css", "vendor/protomaps-leaflet.js", "vendor/pmtiles.js",
    "vendor/images/layers.png", "vendor/images/layers-2x.png")}}
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".png": "image/png"}
DISTANCES = (0.25, 0.5, 1.0, 2.0)
PARCEL_ID_RE = re.compile(r"[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{3}")
NOT_FOUND = "Could not find that address. Check its spelling, add its city or ZIP, or type its Parcel ID (like 1234-0001-0001-000)."
TILE_RE = re.compile(r"/tiles/(galveston\.pmtiles|USGSImageryOnly/[0-9]+/[0-9]+/[0-9]+)")


def test_addresses(path):
    """Each test address and its own point. The test set's expected Jobs and distances are dropped here,
    so Nearby search can never read them."""
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {a["id"]: {"id": a["id"], "address": a["address"], "lat": a["lat"], "lon": a["lon"]} for a in data["addresses"]}


def load_index(folder):
    """The index folder, as Nearby search reads it."""
    def read(name):
        try:
            return json.loads((folder / name).read_text(encoding="utf-8"))
        except FileNotFoundError:
            sys.exit(f"{folder / name} is missing. Run ingestion again to build the whole index folder.")
    index = {**read("index.json"), "gcad": Gcad(read("parcels.json")), "fema": read("fema.json"), "ngs": read("ngs.json")}
    index["by_id"] = {r["id"]: r for r in index["records"]}
    return index


def record_file(index, index_dir, archive, kind, q):
    """The file for /page?id=&n=, /photo?id= or /pdf?id=, as a resolved path, or None. Only Records in the index are
    served, only from the index folder and the Legacy archive folder, and an id with '..' is refused."""
    rid = q.get("id", "")
    rec = index["by_id"].get(rid)
    if not rec or ".." in rid:
        return None
    if kind == "pdf":
        base, path = archive, archive / rid
    elif kind == "photo":
        base, path = index_dir, pages_dir(index_dir, rid) / "photo.jpg"
    else:
        n = q.get("n", "1")
        if not (n.isascii() and n.isdecimal() and len(n) <= 4 and 1 <= int(n) <= (rec.get("pages") or 0)):
            return None
        base, path = index_dir, pages_dir(index_dir, rid) / f"{int(n)}.jpg"
    path = path.resolve()
    return path if path.is_file() and base.resolve() in path.parents else None


def plat_file(index, index_dir, q):
    """The page image for /plat?id=7_12, as a resolved path, or None. Only a Recorded Plat in the index is served, and
    only from the index folder's pages/plats/."""
    plat = index.get("plats", {}).get(q.get("id", ""))
    if not plat or not plat.get("image"):
        return None
    folder = (index_dir / "pages" / "plats").resolve()
    path = (index_dir / plat["image"]).resolve()
    return path if path.is_file() and folder in path.parents else None


def map_tile(tiles, path):
    """(bytes, type) for /tiles/galveston.pmtiles (the streets) or /tiles/USGSImageryOnly/{z}/{y}/{x} (the aerial),
    from the tiles folder, or None. Nothing else in the folder is served. A tile keeps the type USGS sent it as."""
    m = TILE_RE.fullmatch(path)
    if not m or not (tiles / m[1]).is_file():
        return None
    data = (tiles / m[1]).read_bytes()
    if m[1].endswith(".pmtiles"):
        return data, "application/octet-stream"
    return data, "image/png" if data.startswith(b"\x89PNG") else "image/jpeg"


def find_place(gcad, text, geocoder):
    """(point, label, Parcel ID or None) for a typed Parcel ID or street address, or the message to show when it is not
    found. An address is looked up in the saved GCAD situs data, with no network; the geocoder is asked only when GCAD
    has no such street at all."""
    if PARCEL_ID_RE.fullmatch(text):
        pieces, split = gcad.pieces(text)
        if not pieces:
            return f"No GCAD parcel has the Parcel ID {text}. Check it, or type the address."
        return centre(pieces), f"Parcel {text}" + (" (split since: searched from its pieces today)" if split else ""), text
    found = gcad.matches(text)
    if len(found) > 1:
        places = sorted(parcels[0]["situs"] for parcels in found)
        return f"That address is in more than one place: {'; '.join(places[:3])}{'; …' if len(places) > 3 else ''}. Add its city or ZIP."
    if found:
        return centre(found[0]), found[0][0]["situs"], found[0][0]["id"]
    # ponytail: the timeout does not cover the name lookup, which can hang on Wi-Fi with no internet;
    # run the geocoder in a thread with its own deadline if that happens
    point = geocoder(text)
    return (point, text, None) if point and in_county(point) else NOT_FOUND


def search(index, addresses, q, geocoder=partial(census_geocoder, timeout=3)):  # offline, a typed search fails fast
    """(status, body) for /api/search?id=T01&r=0.5 or ?q=typed address or Parcel ID&r=0.5."""
    try:
        r = float(q.get("r", "0.5"))
    except ValueError:
        r = None
    if r not in DISTANCES:
        return 400, {"error": "Pick a distance of ¼, ½, 1 or 2 miles."}
    typed = q.get("q", "").strip()
    test_address = addresses.get(q.get("id")) or next((a for a in addresses.values() if typed and typed.lower() in (
        a["address"].lower(), a["address"].split(",")[0].lower())), None)
    if test_address:
        # A test point can sit in the street, just outside its parcel: its address finds the parcel then
        at_address = index["gcad"].at_address(test_address["address"])
        point, label = (test_address["lat"], test_address["lon"]), test_address["address"]
        parcel_id = at_address[0]["id"] if at_address else None
    else:
        found = find_place(index["gcad"], typed, geocoder) if typed else NOT_FOUND
        if isinstance(found, str):
            return 404, {"error": found}
        point, label, parcel_id = found
    answer = nearby_search(index, point, r, parcel_id)
    answer["query"]["label"] = label
    return 200, answer


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--index", default="index", type=Path, help="the index folder from ingestion")
    ap.add_argument("--archive", default="Data", type=Path, help="the Legacy archive folder (the PDFs), for Open PDF")
    ap.add_argument("--testset", default="testset/test-set.json", type=Path, help="the local test set file, if any")
    ap.add_argument("--tiles", default="tiles", type=Path, help="the map tiles folder, from python -m surveysleuth.tiles")
    ap.add_argument("--live-map", action="store_true", help="show live map tiles from the internet, not the tiles folder")
    ap.add_argument("--port", default=8765, type=int)
    ap.add_argument("--host", default="127.0.0.1", help="0.0.0.0 serves the whole office network, not only this computer")
    args = ap.parse_args()
    index = load_index(args.index)
    addresses = test_addresses(args.testset)
    if not args.live_map and not (args.tiles / "galveston.pmtiles").is_file():
        sys.exit(f"{args.tiles / 'galveston.pmtiles'} is missing. Build the map tiles with: python -m surveysleuth.tiles --aerial\n"
                 "Or show live map tiles from the internet: python -m surveysleuth.app --live-map")
    map_setup = {"live": args.live_map, "aerial": args.live_map or (args.tiles / "USGSImageryOnly").is_dir(),
                 "box": [[S, W], [N, E]]}  # the tiles' box, which the map stays inside

    class Handler(BaseHTTPRequestHandler):
        def send(self, status, body, ctype="application/json; charset=utf-8"):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if ".." in urlparse(self.path).path:  # a search query may hold ".."; record_file checks ids itself
                return self.send(400, {"error": "Bad path."})
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            if url.path == "/api/start":
                return self.send(200, {"counts": index["counts"], "map": map_setup,
                                       "addresses": [{"id": a["id"], "address": a["address"]} for a in addresses.values()]})
            if url.path == "/api/search":
                return self.send(*search(index, addresses, q))
            if url.path in ("/page", "/photo", "/pdf"):
                kind = url.path[1:]
                path = record_file(index, args.index, args.archive, kind, q)
                if not path:
                    return self.send(404, {"error": "Not found."})
                return self.send(200, path.read_bytes(), "application/pdf" if kind == "pdf" else "image/jpeg")
            if url.path == "/plat":
                path = plat_file(index, args.index, q)
                return self.send(200, path.read_bytes(), "image/png") if path else self.send(404, {"error": "Not found."})
            if url.path.startswith("/tiles/"):
                tile = map_tile(args.tiles, url.path)
                if not tile:
                    return self.send(404, {"error": "Not found."})
                return self.send(200, *tile)
            if url.path in PAGES:
                name = PAGES[url.path]
                return self.send(200, (STATIC / name).read_bytes(), TYPES[Path(name).suffix])
            self.send(404, {"error": "Not found."})

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"SurveySleuth: {index['counts']['records']} Records, {len(addresses)} test addresses.")
    if args.live_map:
        print("Map: live tiles from the internet.")
    else:
        print(f"Map: offline tiles from {args.tiles}{'' if map_setup['aerial'] else ' (streets only: no aerial tiles)'}.")
    where = f"http://{platform.node()}:{args.port}/ from any computer in the office" if args.host == "0.0.0.0" else f"http://127.0.0.1:{args.port}/"
    print(f"Open {where}  (Ctrl+C to stop)")
    server.serve_forever()


if __name__ == "__main__":
    main()
