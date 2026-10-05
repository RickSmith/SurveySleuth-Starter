# 4. Hand it to your agent

Took the short way on page 1? Your agent is already following the wizard. Read "What happens next" and "How to answer" below.

## Start the agent in the project folder

In the terminal:

```
cd C:\SurveySleuth
claude
```

Or in the Claude desktop app: click **Code**, then **Select folder**, and choose `C:\SurveySleuth`.

## Start the wizard

Type:

```
/setup
```

With another agent, paste this instead: `Read docs/wizard.md and follow it.`

## What happens next

- It checks the programs from page 1, proves the code runs, asks about your office and your county, reads your sample,
  and at the end reads the whole archive.
- One step at a time. It says what a command does before it runs it. It asks before it changes anything.
- It writes what it learns into `OFFICE.md`. If you stop, close the window and come back tomorrow, start the agent
  again and type `/setup`. It reads `OFFICE.md` and carries on.
- Long steps: reading the whole archive runs for hours to days. Keep the computer on and awake. In the power settings,
  set sleep to Never while plugged in.
- Permissions: Claude Code asks before it runs a command or changes a file. Everything it needs happens inside
  `C:\SurveySleuth`. It never needs to write into your archive.

## How to answer

- Plain words. "The surveys are in S:\Scans\Surveys, one PDF per job, named by the job number."
- "I do not know" is a fine answer. It finds out, or asks another way.
- When it shows you a result, a count, a map or a list, look at it. You know your archive; it does not. Tell it when
  something is wrong.

Next: [Every day](5-every-day.md).
