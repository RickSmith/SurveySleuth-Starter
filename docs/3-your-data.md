# 3. Get your data ready

<div class="do" markdown="1">
This page is yours, whichever option you took. Gather two things before the wizard needs them: a sample of your
scans, and your county's parcel data. The last section is for your agent.
</div>

## Your scans

What the code reads:

- **PDF files, one per Record.** A Record is one document; a Job is one piece of work with a number, and a Job can have
  several Records. The county's recorded plats can be TIF files.
- **The Job number in the file name**, like `11-0527.pdf`. The Galveston firm's numbers are two digits, a dash, four
  digits. A second Record of the same Job can be `11-0527 EC.pdf`: the number is what matters.
- **Folders by kind.** The firm had one folder of elevation certificates and letters, one folder of surveys, and folders
  of the county's recorded plats. Your folder names will differ. Your agent changes the code to match.
- **Kinds of Record it knows:** Survey, Elevation Certificate, Natural Ground Letter, Metes-and-Bounds Description,
  Floor Plan. Other kinds are read and listed too, with fewer details.
- **Typed or scanned:** a typed Elevation Certificate is read from its text. Everything else is looked at by the reader.

<div class="warn" markdown="1">
**The archive stays where it is.** The code only reads it. It never writes there, and neither does your agent.
A network drive is fine; [page 5](5-every-day.md#your-scans-on-a-network-drive) says how. Keep your backup anyway.
</div>

### Make a sample

<div class="do" markdown="1">
Make a new folder `C:\SurveySleuth\Data`. Inside it, the same folder names as your archive. Copy about 30 Records in:
some of each kind, some old, some new, and a few at addresses you know well (which lot, which neighbours).
</div>

The wizard starts on the sample, so each try takes minutes instead of hours. The whole archive comes at the end.

## Your county's data

<div class="do" markdown="1">
1. **Parcels.** Download the parcel shapefile from your appraisal district or county GIS site. Search for
   "your county appraisal district GIS data" or "your county parcels shapefile". It is a zip holding `.shp`, `.dbf`
   and `.prj` files, with the Parcel ID, the situs (street) address, the legal description and the acres for every
   parcel. Save it as `C:\SurveySleuth\parcels.zip`. If the site offers a choice of coordinate system, take
   **WGS 84, latitude and longitude**: it saves your agent a step.
2. **Your Parcel ID form.** An example from the appraisal district site, and what your Records call it. The Galveston
   firm's Records print it as "File No.".
3. **Your county's FEMA FIRM prefix.** Open any FIRM panel for your county at https://msc.fema.gov. Its number starts
   with six characters, like `48167C` for Galveston County, Texas. Yours is different.
</div>

Benchmarks need nothing: NGS publishes them, and ingestion fetches the county's.

## The test set

Up to twelve addresses you know the answers for. Your agent writes them into a file; you supply the knowledge. The
check then proves the setup, and proves it again after every change.

<div class="do" markdown="1">
For each address, be ready to say:

- the address, and the Jobs you know lie within half a mile of it, the ones you expect to see;
- Jobs that may or may not show (either way), if any;
- traps, if any: a Job that must be listed for a reason you give, or one that must not be;
- and one or two addresses where you did no Jobs. For those, the flood zone, the BFE, the FIRM panel and the Parcel ID,
  so the check can verify the public data too.
</div>

The file's shape, for your agent (`testset/test-set.json`):

```json
{"addresses": [
  {"id": "a01", "address": "12 Example Dr, Yourtown, TX 77550", "lat": 29.3, "lon": -94.8,
   "expect_no_jobs": false,
   "expected_jobs": [{"job": "07-0001"}, {"job": "11-0527"}],
   "either_way_jobs": [{"job": "09-0100"}],
   "traps": [{"job": "08-0200", "kind": "must be listed", "why": "next door, placed by its Job"}]},
  {"id": "a02", "address": "88 Sample Blvd, Yourtown, TX 77551", "lat": 29.31, "lon": -94.81,
   "expect_no_jobs": true, "expected_jobs": [],
   "parcel_id": "1234-0001-0001-000",
   "authoritative": "FEMA flood zone AE, BFE 11 ft NAVD 88 (FIRM panel 48167C0000X, effective 2017-07-07). GCAD parcel 1234-0001-0001-000."}
]}
```

`kind` is `must be listed` or `must not be listed`. `python -m surveysleuth.check` runs every address and prints pass or fail.

## For your agent: what was built for Galveston County

Each row is a value in the code that is true for Galveston County, Texas and for the firm's archive. The agent changes
each one in step 5 of the wizard. You can skip this table.

| File | Name | What it is |
|---|---|---|
| `surveysleuth/ingest.py` | `CERTIFICATE_FOLDER`, `SURVEY_FOLDER`, `PLAT_GROUP` | the archive's folder names: certificates and letters; surveys; the county's recorded plats |
| `surveysleuth/archive.py` | `JOB_RE` | the Job number form: two digits, a dash, four digits |
| `surveysleuth/archive.py` | `COUNTY_BOX` | a lat/lon box around the county. A Record placed outside it is flagged. NGS benchmarks are fetched for it |
| `surveysleuth/archive.py` | `AUTHORITIES` | the name of the parcel source, "Galveston CAD parcels" |
| `surveysleuth/gcad.py` | `read_parcels` | the file names inside the zip (`parcels.shp`, `parcels.dbf`) and the field names (`GEOID`, `SITUS`, `LEGAL`, `ACRES`) |
| `surveysleuth/gcad.py` | `to_latlon` | the map projection: NAD83 Texas South Central, EPSG 2278, US survey feet. A WGS 84 download makes this a pass-through. Another state plane zone needs its own constants, and a Transverse Mercator zone its own inverse formula (Snyder) |
| `surveysleuth/sources.py` | `DFIRM_ID` | the county's FEMA FIRM prefix |
| `surveysleuth/sources.py` | `US_FT_PER_M` | NAVD 88 heights in US survey feet, as Texas publishes them |
| `surveysleuth/tiles.py` | `W, S, E, N` | the county's box for the offline map |
| `surveysleuth/app.py` | `PARCEL_ID_RE`, `NOT_FOUND` | the Parcel ID form, `1234-0001-0001-000`, and the message that shows it |
| `surveysleuth/vision.py`, `surveysleuth/plats.py` | the prompts | they tell the model "a Texas land-surveying firm" and "Galveston County" |
| `surveysleuth/plats.py` | `PLAT` | the recorded plat file name form: volume and page, `7_12.tif` |
| `surveysleuth/static/app.js` | the search box text, the "GCAD" labels | what the person sees |
| `tests/` | example points and addresses | they lie in Galveston County; move them into your county when `COUNTY_BOX` changes |
| `CONTEXT.md` | the Parcel ID example | the glossary |

The file name `galveston.pmtiles` is only a file name. It can stay.

<p class="next" markdown="1">[Next: Hand it to your agent](4-hand-it-to-your-agent.md)</p>
