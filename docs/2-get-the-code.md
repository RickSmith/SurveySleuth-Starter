# 2. Get the code

Took the short way on page 1? Your agent does this page. Skip to [page 3](3-your-data.md).

## Pick a folder

A short path with no spaces: `C:\SurveySleuth` on Windows, `~/SurveySleuth` on a Mac. The rest of this walkthrough
uses `C:\SurveySleuth`.

## Option A: copy it to your computer

No GitHub account needed. In the terminal:

```
git clone https://github.com/RickSmith/SurveySleuth-Starter.git C:\SurveySleuth
```

Your copy lives on your computer only. The changes your agent makes stay there.

## Option B: your own private copy on GitHub

This keeps your office's version safe on GitHub, so a second computer can get it later.

1. Open https://github.com/RickSmith/SurveySleuth-Starter and click **Use this template**, then **Create a new repository**.
2. Give it a name. Choose **Private**: the license does not allow publishing your copy. Click **Create repository**.
3. On your new repository's page, click the green **Code** button and copy the address. Then:

```
git clone https://github.com/YOUR-NAME/YOUR-REPOSITORY.git C:\SurveySleuth
```

## Prove it runs

```
cd C:\SurveySleuth
python -m unittest
```

The last line says `OK`. These tests run on made-up data: no scans, no model, no internet. When they pass, Python is set up right.

## What is in the folder

- `surveysleuth/` is the code. `ingest.py` reads the scans, `app.py` is the search app, `tiles.py` builds the offline
  map, `check.py` runs your test addresses.
- `tests/` are the tests on made-up data.
- `docs/` is this walkthrough and the wizard prompt.
- `CONTEXT.md` defines the words the code uses: Record, Job, Survey, Location, Fact. Worth five minutes: your agent
  uses these words when it talks to you.
- `README.md` is the technical reference: every command and what it does.
- `LICENSE` is the license.

These folders appear later, and never go to GitHub: `Data/` (your sample scans), `index/` (what ingestion builds),
`tiles/` (the offline map), `testset/` (your test addresses) and `parcels.zip` (your county's parcels).

Next: [Get your data ready](3-your-data.md).
