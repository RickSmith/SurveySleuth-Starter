# 1. Set up your computer

Six programs go on your computer. Pick one of the two options.

## Option 1: let the agent do it

Only two things need you: installing the agent, and clicking the pop-ups.

<div class="do" markdown="1">
1. Install the **Claude desktop app** from https://claude.ai/download and sign in. It needs a Claude Pro or Max
   subscription (https://claude.com/pricing). The free plan does not include the Code tab.
2. Make an empty folder named `C:\SurveySleuth`. In File Explorer: right-click, New, Folder. On a Mac, a folder named
   `SurveySleuth` in your home folder.
3. In the app, click **Code**, then **Select folder**, and pick that folder.
4. Paste this line into the box and press Enter:
</div>

<div class="paste" markdown="1">
```
Read https://raw.githubusercontent.com/RickSmith/SurveySleuth-Starter/main/docs/1-setup.md and install everything on it that this computer is missing. Then copy the code into this folder with: git clone https://github.com/RickSmith/SurveySleuth-Starter.git . Then read docs/wizard.md and follow it.
```
</div>

<div class="agent" markdown="1">
It asks you which reader you want (see [Which graphics card](#which-graphics-card) and [Or a cloud model instead](#or-a-cloud-model-instead)
below). Then it installs Git, Python, Poppler and, for the in-house reader, Ollama and the model. Then it copies the code
and starts the wizard. It asks before each command: say yes.
</div>

<div class="tip" markdown="1">
When Windows shows a pop-up asking for permission, click Yes. The model download is 23 GB; let it run. If the app
stops, or you close it, open the folder again and paste the same line. It skips what is already done.
</div>

That is pages 1, 2 and 4 of this walkthrough in one go. [Page 3, your data](3-your-data.md), still needs you.

## Option 2: step by step

Each program has a check, so you know it worked. Do them in order. Windows first; the Mac steps are near the end.

### Before you start

<div class="tip" markdown="1">
**The terminal** is where you paste commands. Press the Windows key, type `Terminal`, and open Windows Terminal. It
shows a line that ends in `>` and waits for you. To paste, right-click in the window. Press Enter to run the line.
Every code box on this page has a Copy button.

**After each install, open a new terminal.** A new terminal knows about the new program. The old one does not, and its
check will fail.

**Pop-ups** that ask for permission: click Yes.
</div>

### Git

Git copies the code to your computer and keeps track of every change. Your agent uses it.

```
winget install --id Git.Git -e --source winget
```

New terminal. Check:

```
git --version
```

<div class="check" markdown="1">
`git version 2.` followed by more numbers.
</div>

### Python 3.11

Python is the language SurveySleuth is written in. It needs version 3.11. Newer versions are untested; older ones will
not run it.

```
winget install --id Python.Python.3.11 -e --source winget
```

New terminal. Check:

```
py -3.11 --version
```

<div class="check" markdown="1">
`Python 3.11.` followed by a number.
</div>

Now also try `python --version`. If it also says 3.11, use `python`, as this guide does. If it says another version,
or opens the Microsoft Store, type `py -3.11` wherever this guide says `python`. Tell your agent which one works; it
will use that one.

Then install Pillow, the one add-on the scan reader needs:

```
python -m pip install pillow
```

<div class="check" markdown="1">
A last line that says `Successfully installed` or `Requirement already satisfied`. Either is good.
</div>

### Poppler

Poppler turns a page of a PDF into a picture, so the reader can look at it.

```
winget install --id oschwartz10612.Poppler -e --source winget
```

New terminal. Check:

```
pdftoppm -v
```

<div class="check" markdown="1">
`pdftoppm version` followed by a number.
</div>

### Ollama and the vision model

Ollama runs AI models on your own computer. The model reads your scans. Nothing leaves your computer. This is the way
the code was built and tested. Skip this section if you choose a cloud model instead (below).

```
winget install --id Ollama.Ollama -e --source winget
```

Ollama starts and sits in the corner of the taskbar, as a llama icon. It must be running whenever the scans are read.
New terminal. Now download the model. It is 23 GB (a 24 GB card: `ollama pull qwen3.6:27b` instead, 17 GB; see
[Which graphics card](#which-graphics-card)):

```
ollama pull qwen3.6:35b
```

Wait for it to finish. Check:

```
ollama list
```

<div class="check" markdown="1">
`qwen3.6:35b` in the list.
</div>

### Which graphics card

The model is 23 GB. It runs fastest when the whole model sits in the graphics card's memory.

<div class="cards" markdown="1">
<div class="card pick" markdown="1">
**32 GB of card memory or more** (NVIDIA GeForce RTX 5090): `qwen3.6:35b`, the model the code was built and tested
with. This is the recommendation.
</div>
<div class="card" markdown="1">
**24 GB** (RTX 3090, RTX 4090): `qwen3.6:27b`, 17 GB. It fits whole on the card. It reads a little less well; see below.
</div>
<div class="card" markdown="1">
**Less than 24 GB, or no card.** The models run on the processor, and a scan takes minutes instead of seconds.
Consider the cloud model instead.
</div>
<div class="card" markdown="1">
**A Mac with Apple silicon.** 32 GB of memory or more for 35b, 24 GB for 27b. The card and the processor share it.
</div>
</div>

To use the smaller model, pull it instead (`ollama pull qwen3.6:27b`) and tell the wizard. Reading then runs with
`--model qwen3.6:27b`. You can change models later: each model's answers are kept apart, and the test set shows the
difference. If a model does not fit, Ollama says so when the first scan is read, and your agent will tell you.

<div class="warn" markdown="1">
**How much do you lose with 27b?** We re-read 65 real Records with both models. On the fields that place a Record on
the map they agree almost always: Parcel ID 100%, Job number 97%, street 97%, date 100%, flood zone, BFE and FIRM
panel 100%. They differ more on details: the lots and block a survey names (often only in wording, "Lot 7" against
"7"), the lot count on a recorded plat (half differ), the buildings drawn on a survey, and a certificate's FIRM panel
date. Over every field, 86% agree. 35b stays the recommendation; 27b is a fair second.
</div>

### Or a cloud model instead

If you do not have the card, or do not want to run a model yourself, a cloud model can read the scans instead:
OpenAI (the models behind ChatGPT), Google (Gemini), xAI (Grok) or Anthropic (Claude).

<div class="warn" markdown="1">
- Every page of every scan is sent to that company. The Ollama way keeps everything in the office.
- You need an account with that company and an API key, a password that programs use, and you pay per page read.
  Set a spending limit in that account first.
- The code is built and tested with the Ollama model. Your agent adds the cloud call in the wizard. The test set
  (page 3) then shows how well that model reads your scans.
</div>

To choose this: skip Ollama, and tell the wizard at its first step.

### Claude Code

Claude Code is the AI agent that sets up SurveySleuth with you. It runs in the terminal, inside your project folder. It
can read files, change code and run commands, and it asks you before it does.

It needs a Claude Pro or Max subscription. The free plan does not include it. See https://claude.com/pricing.

```
irm https://claude.ai/install.ps1 | iex
```

New terminal. Check:

```
claude --version
```

<div class="check" markdown="1">
A version number. Then type `claude` and press Enter: a browser window opens, you log in there, and come back.
Type `/exit` to leave Claude Code for now.
</div>

<div class="tip" markdown="1">
Prefer a window to a terminal? The Claude desktop app has a **Code** tab that does the same job: https://claude.ai/download.
Install it, sign in, and click Code. Other agents work with the wizard prompt too, as long as they can run commands
in a folder: OpenAI Codex, Google's Gemini CLI, Cursor. This walkthrough shows Claude.
</div>

### Optional: a GitHub account and the GitHub CLI

Only needed if you want your own copy of the code kept on GitHub (page 2, option B).
Account: https://github.com/signup. Then:

```
winget install --id GitHub.cli -e --source winget
```

New terminal, then `gh auth login` and follow the questions.

### macOS

Open Terminal (Spotlight: type `Terminal`). Git comes with Apple's command line tools:

```
xcode-select --install
```

Homebrew installs the rest:

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python@3.11 poppler
python3.11 -m pip install pillow
```

Ollama: download it from https://ollama.com/download, open it, then in Terminal: `ollama pull qwen3.6:35b`.

Claude Code:

```
curl -fsSL https://claude.ai/install.sh | bash
```

Use `python3.11` wherever this guide says `python`.

### The final check

Open a new terminal and run each line.

```
git --version
python --version
python -m pip show pillow
pdftoppm -v
ollama list
claude --version
```

<div class="check" markdown="1">
A version from every line, and `qwen3.6:35b` in the Ollama list (skip that one if you chose a cloud model).
</div>

<p class="next"><a href="2-get-the-code.md">Next: Get the code</a></p>
