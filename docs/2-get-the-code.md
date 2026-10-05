# 2. Get the code

<div class="agent" markdown="1">
Took option 1 on page 1? Your agent does this page. Skip to [page 3](3-your-data.md).
</div>

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

<div class="do" markdown="1">
1. Open https://github.com/RickSmith/SurveySleuth-Starter and click **Use this template**, then **Create a new repository**.
2. Give it a name. Choose **Private**: the license does not allow publishing your copy. Click **Create repository**.
3. On your new repository's page, click the green **Code** button and copy the address. Then:
</div>

```
git clone https://github.com/YOUR-NAME/YOUR-REPOSITORY.git C:\SurveySleuth
```

## Prove it runs

```
cd C:\SurveySleuth
python -m unittest
```

<div class="check" markdown="1">
A last line that says `OK`. These tests run on made-up data: no scans, no model, no internet. When they pass,
Python is set up right.
</div>

## What is in the folder

| Folder or file | What it is |
|---|---|
| `surveysleuth/` | The code. `ingest.py` reads the scans, `app.py` is the search app, `tiles.py` builds the offline map, `check.py` runs your test addresses. |
| `tests/` | The tests on made-up data. |
| `docs/` | This walkthrough and the wizard prompt. |
| `CONTEXT.md` | The words the code uses: Record, Job, Survey, Location, Fact. Worth five minutes: your agent uses these words when it talks to you. |
| `LICENSE` | The license. |

These appear later, and never go to GitHub: `Data/` (your sample scans), `index/` (what ingestion builds),
`tiles/` (the offline map), `testset/` (your test addresses), `parcels.zip` (your county's parcels) and `OFFICE.md`
(the agent's notes about your office).

<p class="next"><a href="3-your-data.md">Next: Get your data ready</a></p>
