"""Build the offline map tiles for Galveston County, so the app's map needs no internet.

    python -m surveysleuth.tiles [--tiles tiles] [--aerial]

Streets: a Protomaps extract of OpenStreetMap data, zoom 0-15 (about 13 MB), cut with the pmtiles tool, which is
downloaded into the tiles folder. Aerial (--aerial): USGS The National Map USGSImageryOnly tiles, zoom 10-16
(about 24,000 requests and 285 MB, one at a time: a few hours. A re-run fetches only the missing tiles).
Needs Python only and the internet, once. Delete tiles/galveston.pmtiles to cut a newer one.
"""
import argparse
import json
import math
import platform
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

W, S, E, N = -95.233081, 29.062739, -94.369361, 29.598264  # Galveston County (Census TIGERweb, GEOID 48167)
PMTILES_VERSION = "1.31.2"  # the go-pmtiles release (BSD-3)
HEADERS = {"User-Agent": "SurveySleuth tile build (github.com/RickSmith/SurveySleuth)"}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60).read()


def tiles_in_box(z):
    """The x and y ranges of the zoom z tiles that touch the county box (Web Mercator, numbered as slippy maps are)."""
    def tile(lon, lat):
        n = 2 ** z
        return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    (x0, y0), (x1, y1) = tile(W, N), tile(E, S)
    return range(x0, x1 + 1), range(y0, y1 + 1)


def pmtiles_tool(folder):
    """The pmtiles command-line tool for this computer, downloaded into the tiles folder the first time."""
    system = platform.system()
    exe = folder / "pmtiles-cli" / ("pmtiles.exe" if system == "Windows" else "pmtiles")
    if not exe.is_file():
        arch = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x86_64"
        # The release names its macOS files with a hyphen and its Linux files as .tar.gz
        name = f"go-pmtiles{'-' if system == 'Darwin' else '_'}{PMTILES_VERSION}_{system}_{arch}.{'tar.gz' if system == 'Linux' else 'zip'}"
        print(f"Downloading {name}")
        archive = folder / name
        archive.write_bytes(get(f"https://github.com/protomaps/go-pmtiles/releases/download/v{PMTILES_VERSION}/{name}"))
        shutil.unpack_archive(archive, exe.parent)
        archive.unlink()
        exe.chmod(0o755)  # a zip file keeps no "may run" mark for macOS
    return exe


def streets(folder):
    """tiles/galveston.pmtiles: the county from the newest daily Protomaps build (older builds are deleted after a week)."""
    out = folder / "galveston.pmtiles"
    if out.is_file():
        print(f"{out} is there already.")
        return
    exe = pmtiles_tool(folder)
    # protomaps-leaflet 5 draws only version 4 of the Protomaps tiles
    build = max(b["key"] for b in json.loads(get("https://build-metadata.protomaps.dev/builds.json"))
                if b["version"].startswith("4."))
    part = folder / "galveston-part.pmtiles"
    print(f"Cutting the county from Protomaps build {build}")
    subprocess.run([exe, "extract", f"https://build.protomaps.com/{build}", part, f"--bbox={W},{S},{E},{N}", "--maxzoom=15"],
                   check=True)
    subprocess.run([exe, "verify", part], check=True)
    part.replace(out)


def aerial(folder):
    """tiles/USGSImageryOnly/{z}/{y}/{x}: each tile as USGS sent it (JPEG, or PNG over water)."""
    for z in range(10, 17):
        xs, ys = tiles_in_box(z)
        print(f"Aerial zoom {z}: {len(xs) * len(ys)} tiles")
        for x in xs:
            for y in ys:
                out = folder / f"USGSImageryOnly/{z}/{y}/{x}"
                if out.exists():
                    continue
                try:
                    data = get(f"https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}")
                except urllib.error.HTTPError as e:
                    if e.code == 404:  # open water: USGS has no tile
                        continue
                    raise
                out.parent.mkdir(parents=True, exist_ok=True)
                part = out.with_name(f"{x}.part")  # a run stopped mid-write leaves no cut-off tile behind
                part.write_bytes(data)
                part.replace(out)
                time.sleep(0.1)  # polite to a free public service


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tiles", default="tiles", type=Path, help="the tiles folder the app reads")
    ap.add_argument("--aerial", action="store_true", help="also fetch the aerial tiles (about 285 MB)")
    args = ap.parse_args()
    args.tiles.mkdir(parents=True, exist_ok=True)
    streets(args.tiles)
    if args.aerial:
        aerial(args.tiles)
    print("Done.")


if __name__ == "__main__":
    main()
