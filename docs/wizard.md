# Setup wizard

You are setting up SurveySleuth for a land-surveying office, with the person who works there. They are a surveyor,
not a programmer. Take the steps below in order, one at a time.

## How to work

- Plain words, short sentences. Explain a term the first time it comes up: a terminal, a folder path, a shapefile.
- Before running a command, say in one line what it does. At every question, wait for the person's answer.
- `OFFICE.md` at the repo root is the record: the answers, the paths, the commands that work on this computer, and a
  checklist of these steps. Write to it as you learn. Tick a step when its Done line holds. On a later run, read it
  first and continue from the first unticked step.
- `CONTEXT.md` holds the vocabulary. Read it before step 3 and use its words.
- The archive is read-only: the code never writes into it, and neither do you. `Data/`, `index/`, `testset/`, `tiles/`
  and `*.zip` are gitignored; keep them so. An API key lives in an environment variable, never in a file in git.
- A step that changed code ends with `python -m unittest` passing and a commit whose one-line message names the step.
- `docs/reference.md` is the command reference. `docs/3-your-data.md` lists every Galveston County
  value in the code, and the test set's shape. `docs/1-setup.md` has the install command for each program.

## Steps

### 1. The tools

First ask: will the scans be read on this computer, by the Ollama model (the tested way; it needs the graphics card
`docs/1-setup.md` describes), or by a cloud model (OpenAI, Google, xAI or Anthropic: the person has an account and an
API key there, and every scan page goes to that company)? Write the answer, the reader, into OFFICE.md.

Then run each check and show the person the result: `git --version`; `python --version` (3.11; on Windows, when
`python` is not 3.11, `py -3.11 --version`, then use `py -3.11` in every command and note that in OFFICE.md);
`python -m pip show pillow`; `pdftoppm -v`; and, for the Ollama reader, `ollama list` (shows `qwen3.6:35b`).

Install what is missing yourself, with that program's command from `docs/1-setup.md` (winget on Windows, Homebrew on a
Mac); the person clicks the permission pop-ups. A program not found right after its install: use its full path until
the app is restarted, and note the path in OFFICE.md.
Done when every check prints a version and, for the Ollama reader, the model is listed.

### 2. The code runs

`python -m unittest`. Done when it ends with OK.

### 3. The office

Ask one question at a time and write each answer into OFFICE.md:

- the county and the state;
- where the scans are (the folder path, often a network drive), the folder names inside it, and what each folder holds;
- what kinds of Record there are: Survey, Elevation Certificate, Natural Ground Letter, Metes-and-Bounds Description,
  Floor Plan, others;
- what a Job number looks like: two real file names, read from the folder, not typed from memory;
- what a Parcel ID looks like in this county, and what the Records call it ("File No." in Galveston);
- the appraisal district or county GIS site with the parcel download.

"I do not know" is an answer: write it down and find it out in step 5. Done when OFFICE.md has a line for each question.

### 4. A sample

With the person, make `Data/` in the repo folder, with the archive's folder names inside, and copy about 30 Records in:
some of each kind, old and new, and a few at addresses the person knows well. Done when `Data/` holds them and the
archive is unchanged (compare file counts before and after).

### 5. The county

Get the county's parcels as a shapefile zip (`docs/3-your-data.md`, "Your county's data") and save it as `parcels.zip`
in the repo folder. Read the zip's `.dbf` field names and `.prj` projection yourself (`zipfile`, `struct`), and show
the person one parcel so they confirm which fields are the Parcel ID, the address, the legal description and the acres.
Find the FEMA FIRM prefix and the county's lat/lon box (the parcels' extent, padded a little).
Then change every value in the "What was built for Galveston County" table of `docs/3-your-data.md` to this county
and this office: the tests' example points and the model prompts' state and county included.
Done when `python -c "from surveysleuth.gcad import read_parcels; p = read_parcels('parcels.zip'); print(len(p), p[0]['id'], p[0]['situs'], p[0]['centre'])"`
prints a count and a parcel whose centre lies inside the county box, and `python -m unittest` is OK.

### 6. The reader

For the Ollama reader, nothing to do: tick this step.

For a cloud reader: `ask(images, reading)` in `surveysleuth/vision.py` is the one function that talks to the model.
It sends `reading["prompt"]` and the page images, and returns a dict that fits `reading["schema"]`. Write the vendor's
version of `ask` beside it, with the same prompt, the same images, temperature 0 and the schema as the required
output; choose it by `MODEL`, and set `MODEL` to the vendor's model name, so every saved answer is keyed by it. Keep the
Ollama version. The key comes from an environment variable; tell the person how to set it on this computer and write
that in OFFICE.md. Ask the person to set a spending limit at the vendor before the first run.
Done when `python -m unittest` is OK and one Record from `Data/` is read: `ask` returns a dict with the schema's keys.

### 7. Ingest the sample

`python -m surveysleuth.ingest Data index --parcels parcels.zip`. The first run fetches the county's FEMA and NGS data,
then the model reads every Record: seconds to a minute each, depending on the computer. Then read `index/report.json`
with the person: every skipped file and its reason, every Record without a Location, every flagged Record. A skipped
folder means a folder-name constant is wrong. A Record without a Location usually means the Parcel ID form or the Job
number form is wrong, or the parcel data lacks that parcel. Fix, and run again: a re-run reuses every saved model
answer, so it is quick.
Done when every Record in the sample has a Location, or a reason the person accepts, and the skipped files are only
ones that should be skipped. Show the person the counts.

### 8. The app

`python -m surveysleuth.app --live-map`, then open http://127.0.0.1:8765/ in the browser. Ask the person for an
address in the sample. Done when they find a Job they know on the map, read its Search summary and open its Record.
Stop the app with Ctrl+C.

### 9. The test set

Ask the person for 5 to 12 addresses they know the answers for (`docs/3-your-data.md`, "The test set"): the Jobs
within half a mile of each, and one or two addresses with no Jobs. Find each address's lat/lon from the parcels
(situs) or the Census geocoder (`surveysleuth.sources.census_geocoder`), and write `testset/test-set.json` in the
shape shown there. Run `python -m surveysleuth.check`.
Done when every address passes, or the person agrees why one cannot yet (its Records are not in the sample: note it
for step 10).

### 10. The whole archive

`python -m surveysleuth.ingest <archive path> index --parcels parcels.zip`. Tell the person how long it runs: hours
to days (for a cloud reader, also what it will cost: the pages read so far times the price per page). Ctrl+C stops
it, and the same command carries on where it left off. Run it. When it ends:
`python -m surveysleuth.tiles --aerial` (hours; needs the internet once), then `python -m surveysleuth.check` on the
full index, then the app without `--live-map` and with `--archive <archive path>`.
Done when the check passes on the full index and the app runs from the offline tiles.

### 11. Hand over

Ask whether other computers in the office will use the app. If so, start it with `--host 0.0.0.0`, have the person
allow Python through the firewall on private networks when Windows asks, and open the address it prints from a second
computer. Offer to make it start when the computer starts, and to make a desktop shortcut.
Write into OFFICE.md the exact command that starts the app on this computer (with its `--host`, `--index`,
`--archive` and `--tiles` paths), the office address, and the exact command that ingests again when new scans arrive.
Have the person start the app from OFFICE.md and search an address, with no help from you. Done when they do.
