# SurveySleuth Starter

**Type an address. See every job your office ever did near it, on a map, with a short briefing.**

Your office has years of surveys, elevation certificates and letters, scanned and filed by job number. Nobody can
search them by place. SurveySleuth reads every scan with an AI model, pins each one to its lot on the map, and answers
the question you ask before every quote: what have we done here before?

## What you get

- **The search app.** Type an address or a Parcel ID, pick a distance, and see every job nearby, its records, the
  flood zone, the benchmarks, and a written briefing in which every claim names the record it came from. Click a
  record to see the scan. Run it on one computer, and the whole office opens it in a browser.
- **The reader.** An AI vision model reads each scanned page: the address, the Parcel ID, the flood zone, the
  elevations, the buildings and easements drawn on a survey. It runs on your own computer, so nothing leaves the
  office. Or in the cloud, if you prefer.
- **A walkthrough and a wizard.** The walkthrough is written for a surveyor, not a programmer. The wizard is a prompt
  for an AI agent: it installs what is needed, adapts the code to your county and your folders, reads your scans, and
  checks the result with you, one step at a time.

## Start here

**The walkthrough: https://ricksmith.github.io/SurveySleuth-Starter/**

Two ways to set it up:

1. **Let the agent do it.** Install the Claude desktop app, make a folder, paste one line. The agent does the rest
   and asks you as it goes.
2. **Step by step.** Install each program yourself with the commands on the site, then hand the project to the agent.

## What you need

A Windows or Mac computer. Your scans as PDF files. Your county's free parcel download. A Claude Pro or Max
subscription for the agent (or another coding agent). For the in-house reader, a big graphics card: it was built on an
NVIDIA GeForce RTX 5090. The walkthrough has the details.

## Built for Galveston County, made for yours

The code was built for one surveying firm in Galveston County, Texas. The walkthrough lists everything that is local
to that county, and the wizard changes it for your county with you.

## License

You may use this software inside your own company and change it for your company's use. You may not distribute it,
sell it, offer it to other companies, or publish your copy. The terms are the PolyForm Internal Use License 1.0.0, in
`LICENSE`. Copyright (c) 2026 Rick Smith.

Technical details, every command, and the third-party licenses and data sources: [docs/reference.md](docs/reference.md).
