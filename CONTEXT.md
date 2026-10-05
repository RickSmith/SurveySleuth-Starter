# SurveySleuth

A standalone tool that turns a land-surveying firm's legacy folders of scanned records into a searchable, mapped archive, so the firm can see what it has already done near a property before quoting a new job.

## Language

### Firm and archive

**Firm**:
A land-surveying company whose records SurveySleuth ingests (e.g. your own company).
_Avoid_: Customer, client, company

**Legacy archive**:
A Firm's existing folders of scanned or printed-to-PDF records, typically organized only by Job number. It can hold Records made by a company the Firm bought, which may carry that company's name.
_Avoid_: Backlog, old files, dataset

**Job**:
One piece of work the Firm did, identified by its Job number (e.g. `11-0527`); a Job may have many Records of different kinds.
_Avoid_: Project, order, file

**Record**:
A single document file in the Legacy archive, belonging to exactly one Job.
_Avoid_: File, scan, PDF (when meaning the document)

**Job List**:
A Firm's own typed list of its Jobs, each line giving a short place description (subdivision, lot, block, town), such as a "flat file index". It is not a Record: it covers many Jobs.
_Avoid_: Index (that is ingestion's output), flat file index, job log

### Record kinds

**Survey**:
A Record that is a drawn plat of a boundary, lot, or replat, with bearings, distances, and a title block (on older sheets, a typed title paragraph).
_Avoid_: Plat (as a synonym), drawing

**Elevation Certificate**:
A Record on the FEMA Elevation Certificate form, stating a structure's flood zone and elevations.
_Avoid_: EC, flood cert, flood certificate

**Natural Ground Letter**:
A Record, not on the FEMA form, stating the natural ground elevation and flood zone for a lot.
_Avoid_: NG letter, CD letter

**Metes-and-Bounds Description**:
A Record that describes a tract's boundary in words, as a run of bearings and distances, with no drawing (the Firm heads it Exhibit "A").
_Avoid_: Exhibit A, M&B, field notes

**Floor Plan**:
A Record that is a drawn plan of a building's interior spaces, with their areas.
_Avoid_: Interior survey, internal survey

**Field Notes**:
Handwritten notes and sketches from field crews (e.g. measurements on graph paper); rare in the Legacy archives received so far.

### Place and search

**Parcel ID**:
The county appraisal district's identifier for a piece of land, printed on Records as "File No." (e.g. `1234-0001-0005-000`).
_Avoid_: File No., account number

**Location**:
The point where a Record is placed on the map, together with how it was found (e.g. "certificate lat/long, checked by Parcel ID", "placed by its Job", "placed by hand"); for a Record "placed in its subdivision" it is the subdivision's area, not a point. A Job is near a place when any of its Records' Locations is (or, for an area, reaches it).
_Avoid_: Coordinates, geocode, position

**Benchmark**:
A survey mark with a known elevation that a Job's elevations are carried from (e.g. an NGS mark, a Subsidence District monument, or a temporary mark cut in a curb).
_Avoid_: BM, elevation mark

**Nearby search**:
A question of the form "which Jobs lie within a distance of this address or parcel?"
_Avoid_: Spatial query, lookup

**Search result**:
One Job matched by a Nearby search, listing all of its Records.
_Avoid_: Hit, match

**Search summary**:
A short written briefing above the Search results of a Nearby search, giving findings and recommendations; it is written only from Facts, and every claim in it cites the Record or Authoritative source it came from.
_Avoid_: Report, answer

**Authoritative source**:
Public data published by a government agency or a major platform provider (e.g. county parcels, FEMA flood maps, Google address lookup).
_Avoid_: Public data, third-party data

**Recorded Plat**:
A subdivision plat filed in the county's Map Records, found by its volume and page. It is an Authoritative source, not a Record, even when the Firm drew it: the county's recorded copy is the official one.
_Avoid_: Plat (alone), county plat, map record

**Fact**:
One piece of information from a single Record or Authoritative source, tagged with that source (e.g. the flood zone on one Elevation Certificate).
_Avoid_: Field, attribute, data point, metadata

**Drawing Fact**:
A Fact read from what page 1 of a Survey draws: one building, easement or setback line, copied as labelled (e.g. `20' B.L.`). Corner marks are not Drawing Facts: the vision model cannot count them.
_Avoid_: Plat fact, drawing (as a synonym for Survey)
