---
name: aima
description: >-
  Drive AIMA Labs voice/WhatsApp campaigns from the command line with the `aima`
  CLI. Use when the user wants to create or update a campaign or agent, add or
  upload leads, place outbound calls, check call status/results, browse voices,
  or configure `aima` credentials. Grammar is `aima <noun> <verb>`.
---

# aima — AIMA Labs CLI

`aima` is an AWS-CLI-shaped client over the AIMA Labs `/api/cli` REST surface.
Every command is `aima <noun> <verb>` and maps 1:1 to an endpoint, except the
client-side composites `init`, `status`, and `onboard`.

The PyPI package is `aimalabs-cli`; the installed command is `aima`.

## Golden rules

1. **Drive the real `aima` binary** — never reproduce calls with `curl`/`httpx`.
   Reach for `aima ... --help` when unsure of a flag.
2. **Always run non-interactively.** Pass `--json` (or set `AIMA_OUTPUT=json`)
   so output is deterministic and parseable, and pass `--yes` on commands that
   cost money or place calls. Without a TTY, `aima` already auto-emits JSON, but
   be explicit.
3. **`stdout` is data; `stderr` is chatter.** With `--json`, only the raw
   response body goes to stdout. Status, prompts, and errors go to stderr. Pipe
   stdout straight into `jq`.
4. **Trust the exit code**, don't scrape prose:
   `0` success · `1` user error / 4xx · `2` server / network (5xx) · `3`
   missing/invalid config.
5. **`calls dispatch` places a REAL phone call.** Confirm intent with the user,
   then pass `--yes`. Default to **test** leads (`leads add-test`) while iterating.

## Setup & config

```bash
aima status --json            # check whether a working key is configured
aima init                     # interactive: prompt + validate + write ~/.aima/config.json (0600)
aima config show              # api_key masked as api_…<last4>
aima config set base_url https://staging.aimalabs.io
aima config clear
```

Config file: `~/.aima/config.json`. Env overrides (take precedence over file):

| Variable | Effect |
|---|---|
| `AIMA_API_KEY` | Override `api_key` (use in CI instead of `init`). |
| `AIMA_BASE_URL` | Override `base_url` (self-hosted / staging). |
| `AIMA_CONFIG` | Use an alternate config-file path. |
| `AIMA_OUTPUT=json` | Force machine-readable output. |

If `aima status` exits `3`, there's no usable key — ask the user to run `aima init`
or set `AIMA_API_KEY`; don't try to invent one.

## Core workflow

```bash
# 1. Pick a voice
aima voices list --json | jq '.[] | {voice_id, name, language}'

# 2. Create a campaign (creates campaign + agent + extraction fields atomically)
aima campaigns create \
  --title "Q2 outbound" --company-name "Acme Corp" --voice-id 42 \
  --field "budget:string:Ask the prospect their monthly budget." \
  --field "tier:enum:Which tier?:values=bronze,silver,gold" \
  --json

# 3. Add a TEST lead while iterating (no dispatch)
aima leads add-test --campaign-id 17 --lead "Jane Doe:+15551234567" --json

# 4. Place a REAL call (confirm with the user first)
aima calls dispatch 501 --yes --json

# 5. Watch it to completion and read extracted values
aima calls status 501 --poll --json
```

## Command reference

| Command | Notes |
|---|---|
| `aima voices list [--language] [--provider] [--voice-type] [--no-active]` | Active voices by default. |
| `aima agents list [--limit N]` / `aima agents get <id>` | `get` includes the full system prompt. |
| `aima agents create --name N --company-name C [--language] [--system-prompt] [--voice-id]` | Reusable agent. |
| `aima agents update <id> [--name] [--company-name] [--language] [--system-prompt] [--voice-id]` | Only the flags you pass change. |
| `aima campaigns list [--active\|--inactive] [--limit N]` | Newest first. |
| `aima campaigns create ...` | Campaign + agent + fields in one call. See fields below. |
| `aima campaigns update <id> [--title] [--agent-id] [--extra-context] [--active\|--inactive]` | Retitle, reassign agent, edit context. |
| `aima leads add-test --campaign-id ID --lead "NAME:+E164"` | Repeat `--lead` for several. No call placed. |
| `aima leads upload-csv --campaign-id ID --file PATH [--map ...]` | Bulk create. `--file -` reads stdin. |
| `aima calls dispatch <lead_id> --yes` | **Real** outbound call. |
| `aima calls status <lead_id> [--poll]` | Latest status + extracted values; `--poll` blocks until the call ends. |

### Extraction fields (`--field`, repeatable)

Token format `title:type:description` (enums add a trailing `:values=...`):

```bash
--field "budget:string:Ask their monthly budget."
--field "meeting:calendar_appointment:Book a demo."
--field "tier:enum:Which tier?:values=bronze,silver,gold"
```

Types: `string`, `integer`, `float`, `boolean`, `date`, `datetime`, `enum`,
`json`, `array`, `calendar_appointment`, `file`.

### Reading from files & YAML

- `--system-prompt` and `--extra-context` accept a literal string **or**
  `@path/to/file` to read from disk.
- A whole request body can be supplied with `--from-yaml body.yaml`; explicit
  flags override values from the YAML.

## Discovering details

When you need a flag you don't see here, ask the CLI itself — it's the source of
truth and stays in sync with the installed version:

```bash
aima --help
aima <noun> --help
aima <noun> <verb> --help
aima --version
```
