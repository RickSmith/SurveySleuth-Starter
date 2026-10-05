# Technical reference

How SurveySleuth runs, as built for Galveston County, Texas. This page is for your agent and for the curious. The
walkthrough does not need it.

## Data

Raw data is not stored in git. Keep it locally:

- `EL_GAL.zip` → extracted to `Data/EL_GAL_Data/`
- `SUR_GAL.zip` → extracted to `Data/SUR_GAL_Data/`

## Run it

Needs Python 3.11. Ingestion also needs Poppler on PATH, Ollama with `qwen3.6:35b` (it reads the Survey folder)
and Pillow (`pip install pillow`, to read a Survey's buildings, easements and setback lines).
The search app needs Python only. It finds a typed address in the saved GCAD data, and asks the Census Geocoder
(online) only when GCAD does not have it.

```sh
python -m surveysleuth.ingest Data index --parcels parcels.zip --overrides overrides.json
                                             # Legacy archive folder -> index folder (a few minutes)
                                             # --model qwen3.6:27b: the smaller model (a 24 GB card); answers are kept per model
python -m surveysleuth.tiles --aerial        # offline map tiles -> tiles/ (streets: seconds; aerial: hours, run again to resume)
python -m surveysleuth.app                   # reads index/, Data/ (for Open PDF), testset/test-set.json and tiles/; open http://127.0.0.1:8765/
python -m surveysleuth.app --host 0.0.0.0    # the same, reachable from every computer on the office network
python -m unittest                           # tests on fake data: no Firm data, Poppler or network
python -m surveysleuth.check                 # success check: the 12 test addresses on the real index, pass or fail
```

`parcels.zip` is the GCAD "Parcels with data" shapefile from https://galvestoncad.org/gis-data/.
`overrides.json` is optional. It places Records by hand: `{"EL_GAL_Data/07-0001.pdf": {"lat": 29.30, "lon": -94.80, "why": "..."}}`.
Ingestion reads only these folders of the archive folder: `EL_GAL_Data` (certificates and letters), `SUR_GAL_Data`
(Surveys) and plat group folders such as `Galveston County Plats Group 1` (the county's Recorded Plats). It skips every
other folder, and every file at the top of the archive folder, without reading it. A Recorded Plat is known by the
volume and page in its file name (`7_12.tif`) and gets a page image in `index/pages/plats/`. The vision model reads
each plat's title (name, section, kind, the lots a replat names, lot count, town, date), and ingestion places it on
the area of the GCAD parcels it lays out when the rules allow (see `plats.py`; the index keeps the area's Parcel IDs).
The first run draws about 4,000 plat pages (about 0.5 GB, a few minutes) and reads them for about 8 hours; stop it
at any time and run it again to go on. The vision model reads the plat volume and page a Survey cites; when that
Galveston County plat is held, the Record viewer's Plat button opens it. A search lists the placed Recorded Plats whose
area holds the searched parcel, and the Search summary cites them; each opens in the Record viewer.
The ingestion report (`index/report.json`) lists every Record with no Location, every flagged Record, every skipped
file with the reason (for a skipped folder, the reason names the folder), and the Recorded Plats placed and not placed.
Ingestion draws every page of every Record into `index/pages/` (with a certificate's building photo), so the
laptop needs no Poppler; pages already drawn are kept. Ingestion saves every vision-model answer in `index/vision.jsonl`, so a re-run asks the model only about new or
changed Records. The first run also saves the county's FEMA flood zones (`index/fema.json`) and NGS Benchmarks (`index/ngs.json`).
Later runs reuse them. Delete one to fetch it again. Flood data: FEMA National Flood Hazard Layer.

`index/` and `testset/` hold Firm data. They are gitignored.

The map needs no internet once `tiles/` is built: streets from a Protomaps extract of OpenStreetMap, and an aerial
layer from USGS The National Map. The app serves the map code too (`surveysleuth/static/vendor/`).
`python -m surveysleuth.app --live-map` uses live OpenStreetMap and USGS tiles from the internet instead. Without
`tiles/galveston.pmtiles` and with no `--live-map`, the app stops and says how to build it. `tiles/` is gitignored.
Map services and data available from U.S. Geological Survey, National Geospatial Program.

## Licenses and sources

The code is under the PolyForm Internal Use License 1.0.0 (`LICENSE`). Copyright (c) 2026 Rick Smith.
The map code in `surveysleuth/static/vendor/` (Leaflet, PMTiles, protomaps-leaflet) is under its own open-source
licenses, listed in `LICENSES.txt` there. Map data: OpenStreetMap contributors, via Protomaps; USGS The National Map.
Flood data: FEMA National Flood Hazard Layer. Benchmarks: NGS. Addresses: the US Census Geocoder.
