"""Source fetchers: the county's FEMA NFHL flood zones and FIRM panels, and its NGS vertical Benchmarks (decision #4),
saved at ingestion; and the Census Geocoder, asked at ingestion and by a typed search. All are Authoritative sources;
FEMA asks for acknowledgement in products made from the NFHL.
"""
import json
import time
from datetime import date, datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from surveysleuth.archive import COUNTY_BOX
from surveysleuth.gcad import bbox_of

NFHL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer"
DFIRM_ID = "48167C"  # Galveston County
US_FT_PER_M = 3.2808333  # US survey feet, as NAVD 88 heights are given in Texas


def get_json(url, tries=6):
    """FEMA drops about a third of connections (decision #4), so try again with a growing pause."""
    for i in range(tries):
        try:
            with urlopen(Request(url, headers={"User-Agent": "SurveySleuth"}), timeout=120) as r:
                return json.load(r)
        except (OSError, ValueError):
            if i == tries - 1:
                raise
            time.sleep(2 ** i)


def census_geocoder(address, timeout=10):
    """The Census Geocoder's (lat, lon) for 'street, city', or None when it has no match or the computer is offline."""
    url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?" + urlencode(
        {"address": f"{address}, TX", "benchmark": "Public_AR_Current", "format": "json"})
    try:
        with urlopen(url, timeout=timeout) as r:
            matches = json.load(r)["result"]["addressMatches"]
    except (OSError, ValueError, KeyError):
        return None
    return (matches[0]["coordinates"]["y"], matches[0]["coordinates"]["x"]) if matches else None


def nfhl_layer(layer, fields):
    """Every feature of one NFHL layer in the county, with its shape as rings of [lat, lon]."""
    out = []
    while True:
        q = urlencode({"where": f"DFIRM_ID='{DFIRM_ID}'", "outFields": fields, "returnGeometry": "true", "outSR": 4326,
                       "geometryPrecision": 7, "resultOffset": len(out), "resultRecordCount": 200, "f": "json"})
        page = get_json(f"{NFHL}/{layer}/query?{q}")["features"]
        out += [{"attrs": f["attributes"], "shape": [[[lat, lon] for lon, lat in ring] for ring in f["geometry"]["rings"]]}
                for f in page if (f.get("geometry") or {}).get("rings")]
        if len(page) < 200:
            return out


def fetch_fema():
    """{saved, zones: [{zone, subtype, bfe, sfha, datum, shape, bbox}], panels: [{panel, date, shape, bbox}]}."""
    zones = [{"zone": f["attrs"]["FLD_ZONE"], "subtype": f["attrs"]["ZONE_SUBTY"],
              "bfe": f["attrs"]["STATIC_BFE"] if (f["attrs"]["STATIC_BFE"] or -9999) > -9000 else None,
              "sfha": f["attrs"]["SFHA_TF"] == "T", "datum": f["attrs"]["V_DATUM"] or None, "shape": f["shape"], "bbox": bbox_of(f["shape"])}
             for f in nfhl_layer(28, "FLD_ZONE,ZONE_SUBTY,STATIC_BFE,SFHA_TF,V_DATUM")]
    panels = [{"panel": f["attrs"]["FIRM_PAN"], "shape": f["shape"], "bbox": bbox_of(f["shape"]),
               "date": f["attrs"]["EFF_DATE"] and datetime.fromtimestamp(f["attrs"]["EFF_DATE"] / 1000, timezone.utc).date().isoformat()}
              for f in nfhl_layer(3, "FIRM_PAN,EFF_DATE")]
    return {"saved": date.today().isoformat(), "zones": zones, "panels": panels}


def fetch_ngs(box=COUNTY_BOX):
    """NGS Benchmarks: marks with a published orthometric height that are not lost or destroyed, and not a GPS
    antenna reference point (ARP). [{id, name, lat, lon, height_ft, datum, condition, recovered}]. A query returns
    at most 500 marks, so a full box is split in four until each part fits."""
    lat0, lon0, lat1, lon1 = box
    marks = get_json("https://geodesy.noaa.gov/api/nde/bounds?" + urlencode(
        {"minlat": lat0, "maxlat": lat1, "minlon": lon0, "maxlon": lon1}))
    if len(marks) >= 500:
        mlat, mlon = (lat0 + lat1) / 2, (lon0 + lon1) / 2
        parts = [(lat0, lon0, mlat, mlon), (lat0, mlon, mlat, lon1), (mlat, lon0, lat1, mlon), (mlat, mlon, lat1, lon1)]
        return list({m["id"]: m for part in parts for m in fetch_ngs(part)}.values())
    return [{"id": m["pid"], "name": m["name"].strip(), "lat": float(m["lat"]), "lon": float(m["lon"]),
             "height_ft": round(float(m["orthoHt"]) * US_FT_PER_M, 2), "datum": m["vertDatum"].strip(),
             "condition": m["condition"].strip(), "recovered": m["lastRecovered"].strip()[:4]}
            for m in marks if m["orthoHt"].strip() and not any(w in m["condition"] for w in ("NOT FOUND", "DESTROYED"))
            and not m["name"].strip().endswith("ARP") and not m["corsId"].strip()]
