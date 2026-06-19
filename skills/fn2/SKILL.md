---
name: fn2
description: Research stocks, markets, and the economy with FN2's grounded AI, and create, schedule, and manage FN2 research agents.
version: 1.0.0
author: FN2
platforms: [macos, linux]
metadata:
  hermes:
    tags: [finance, stocks, markets, research, agents, fn2]
    category: research
required_environment_variables:
  - name: FN2_API_KEY
    prompt: FN2 API key (fn2_...)
    help: Create one at https://fn2.ai under Settings -> API Keys
    required_for: all FN2 features
---

# FN2 — market research & research agents

[FN2](https://fn2.ai) is an AI research platform for stocks, markets, and the
economy. It answers questions with **grounded, sourced** analysis (live prices,
earnings transcripts, SEC filings, economic data, prediction markets) and lets
you run **agents** that research on a schedule and report back.

This skill talks to FN2 through a small bundled CLI: **`scripts/fn2`** (Python 3
standard library only — nothing to install).

## When to use this skill

Use FN2 whenever the user asks about:

- A stock or ticker — price action, "how did NVDA do this week and why", fundamentals
- Earnings, guidance, or what management said on a call
- The market or macro picture — the S&P/Nasdaq, the Fed, inflation, rates, jobs
- Comparing companies, screening, or "what's moving and why"
- Setting up **recurring research** — a daily market brief, a weekly recap, an
  earnings-day monitor — delivered automatically

For one-off questions, use `research`. For anything recurring or that should keep
running on its own, create an **agent**.

## Setup (once)

The CLI authenticates with an API key in the `FN2_API_KEY` environment variable.

**If the user isn't connected to FN2 yet** (no key set), the CLI prints a sign-up
link — surface it to them as the next step. Don't try to work around a missing
key; getting one is the onboarding:

> You'll need a free FN2 account to use this. Create one and grab an API key here
> (it takes a minute): **https://fn2.ai/api-keys?ref=hermes**
> Then run: `export FN2_API_KEY=fn2_...`

The `?ref=hermes` link takes them straight to key creation. Once they've exported
the key, retry their request.

Make the CLI executable the first time: `chmod +x scripts/fn2`.

## How to use it

Run the bundled CLI from this skill's directory. Add `--json` to any command when
you want machine-readable output to parse.

### Research (the most common use)

```bash
scripts/fn2 research "How did NVDA do this week, and what drove it?"
scripts/fn2 research "What's the macro backdrop going into the next Fed meeting?"
scripts/fn2 research "Summarize Apple's latest earnings call" --model z-ai/glm-5.2
```

A research call can take 30–120 seconds because FN2 pulls live data and reads
sources. The answer comes back as Markdown.

### Agents — schedule recurring research

```bash
# Run once, right now (good for a quick deep dive you want saved):
scripts/fn2 agents create --prompt "Deep dive on AMD vs NVDA in AI accelerators"

# Every weekday morning:
scripts/fn2 agents create --name "Macro Brief" \
  --prompt "Give me this morning's macro brief: overnight moves, key data, what to watch" \
  --every weekdays --timezone America/New_York

# A specific cron schedule (Mondays at 9am):
scripts/fn2 agents create --name "Weekly Tech Recap" \
  --prompt "Recap the week in big-cap tech and call out next week's catalysts" \
  --cron "0 9 * * 1" --timezone America/New_York
```

### Manage agents and read their results

```bash
scripts/fn2 agents list                       # see your agents
scripts/fn2 agents run <agent-id>             # trigger a run now
scripts/fn2 runs list <agent-id>              # list that agent's runs
scripts/fn2 runs get <agent-id> <run-id>      # read a run's full answer
scripts/fn2 agents pause <agent-id>           # pause / resume
scripts/fn2 agents resume <agent-id>
scripts/fn2 agents delete <agent-id>          # delete it and its history
```

### Account & models

```bash
scripts/fn2 models     # which models you can use (★ = your default)
scripts/fn2 usage      # your plan and token usage
```

## Good habits

- Quote the user's question closely in `research` — FN2 does the interpreting.
- After creating a scheduled agent, confirm its `id` and schedule back to the user.
- A run started with `agents run` is asynchronous: poll `runs get` until its
  status is `completed`, then share the result text.
- If you get a `403 Missing scope` error, the user's API key needs the relevant
  scope (`chat` for research, `agents` for agents, `models` for the model list).
  They can edit the key's scopes at https://fn2.ai.
- Hit a `429`? That's a quota limit — show `scripts/fn2 usage` so they can see it.

See [`references/api.md`](references/api.md) for the full command and endpoint
reference.
