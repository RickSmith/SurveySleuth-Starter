# 5. Every day

Your agent wrote the exact commands for your computer into `OFFICE.md`. This page explains them, and what else you can
do once it is running. [Every command](#every-command) is listed at the end.

## Start the app

In a terminal, in the project folder:

```
cd C:\SurveySleuth
python -m surveysleuth.app --archive "S:\Scans"
```

<div class="check" markdown="1">
`Open http://127.0.0.1:8765/`. Open that address in a browser. The app runs until you press Ctrl+C in the terminal.
</div>

It needs no internet: the map comes from `tiles/` and the data from `index/`. Before the offline map is built, add
`--live-map`, and the map comes from the internet.

<div class="tip" markdown="1">
Ask your agent: "Make a desktop shortcut that starts the app." Then it is a double-click.
</div>

## Search

Type an address or a Parcel ID. Pick a distance: a quarter, a half, one or two miles. You get:

- **The Search summary.** A short briefing. Every claim in it names the Record or the public source it came from.
- **The Jobs nearby**, each with its Records: the survey, the certificate, the letter.
- **The map**, with the parcel, the flood zone, the benchmarks, and the Jobs as pins.

Click a Record to open it. **Open PDF** shows the original scan. **Plat** opens the county's recorded plat when it is held.

## Run it for the whole office

One computer runs the app. Everyone else opens it in their browser.

<div class="do" markdown="1">
1. **Pick the computer.** One that is on all day, holds the `index/` and `tiles/` folders, and can see the archive.
   The reader's graphics card is only needed when scans are read, so this can be a plain office PC once the archive
   is ingested.
2. **Start the app for the network**, with `--host 0.0.0.0`:

   ```
   python -m surveysleuth.app --host 0.0.0.0 --archive "\\server\Scans"
   ```

3. **Allow it through the firewall.** The first time, Windows asks whether Python may accept connections. Allow it
   on private networks.
4. **Share the address.** The app prints it, like `http://SURVEY-PC:8765/`. Everyone in the office opens that in a
   browser and bookmarks it.
</div>

<div class="tip" markdown="1">
Ask your agent: "Make the app start by itself when this computer starts." It sets that up for you.
</div>

<div class="warn" markdown="1">
Anyone on your office network can open it, including every scan. There is no login. Keep it on the office network,
not on public Wi-Fi, and not on the internet.
</div>

## Your scans on a network drive

Yes. Point the reader and the app at the network folder. Use the full network path, like `\\server\Scans`, rather
than a drive letter like `S:`. A drive letter is only known to the person who mapped it, and not to a program that
starts by itself.

```
python -m surveysleuth.ingest "\\server\Scans" index --parcels parcels.zip
```

Reading goes over the network, so the first full run is slower than from a local disk. The index stays on the computer
that runs the app. The archive is never written to.

## New scans

Add them to the archive, in the same folders, then run ingestion again (the command is in `OFFICE.md`). Only new or
changed Records are read by the model; everything else is reused. Start the app again afterwards.

## Change SurveySleuth

Open the agent in the project folder and ask in plain words. Say what you want to see, not how to build it.

<div class="do" markdown="1">
- "Show the year of each Job in the search results."
- "Add a button that prints the Search summary."
- "Read the room areas off a Floor Plan too."
- "The flood zone is wrong for this address. Here is what the certificate says."
</div>

<div class="agent" markdown="1">
It changes the code, runs the tests and the check, and asks you to look. Every change is saved as a commit, a save
point. Say "undo the last change" and it goes back.
</div>

<div class="tip" markdown="1">
`CONTEXT.md` lists the words the code uses: Record, Job, Survey, Location, Search summary. Use them and the agent knows
exactly what you mean.
</div>

## A Record placed wrong, or not at all

`index/report.json` lists every Record without a Location and every flagged one. To place a Record by hand, add it to
`overrides.json` in the project folder, with its position and why, and run ingestion again with `--overrides overrides.json`:

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

<div class="check" markdown="1">
`pass` for every test address, and a last line like `12 of 12 addresses pass.` Run it after a change, or after a big
batch of new scans.
</div>

## Every command

Run them in the project folder (`cd C:\SurveySleuth`). Replace `\\server\Scans` with your archive's path.

| What | Command |
|---|---|
| Start the app on this computer | `python -m surveysleuth.app --archive "\\server\Scans"` |
| Start the app for the whole office | `python -m surveysleuth.app --host 0.0.0.0 --archive "\\server\Scans"` |
| Start the app before the map is built | add `--live-map` to either line |
| Read the sample | `python -m surveysleuth.ingest Data index --parcels parcels.zip` |
| Read the whole archive, or new scans | `python -m surveysleuth.ingest "\\server\Scans" index --parcels parcels.zip` |
| Read with Records placed by hand | add `--overrides overrides.json` to the line above |
| Build the offline map | `python -m surveysleuth.tiles --aerial` |
| Run the check | `python -m surveysleuth.check` |
| Run the tests | `python -m unittest` |
| Stop the app or a reading | Ctrl+C in its terminal. A reading carries on where it left off next time. |

## Keep it to yourselves

The license lets your company use this and change it. It does not let you give it to other companies, sell it, or
publish your copy.
