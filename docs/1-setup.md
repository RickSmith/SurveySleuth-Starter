# 1. Set up your computer

Six programs go on your computer. There are two ways to get them there: let the agent do it, or do it yourself.

## The short way: the agent installs them

Only two things need you: installing the agent, and clicking the pop-ups.

1. Install the Claude desktop app from https://claude.ai/download and sign in. It needs a Claude Pro or Max
   subscription (https://claude.com/pricing). The free plan does not include the Code tab.
2. Make an empty folder named `C:\SurveySleuth` (in File Explorer: right-click, New, Folder). On a Mac, `SurveySleuth`
   in your home folder.
3. In the app, click **Code**, then **Select folder**, and pick that folder.
4. Paste this line and press Enter:

```
Read https://raw.githubusercontent.com/RickSmith/SurveySleuth-Starter/main/docs/1-setup.md and install everything on it that this computer is missing. Then copy the code into this folder with: git clone https://github.com/RickSmith/SurveySleuth-Starter.git . Then read docs/wizard.md and follow it.
```

The agent asks before each command: say yes. When Windows shows a pop-up asking for permission, click Yes. The model
download is 23 GB; let it run. If the app stops, or you close it, open the folder again and paste the same line. It
skips what is already done.

Before you paste, read [Which graphics card](#which-graphics-card) and [Or a cloud model instead](#or-a-cloud-model-instead)
below: the agent asks you which way you want at its first step.

That is pages 1, 2 and 4 of this walkthrough in one go. Page 3, your data, still needs you.

## The long way: you install them

Each program has a check, so you know it worked. Do them in order. The Windows steps come first; the Mac steps are
near the end of the page.

### Before you start

- **The terminal.** Press the Windows key, type `Terminal`, and open Windows Terminal. It shows a line that ends in `>`
  and waits for you to type. That is where you paste the commands on this page. To paste, right-click in the window.
  Press Enter to run the line.
- **After each install, open a new terminal.** Close the terminal window and open it again. A new terminal knows about
  the new program. The old one does not, and its check will fail.
- **Pop-ups.** Some installs open a window that asks for permission. Click Yes.
- **Time.** The programs are quick. The vision model is a 23 GB download, so start it and do something else.

### Git

Git copies the code to your computer and keeps track of every change. Your agent uses it.

```
winget install --id Git.Git -e --source winget
```

New terminal. Check:

```
git --version
```

You should see `git version 2.` followed by more numbers.

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

You should see `Python 3.11.` followed by a number. Now also try:

```
python --version
```

If this also says 3.11, use `python`, as this guide does. If it says another version, or opens the Microsoft Store,
type `py -3.11` wherever this guide says `python`. Tell your agent which one works on your computer; it will use that one.

Then install Pillow, the one add-on the scan reader needs:

```
python -m pip install pillow
```

The last line says `Successfully installed` or `Requirement already satisfied`. Either is good.

### Poppler

Poppler turns a page of a PDF into a picture, so the vision model can look at it.

```
winget install --id oschwartz10612.Poppler -e --source winget
```

New terminal. Check:

```
pdftoppm -v
```

You should see `pdftoppm version` followed by a number.

### Ollama and the vision model

Ollama runs AI models on your own computer. The model reads your scans. Nothing leaves your computer. This is the way
the code was built and tested. Skip this section if you choose a cloud model instead (below).

```
winget install --id Ollama.Ollama -e --source winget
```

Ollama starts and sits in the corner of the taskbar, as a llama icon. It must be running whenever the scans are read.
New terminal. Now download the model. It is 23 GB:

```
ollama pull qwen3.6:35b
```

Wait for it to finish. Check:

```
ollama list
```

You should see `qwen3.6:35b` in the list.

### Which graphics card

The model is 23 GB. It runs fastest when the whole model sits in the graphics card's memory.

- **Built and tested on an NVIDIA GeForce RTX 5090**, which has 32 GB of card memory. That is the recommendation.
- A card with 24 GB (RTX 3090, RTX 4090) holds most of it. The rest goes to normal memory, and it runs slower.
- A smaller card, or none: it runs on the processor, and a scan takes minutes instead of seconds. Then consider a cloud
  model instead, below.
- A Mac with Apple silicon: 32 GB of memory or more. The card and the processor share it.

If the model does not fit, Ollama says so when the first scan is read, and your agent will tell you.

### Or a cloud model instead

If you do not have the card, or do not want to run a model yourself, a cloud model can read the scans instead:
OpenAI (the models behind ChatGPT), Google (Gemini), xAI (Grok) or Anthropic (Claude). Know what that means:

- Every page of every scan is sent to that company. The Ollama way keeps everything in the office.
- You need an account with that company and an API key, a password that programs use, and you pay per page read.
  Set a spending limit in that account first.
- The code is built and tested with the Ollama model. Your agent adds the cloud call in the wizard. The test set
  (page 3) then shows how well that model reads your scans.

To choose this: skip Ollama, and tell the wizard at its first step.

### Claude Code

Claude Code is the AI agent that sets up SurveySleuth with you. It runs in the terminal, inside your project folder. It
can read files, change code and run commands, and it asks you before it does.

It needs a Claude Pro or Max subscription. The free plan does not include it. See https://claude.com/pricing.

Install, in the terminal:

```
irm https://claude.ai/install.ps1 | iex
```

New terminal. Check:

```
claude --version
```

Sign in: type `claude` and press Enter. A browser window opens; log in there and come back to the terminal. Type
`/exit` to leave Claude Code for now.

Prefer a window to a terminal? The Claude desktop app has a **Code** tab that does the same job: https://claude.ai/download.
Install it, sign in, and click Code. Page 4 shows both ways.

Other agents work with the wizard prompt too, as long as they can run commands in a folder: OpenAI Codex, Google's
Gemini CLI, Cursor. This walkthrough shows Claude.

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

Open a new terminal and run each line. Every one should print a version, and `ollama list` should show the model
(skip that one if you chose a cloud model):

```
git --version
python --version
python -m pip show pillow
pdftoppm -v
ollama list
claude --version
```

Next: [Get the code](2-get-the-code.md).
