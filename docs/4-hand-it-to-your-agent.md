# 4. Hand it to your agent

<div class="agent" markdown="1">
Took option 1 on page 1? Your agent is already following the wizard. Read "What happens next" and "How to answer" below.
</div>

## Start the agent in the project folder

<div class="do" markdown="1">
In the terminal:

```
cd C:\SurveySleuth
claude
```

Or in the Claude desktop app: click **Code**, then **Select folder**, and choose `C:\SurveySleuth`.
</div>

## Start the wizard

<div class="do" markdown="1">
Type this and press Enter:

```
/setup
```

With another agent, paste this instead: `Read docs/wizard.md and follow it.`
</div>

## What happens next

<div class="agent" markdown="1">
- It checks the programs from page 1 and proves the code runs.
- It asks about your office and your county, one question at a time, and writes the answers into `OFFICE.md`.
- It changes the code for your county and your folder names, then reads your sample.
- It starts the app so you can try a search. Then it builds your test set, and runs the check.
- At the end it reads the whole archive, builds the offline map, and writes the start-up commands into `OFFICE.md`.
</div>

<div class="tip" markdown="1">
- One step at a time. It says what a command does before it runs it. It asks before it changes anything.
- If you stop, close the window and come back tomorrow, start the agent again and type `/setup`. It reads `OFFICE.md`
  and carries on.
- Reading the whole archive runs for hours to days. Keep the computer on and awake. In the power settings, set sleep
  to Never while plugged in.
- Everything it needs happens inside `C:\SurveySleuth`. It never needs to write into your archive.
</div>

## How to answer

- **Plain words.** "The surveys are in S:\Scans\Surveys, one PDF per job, named by the job number."
- **"I do not know" is a fine answer.** It finds out, or asks another way.
- **Look at what it shows you.** A count, a map, a list. You know your archive; it does not. Tell it when something is wrong.

<p class="next" markdown="1">[Next: Every day](5-every-day.md)</p>
