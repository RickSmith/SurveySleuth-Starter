# SurveySleuth

A land-surveying office's scanned Records, read by a local vision model, placed on a map and searched by address.
Python 3.11 standard library; Pillow for ingestion only.

Read `CONTEXT.md` first: it defines the vocabulary (Record, Job, Survey, Location, Fact). Use its terms.

Setting up for an office, or continuing a setup: `/setup`, or read `docs/wizard.md` and follow it.
`OFFICE.md`, when it exists, holds this office's answers and the commands that work on this computer.

## Data

- The archive folder (the office's scans) is read-only. Never write into it.
- `Data/`, `index/`, `testset/`, `tiles/`, `overrides.json` and `*.zip` hold the office's data and are gitignored. Never commit them.
- Tests run on fake data only. No real address, Parcel ID, Job number or person's name goes into a test, a comment or a commit message.

## Run it

`README.md` (the Reference section) lists every command. `python -m unittest` passes before every commit.
