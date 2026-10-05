# SurveySleuth Starter

<p class="lead">Type an address. See every job your office ever did near it, on a map, with a short briefing. Built from the scans you already have.</p>

<svg class="flow" viewBox="0 0 880 150" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Your scans go to a reader, then onto a map, then you search by address">
  <defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10z" fill="#9aa4b2"/></marker></defs>
  <g font-family="-apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif" text-anchor="middle">
    <rect x="10" y="30" width="190" height="90" rx="14" fill="#ffffff" stroke="#e3e6ea" stroke-width="2"/>
    <text x="105" y="68" font-size="17" font-weight="700" fill="#1f2937">Your scans</text>
    <text x="105" y="92" font-size="13" fill="#5b6472">surveys, certificates, letters</text>
    <path d="M202 75 L238 75" stroke="#9aa4b2" stroke-width="3" marker-end="url(#a)"/>
    <rect x="240" y="30" width="190" height="90" rx="14" fill="#ffffff" stroke="#e3e6ea" stroke-width="2"/>
    <text x="335" y="68" font-size="17" font-weight="700" fill="#1f2937">An AI reader</text>
    <text x="335" y="92" font-size="13" fill="#5b6472">reads every page</text>
    <path d="M432 75 L468 75" stroke="#9aa4b2" stroke-width="3" marker-end="url(#a)"/>
    <rect x="470" y="30" width="190" height="90" rx="14" fill="#ffffff" stroke="#e3e6ea" stroke-width="2"/>
    <text x="565" y="68" font-size="17" font-weight="700" fill="#1f2937">A map</text>
    <text x="565" y="92" font-size="13" fill="#5b6472">every job pinned to its lot</text>
    <path d="M662 75 L698 75" stroke="#9aa4b2" stroke-width="3" marker-end="url(#a)"/>
    <rect x="700" y="30" width="170" height="90" rx="14" fill="#0e7490" stroke="#0e7490" stroke-width="2"/>
    <text x="785" y="68" font-size="17" font-weight="700" fill="#ffffff">You search</text>
    <text x="785" y="92" font-size="13" fill="#cffafe">by address, in seconds</text>
  </g>
</svg>

Your office has years of surveys, elevation certificates and letters, scanned and filed by job number. Nobody can
search them by place. SurveySleuth reads every scan with an AI model, pins each one to its lot on the map, and answers
the question you ask before every quote: what have we done here before?

It was built for one firm in Galveston County, Texas. This starter lets you set it up for your own office, in your own
county. An AI agent does the technical work. You answer its questions.

## Two ways to set it up

<div class="cards" markdown="1">
<div class="card pick" markdown="1">
### Option 1: let the agent do it

Install the Claude desktop app, make a folder, and paste one line. The agent installs the programs, copies the code,
and walks you through the rest, asking as it goes. Most of the afternoon is waiting for downloads.

[Start option 1](1-setup.md#option-1-let-the-agent-do-it){: .btn}
</div>
<div class="card" markdown="1">
### Option 2: step by step

Install each program yourself with the commands we give you. Then hand the project to the agent for the rest.
Pick this if you like to see each thing go in.

[Start option 2](1-setup.md#option-2-step-by-step){: .btn .quiet}
</div>
</div>

Either way, the steps are the same five. Option 1 does steps 1, 2 and 4 for you.

<ol class="steps">
<li><b>Set up your computer.</b> Git, Python, Poppler, the AI reader, and the agent.</li>
<li><b>Get the code.</b> Copy this starter to your computer and prove it runs.</li>
<li><b>Get your data ready.</b> A sample of your scans, and your county's parcel data. <em>This one is yours.</em></li>
<li><b>Hand it to your agent.</b> It adapts the code to your county, reads your sample, then your whole archive.</li>
<li><b>Every day.</b> Start it, search, add new scans, run it for the whole office.</li>
</ol>

## What you get

<div class="cards" markdown="1">
<div class="card" markdown="1">
### The search app

Type an address or a Parcel ID. Pick a distance. See every job nearby, its records, the flood zone, the benchmarks,
and a written briefing in which every claim names the record it came from. Click a record to see the scan.
</div>
<div class="card" markdown="1">
### The reader

An AI vision model reads each scanned page: the address, the Parcel ID, the flood zone, the elevations, the buildings
and easements drawn on a survey. On your own computer, so nothing leaves the office. Or in the cloud, if you prefer.
</div>
<div class="card" markdown="1">
### The walkthrough and the wizard

These pages, written for a surveyor, not a programmer. And a wizard prompt that tells the agent exactly what to do with
you, one step at a time, so you never have to.
</div>
</div>

## What you need

- **A computer** running Windows 11 or macOS, on all day if the office will use it.
- **Your scans** as PDF files in folders, on the computer or a network drive. [Page 3](3-your-data.md) says what the code expects.
- **Your county's parcel data**, a free download from your appraisal district or county GIS site. Same page.
- **The reader.** On your computer, it needs a big graphics card: 32 GB for the model the code was built with (an
  NVIDIA GeForce RTX 5090), or 24 GB for a smaller one. [Page 1](1-setup.md#which-graphics-card) has the ladder, and
  the cloud option.
- **An AI agent.** The walkthrough uses Claude Code, which comes with a Claude Pro or Max subscription. Other agents
  that can run commands in a folder, such as OpenAI Codex, Gemini CLI or Cursor, can follow the same wizard prompt.
- **Internet** for the setup and the county data. After that the app works offline.
- **Time.** An afternoon for the setup. Then the first full reading of your archive runs on its own for hours to days,
  depending on how many scans you have. You can stop it and start it again.

<p class="quiet">The public data sources (FEMA flood zones, NGS benchmarks, the Census geocoder, county parcels) are United States sources.</p>

## License

You may use this software inside your own company, and change it for your own company's use. You may not sell it,
offer it to other companies, or publish your copy. The full terms are the PolyForm Internal Use License 1.0.0, in the
`LICENSE` file. The map code in `surveysleuth/static/vendor/` has its own open-source licenses, listed beside it.

Copyright (c) 2026 Rick Smith.
