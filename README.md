<div align="center">

# FN2 skill for Hermes Agent

**Grounded market research and schedulable research agents — right inside [Hermes](https://hermes-agent.nousresearch.com).**

[![CI](https://github.com/fn2ai/fn2-hermes-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/fn2ai/fn2-hermes-skill/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Agent Skills](https://img.shields.io/badge/agentskills.io-compatible-7c3aed.svg)](https://agentskills.io)

</div>

Ask your Hermes agent *"how did NVDA do this week and why?"* or *"set up a daily
macro brief"* — and it answers with [FN2](https://fn2.ai)'s grounded, sourced
research, or spins up an agent that does it on a schedule.

- 🔎 **Research** stocks, markets, earnings, and the economy — answers cite live
  prices, transcripts, filings, and economic data.
- 🤖 **Agents** that run on a schedule (daily brief, weekly recap, earnings
  monitor) and report back.
- 🪶 **Zero dependencies.** One small Python-3-stdlib CLI. No `pip install`.
- 🔓 **No secrets in the repo.** Auth is a `FN2_API_KEY` you provide.

---

## Install

**With the Hermes CLI** (recommended):

```bash
hermes skills install github:fn2ai/fn2-hermes-skill/skills/fn2
```

**Or manually** — copy the skill into your Hermes skills directory:

```bash
git clone https://github.com/fn2ai/fn2-hermes-skill.git
mkdir -p ~/.hermes/skills/research
cp -r fn2-hermes-skill/skills/fn2 ~/.hermes/skills/research/fn2
chmod +x ~/.hermes/skills/research/fn2/scripts/fn2
```

## Get an API key

New to FN2? Create a free account and API key here — it takes a minute:

### → **[fn2.ai/api-keys?ref=hermes](https://fn2.ai/api-keys?ref=hermes)**

(Give the key the `chat`, `agents`, and `models` scopes.) Then export it so the
skill can use it:

```bash
export FN2_API_KEY=fn2_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

If you don't have a key set, the skill points you to that link automatically.

> 🔒 Treat this key like a password. Never commit it or paste it into a chat.
> You can revoke it any time from the same page.

## Use it

Just talk to your agent:

> **You:** How did the semiconductor stocks do today, and what moved them?
>
> **You:** Set up an agent that emails me a market brief every weekday at 8am ET.
>
> **You:** What did Apple's CFO say about guidance on the last call?

Hermes loads the skill on demand and runs the bundled CLI for you.

### Or run the CLI directly

```bash
fn2=~/.hermes/skills/research/fn2/scripts/fn2

$fn2 research "What's the macro setup going into the next Fed meeting?"
$fn2 agents create --name "Macro Brief" \
     --prompt "Morning macro brief: overnight moves, key data, what to watch" \
     --every weekdays --timezone America/New_York
$fn2 agents list
$fn2 models
```

Add `--json` to any command for machine-readable output. See
[`skills/fn2/references/api.md`](skills/fn2/references/api.md) for the full
command and endpoint reference.

## What's in here

```
skills/fn2/
├── SKILL.md            # the skill (agentskills.io standard)
├── scripts/fn2         # the CLI (Python 3 stdlib, no deps)
└── references/api.md   # full command + API reference
tests/                  # offline unit tests (mocked HTTP)
```

## Develop & test

The CLI is plain Python 3 (3.8+). Tests are fully offline — no key needed:

```bash
python3 -m unittest discover -s tests
```

CI runs the test suite and an install-smoke check on every push. Contributions
welcome — open an issue or PR.

## Compatibility

`SKILL.md` follows the open **[agentskills.io](https://agentskills.io)** standard,
so this skill also works with OpenClaw, Claude Code, Codex CLI, OpenCode, and
other compatible agents. An OpenClaw-packaged version lives at
[fn2-openclaw-skill](https://github.com/fn2ai/fn2-openclaw-skill).

## License

[MIT](LICENSE) © FN2. Not affiliated with Nous Research or Hermes Agent.
