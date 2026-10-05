# SurveySleuth Starter

A land-surveying office keeps years of scanned surveys, elevation certificates and letters in folders by job number.
Nobody can search them by place. SurveySleuth reads every scan with an AI vision model that runs on your own computer,
places each one on a map, and lets you type an address to see every job you did near it, with a short written briefing.

It was built for one firm in Galveston County, Texas. This starter lets you set it up for your own office, in your own
county, with an AI coding agent doing the technical work while you answer its questions.

## What you get

- The working code: ingestion (reading the scans), the search app with the map, and the tests.
- This walkthrough, written for a surveyor, not a programmer.
- A wizard prompt. You hand it to an AI agent, and the agent walks you through the rest, one step at a time.

## What you need

- **A computer** running Windows 11 or macOS. Disk space: a copy of your scans, the page images the app shows (a few
  GB), the offline map (300 MB) and, for the in-house reader, the model (23 GB).
- **Your scans** as PDF files in folders. [Get your data ready](3-your-data.md) says what the code expects.
- **Your county's parcel data**, downloaded from your appraisal district or county GIS site. Same page.
- **Internet** for the setup, the downloads and the county data. After that the app works offline.
- **An AI coding agent** to do the setup. The walkthrough uses Claude Code, which needs a Claude Pro or Max
  subscription. Other agents that can run commands in a folder, such as OpenAI Codex, Gemini CLI or Cursor, can follow
  the same wizard prompt.
- **A reader for the scans.** The tested way is a vision model on your own computer, through Ollama: nothing leaves
  the office, and it needs a big graphics card. The code was built on an NVIDIA GeForce RTX 5090 with 32 GB of card
  memory; [page 1](1-setup.md#which-graphics-card) says what else works. The other way is a cloud model from OpenAI,
  Google, xAI or Anthropic: no card needed, but every scan goes to that company, and you pay per page.
- **Time.** Setting up the computer takes an afternoon, or an hour when the agent does it. The first full reading of
  your archive runs for hours to days, depending on how many scans you have. You can stop it and start it again; it
  carries on where it left off.

The public data sources (FEMA flood zones, NGS benchmarks, the Census geocoder, county parcels) are United States sources.

## The walkthrough

1. [Set up your computer](1-setup.md): Git, Python, Poppler, Ollama and the vision model, Claude Code.
2. [Get the code](2-get-the-code.md): copy this starter to your computer and prove it runs.
3. [Get your data ready](3-your-data.md): your scans, your county's data, and what was built for Galveston County.
4. [Hand it to your agent](4-hand-it-to-your-agent.md): start the wizard. The agent takes it from here.
5. [Every day](5-every-day.md): starting the app, searching, adding new scans.

In a hurry? Page 1 starts with a short way: install the Claude desktop app, and the agent does pages 1, 2 and 4 for you.

The wizard prompt itself is [here](wizard.md). You do not need to read it, but you can.

## License

You may use this software inside your own company, and change it for your own company's use. You may not sell it,
offer it to other companies, or publish your copy. The full terms are the PolyForm Internal Use License 1.0.0, in the
`LICENSE` file. The map code in `surveysleuth/static/vendor/` has its own open-source licenses, listed beside it.

Copyright (c) 2026 Rick Smith.
