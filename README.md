# aima — AIMA Labs CLI

An AWS-CLI-shaped command line for [AIMA Labs](https://aimalabs.io). Drive
voice and WhatsApp campaigns — set up a campaign, add leads, place outbound
calls, and watch their status — from a terminal, a CI pipeline, or an AI agent.

The grammar is `aima <noun> <verb>`. It's a thin, dependency-light wire-protocol
client over the `/api/cli` REST surface: every command is a 1:1 wrapper over an
endpoint, except a few client-side composites (`init`, `status`, `onboard`).

## Install

The PyPI package is `aimalabs-cli`; the command it installs is `aima`.

**Homebrew** (macOS/Linux):

```bash
brew install stepacool/tap/aima
```

**uv / pipx** — isolated install onto your PATH (provides the `aima` command):

```bash
uv tool install aimalabs-cli      # or: pipx install aimalabs-cli
```

**pip:**

```bash
pip install aimalabs-cli
```

**Run once without installing** (ephemeral — does _not_ add `aima` to your PATH).
Because the package and command names differ, `uvx` needs `--from`:

```bash
uvx --from aimalabs-cli aima --help    # not: uvx aimalabs-cli
```

Upgrade or remove an isolated install later with `uv tool upgrade aimalabs-cli`
(or `pipx upgrade` / `brew upgrade aima`) and the matching `uninstall`.

## Quick start

```bash
aima init                 # prompts for your API key, validates it, writes ~/.aima/config.json (0600)
aima voices list          # browse available voices
aima onboard              # guided: voice or WhatsApp (connect → campaign → test)
```

Or do it by hand:

```bash
aima campaigns create \
  --title "Q2 outbound" --company-name "Acme Corp" \
  --voice-id 42 \
  --field "budget:string:Ask the prospect their monthly budget." \
  --field "plan:enum:Which plan are they on?:values=free,pro,enterprise"

aima leads add-test --campaign-id 17 --lead "Jane Doe:+15551234567"
aima calls dispatch 501 --yes
aima calls status 501 --poll

# Manage agents and tweak a campaign after the fact:
aima agents list
aima agents create --name "Stefan" --company-name "Acme Corp" --voice-id 42
aima agents update 9 --system-prompt @prompts/stefan.txt
aima campaigns update 17 --title "Q2 outbound (v2)" --agent-id 9 --extra-context "Mention the summer promo."
```

## Configuration

Config lives at `~/.aima/config.json` (mode `0600`):

```json
{ "base_url": "https://api.aimalabs.io", "api_key": "api_..." }
```

Environment variables override the file:

| Variable           | Effect                                       |
| ------------------ | -------------------------------------------- |
| `AIMA_API_KEY`     | Override `api_key`.                          |
| `AIMA_BASE_URL`    | Override `base_url` (self-hosted / staging). |
| `AIMA_CONFIG`      | Use an alternate config-file path.           |
| `AIMA_OUTPUT=json` | Force machine-readable output.               |

Manage it directly:

```bash
aima config show          # api_key is masked as api_…<last4>
aima config set base_url https://staging.aimalabs.io
aima config clear
```

## Output modes

- **Human (default):** rich tables and key/value blocks. The API key is always masked.
- **`--json`:** raw response body to stdout, nothing else. The exit code carries success/failure.
- **Auto:** when stdout is not a TTY, JSON is emitted automatically. Override with `--no-json`.
- `AIMA_OUTPUT=json` behaves like `--json`.

Status lines, prompts, and errors go to **stderr**, so `--json` stdout stays clean
and pipeable:

```bash
aima campaigns list --json | jq '.[].campaign_id'
```

## Commands

| Command                                                                                               | What it does                                                      |
| ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `aima init`                                                                                           | First-run wizard: prompt, validate against the API, write config. |
| `aima status`                                                                                         | Show config and probe that the key still works.                   |
| `aima config show \| set \| clear`                                                                    | Manage local config.                                              |
| `aima voices list [--language] [--provider] [--voice-type] [--no-active]`                             | List voices (active by default).                                  |
| `aima agents list [--limit N]`                                                                        | List agents, newest first.                                        |
| `aima agents get <agent_id>`                                                                          | Show one agent, including its system prompt.                      |
| `aima agents create --name N --company-name C [--language] [--system-prompt] [--voice-id]`            | Create a reusable agent.                                          |
| `aima agents update <agent_id> [--name] [--company-name] [--language] [--system-prompt] [--voice-id]` | Update an agent (only the flags you pass).                        |
| `aima campaigns list [--active\|--inactive] [--limit N]`                                              | List campaigns, newest first.                                     |
| `aima campaigns create ...`                                                                           | Create a campaign + agent + extraction fields atomically.         |
| `aima campaigns update <campaign_id> [--title] [--agent-id] [--extra-context] [--active\|--inactive]` | Retitle, reassign the agent, or edit the prompt.                  |
| `aima leads add-test --campaign-id ID --lead NAME:E164`                                               | Add test leads (no dispatch).                                     |
| `aima leads initiate <lead_id>`                                                                       | Send WhatsApp template to a lead (confirms unless `--yes`).       |
| `aima leads upload-csv --campaign-id ID --file PATH ...`                                              | Bulk-create leads from CSV (or stdin via `--file -`).             |
| `aima whatsapp connect embedded\|coexistence`                                                         | Browser connect flow for WhatsApp credentials.                    |
| `aima whatsapp templates <credentials_id>`                                                            | List APPROVED message templates.                                  |
| `aima calls dispatch <lead_id>`                                                                       | Place a **real** outbound call (confirms unless `--yes`).         |
| `aima calls status <lead_id> [--poll]`                                                                | Lead status (call + conversation); `--poll` until terminal.       |
| `aima onboard`                                                                                        | Interactive walkthrough (`voice` or `whatsapp`).                  |

### Defining extraction fields

`--field` is repeatable. Each token is `title:type:description`:

```bash
--field "budget:string:Ask their monthly budget."
--field "meeting:calendar_appointment:Book a demo."
--field "tier:enum:Which tier?:values=bronze,silver,gold"
```

Types: `string`, `integer`, `float`, `boolean`, `date`, `datetime`, `enum`,
`json`, `array`, `calendar_appointment`, `file`. Enum types require the
trailing `:values=...`.

`--system-prompt` and `--extra-context` accept a literal string or `@path/to/file`
to read from disk. The whole request body can also be supplied with
`--from-yaml body.yaml`; explicit flags override values from the YAML.

## Exit codes

| Code | Meaning                                                                                 |
| ---- | --------------------------------------------------------------------------------------- |
| `0`  | Success.                                                                                |
| `1`  | User error — bad flags, validation, or a 4xx from the API (`detail` printed to stderr). |
| `2`  | Server / network error — a 5xx or a transport failure.                                  |
| `3`  | Missing or invalid config (no API key, unreadable file).                                |

## For AI agents

`aima` is designed to be driven by coding agents. Tips:

- Set `AIMA_OUTPUT=json` (or pass `--json`) for deterministic, parseable output.
- Every error prints the backend's `detail` to stderr and uses a stable exit code.
- `aima <noun> --help` and `aima <noun> <verb> --help` describe every flag.
- Calls that cost money (`calls dispatch`, large `upload-csv`) require `--yes` in
  non-interactive contexts.

## Development

```bash
uv pip install -e ".[dev]"
pytest
ruff check src
```

## License

MIT
