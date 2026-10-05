# 5. Every day

Your agent wrote the exact commands for your computer into `OFFICE.md`. This page says what they do.

## Start the app

In a terminal, in the project folder:

```
cd C:\SurveySleuth
python -m surveysleuth.app --archive <your archive path>
```

It prints `Open http://127.0.0.1:8765/`. Open that address in a browser. The app runs until you press Ctrl+C in the
terminal. It needs no internet: the map comes from `tiles/` and the data from `index/`. Before the offline map is
built, add `--live-map`, and the map comes from the internet.

## Search

Type an address or a Parcel ID. Pick a distance: a quarter, a half, one or two miles. You get the Search summary (a
briefing in which every claim cites its Record or its source), the Jobs nearby with their Records, and the map with the
parcel, the flood zone and the benchmarks. Click a Record to open it. Open PDF shows the original. Plat opens the
county's recorded plat when it is held.

## New scans

Add them to the archive, in the same folders, then run ingestion again (the command is in `OFFICE.md`). Only new or
changed Records are read by the model; everything else is reused. Start the app again afterwards.

## A Record placed wrong, or not at all

`index/report.json` lists every Record without a Location and every flagged one. To place a Record by hand, add it to
`overrides.json` in the project folder, with its position and why, and run ingestion again:

```json
{"Surveys/11-0527.pdf": {"lat": 29.30, "lon": -94.80, "why": "the lot on Example Dr, confirmed from the field notes"}}
```

The key is the Record's path inside the archive.

## Fresh county data

New parcels: a new `parcels.zip`, then ingestion again. New flood zones or benchmarks: delete `index/fema.json` or
`index/ngs.json`, then ingestion again.

## The check

```
python -m surveysleuth.check
```

runs your test addresses and prints pass or fail for each. Run it after a change, or after a big batch of new scans.

## Keep it to yourselves

The license lets your company use this and change it. It does not let you give it to other companies, sell it, or
publish your copy.
